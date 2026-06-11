# -*- coding: utf-8 -*-
"""
AI 流式 worker：在独立 QThread 里跑 Anthropic 流式请求，
通过 Signal 把 token 块推回 UI 线程——绝不在子线程里碰任何 Qt 控件。

- chunk(str)  每来一段文本就发一次（增量，不是全量）
- done(str)   正常结束，带完整回复
- failed(str) 出错，带一句友好的中文提示

内置限流/过载自动重试（仅在还没吐出第一个字之前重试，避免重复输出），
支持中途取消（cancel()）。
"""

import time
import random

import anthropic
from PySide6.QtCore import QThread, Signal

import config

# 整个进程共用一个 client（线程安全，自动从 ANTHROPIC_API_KEY 读 key）
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class AiWorker(QThread):
    chunk = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, messages, system_prompt, parent=None):
        super().__init__(parent)
        self._messages = messages
        self._system = system_prompt
        self._stop = False

    def cancel(self):
        """请求中止：循环里会检测到并尽快收尾。"""
        self._stop = True

    def run(self):
        client = _get_client()
        partial = ""
        started = False  # 是否已吐出第一个字；吐过就不再重试，避免重复
        attempt = 0

        while True:
            try:
                with client.messages.stream(
                    model=config.MODEL,
                    max_tokens=config.MAX_TOKENS,
                    system=self._system,
                    messages=self._messages,
                ) as stream:
                    for text in stream.text_stream:
                        if self._stop:
                            self.done.emit(partial)
                            return
                        started = True
                        partial += text
                        self.chunk.emit(text)
                self.done.emit(partial)
                return

            except anthropic.AuthenticationError:
                self.failed.emit(
                    "⚠️ API key 没设置或者无效。请设好 ANTHROPIC_API_KEY 再试。"
                )
                return

            except (anthropic.RateLimitError, anthropic.APIStatusError,
                    anthropic.APIConnectionError) as e:
                # 已经开始吐字就不能重试（会重复），直接报错收场
                attempt += 1
                if started or attempt > config.MAX_RETRIES or self._stop:
                    if isinstance(e, anthropic.RateLimitError):
                        self.failed.emit("⚠️ 请求太频繁被限流了，喝口水等几秒再发。")
                    else:
                        self.failed.emit(f"⚠️ 服务暂时不稳：{type(e).__name__}，待会儿再试。")
                    return
                # 指数退避 + 抖动后重试
                time.sleep(min(2 ** attempt, 8) + random.random())

            except Exception as e:
                self.failed.emit(f"⚠️ 出了点岔子：{type(e).__name__}: {e}")
                return
