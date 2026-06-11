# -*- coding: utf-8 -*-
"""
配置与状态持久化，集中一处管理：

- 环境变量：API key、模型、max_tokens、热键、重试次数等（含手写 .env 读取）。
- 轻量配置（QSettings）：窗口位置、当前模式、毒舌强度、自启开关。
- 对话历史（history.json）：较大，单独存文件。

其它模块只跟这里打交道，不直接碰 os.environ / QSettings / 文件路径。
"""

import os
import json

from PySide6.QtCore import QSettings

from prompts import MODE_LABELS

# 组织名/应用名，QSettings 和数据目录都用它
ORG = "CyberStressBag"
APP = "DesktopCat"

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── .env 读取（不依赖额外库，让小白也能跑起来）──────────────────────
def _load_dotenv():
    path = os.path.join(_PROJECT_DIR, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


# ── 环境变量集中读取 ────────────────────────────────────────────────
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# 模型与生成参数都可经环境变量覆盖
MODEL = os.environ.get("CYBERCAT_MODEL", "").strip() or "claude-opus-4-8"
MAX_TOKENS = _env_int("CYBERCAT_MAX_TOKENS", 2048)
MAX_RETRIES = _env_int("CYBERCAT_MAX_RETRIES", 3)

# 全局热键，形如 "Ctrl+Alt+C"，由 hotkey.py 解析
HOTKEY = os.environ.get("CYBERCAT_HOTKEY", "").strip() or "Ctrl+Alt+C"


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# ── 对话历史持久化（history.json）──────────────────────────────────
def _history_path() -> str:
    return os.path.join(_PROJECT_DIR, "history.json")


def load_history() -> list:
    """读对话历史，返回 messages 列表 [{"role","content"}, ...]，出错则空。"""
    path = _history_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [
                m
                for m in data
                if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
            ]
    except (OSError, ValueError):
        pass
    return []


def save_history(messages: list) -> None:
    """把 messages 列表写回 history.json。"""
    try:
        with open(_history_path(), "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def clear_history() -> None:
    """清空对话：删掉历史文件。"""
    try:
        os.remove(_history_path())
    except OSError:
        pass


def export_history(messages: list, path: str) -> None:
    """把对话导出成可读的纯文本到指定路径。"""
    lines = []
    for m in messages:
        who = "我" if m.get("role") == "user" else "损友猫"
        lines.append(f"{who}：{m.get('content', '')}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── 轻量配置（QSettings）────────────────────────────────────────────
class Settings:
    """窗口位置 / 模式 / 毒舌强度 / 自启开关，用 QSettings 存注册表（Win）。"""

    def __init__(self):
        self._s = QSettings(ORG, APP)

    # 窗口位置：返回 (x, y) 或 None（首次启动让调用方自己定默认位）
    def pet_pos(self):
        x = self._s.value("pet/x")
        y = self._s.value("pet/y")
        if x is None or y is None:
            return None
        try:
            return int(x), int(y)
        except (TypeError, ValueError):
            return None

    def set_pet_pos(self, x: int, y: int):
        self._s.setValue("pet/x", int(x))
        self._s.setValue("pet/y", int(y))

    # 当前模式：非法值回退到第一个模式
    def mode(self) -> str:
        m = self._s.value("chat/mode", MODE_LABELS[0])
        return m if m in MODE_LABELS else MODE_LABELS[0]

    def set_mode(self, mode: str):
        self._s.setValue("chat/mode", mode)

    # 毒舌强度 0-100
    def savagery(self) -> int:
        try:
            v = int(self._s.value("chat/savagery", 66))
        except (TypeError, ValueError):
            v = 66
        return max(0, min(100, v))

    def set_savagery(self, value: int):
        self._s.setValue("chat/savagery", max(0, min(100, int(value))))

    # 开机自启开关（仅记录用户意愿，实际写注册表由 autostart.py 做）
    def autostart(self) -> bool:
        return str(self._s.value("app/autostart", "false")).lower() == "true"

    def set_autostart(self, on: bool):
        self._s.setValue("app/autostart", "true" if on else "false")
