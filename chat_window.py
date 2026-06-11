# -*- coding: utf-8 -*-
"""
聊天面板：无边框圆角小窗，点猫时弹出。

布局：
  顶部  标题 + 模式下拉 + 毒舌强度滑块 + 关闭
  中间  消息区（流式逐字显示）
  底部  输入框（回车发送，Shift+回车换行）+ 发送 / 清空 / 导出

对话历史会持久化（config.history），说话时发 talking 信号让猫张嘴。
"""

import html

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
    QTextEdit, QPushButton, QFileDialog,
)

import config
from prompts import MODE_LABELS, MODE_HINTS, build_system_prompt
from ai_worker import AiWorker


def _savagery_word(v: int) -> str:
    if v <= 33:
        return "温柔顺毛"
    if v <= 66:
        return "正常损友"
    return "殇血开炮"


class _InputBox(QTextEdit):
    """回车发送、Shift+回车换行的输入框。"""

    submitted = Signal()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            e.modifiers() & Qt.ShiftModifier
        ):
            self.submitted.emit()
            return
        super().keyPressEvent(e)


class ChatWindow(QWidget):
    # 猫说话状态：True=开始/进行中（张嘴动），False=说完（回到 idle）
    talking = Signal(bool)

    def __init__(self, settings: config.Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.messages = config.load_history()
        self.worker = None
        self._partial = ""        # 当前正在流式接收的 assistant 文本
        self._drag_offset = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(380, 520)

        self._build_ui()
        self._render_messages()

    # ── UI 搭建 ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QWidget(self)
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        root = QVBoxLayout(self.card)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # 顶部：标题 + 关闭
        header = QHBoxLayout()
        title = QLabel("🐱 赛博损友猫")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        root.addLayout(header)

        # 模式下拉
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式"))
        self.mode_box = QComboBox()
        self.mode_box.addItems(MODE_LABELS)
        self.mode_box.setCurrentText(self.settings.mode())
        self.mode_box.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_box, 1)
        root.addLayout(mode_row)

        # 毒舌强度滑块
        sav_row = QHBoxLayout()
        sav_row.addWidget(QLabel("毒舌"))
        self.sav_slider = QSlider(Qt.Horizontal)
        self.sav_slider.setRange(0, 100)
        self.sav_slider.setValue(self.settings.savagery())
        self.sav_slider.valueChanged.connect(self._on_savagery_changed)
        sav_row.addWidget(self.sav_slider, 1)
        self.sav_label = QLabel(_savagery_word(self.settings.savagery()))
        self.sav_label.setFixedWidth(64)
        sav_row.addWidget(self.sav_label)
        root.addLayout(sav_row)

        # 模式说明
        self.hint = QLabel(MODE_HINTS.get(self.settings.mode(), ""))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        # 消息区
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setObjectName("view")
        root.addWidget(self.view, 1)

        # 输入框
        self.input = _InputBox()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("把今天的破事打在这里，回车发送，Shift+回车换行…")
        self.input.setFixedHeight(64)
        self.input.submitted.connect(self._on_send)
        root.addWidget(self.input)

        # 底部按钮
        btn_row = QHBoxLayout()
        self.send_btn = QPushButton("发送 💢")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(self.send_btn, 1)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(export_btn)
        root.addLayout(btn_row)

        self.setStyleSheet(_STYLE)

    # ── 模式 / 毒舌 ──────────────────────────────────────────────────
    def _on_mode_changed(self, mode: str):
        self.settings.set_mode(mode)
        self.hint.setText(MODE_HINTS.get(mode, ""))

    def _on_savagery_changed(self, value: int):
        self.settings.set_savagery(value)
        self.sav_label.setText(_savagery_word(value))

    # ── 消息渲染 ─────────────────────────────────────────────────────
    def _render_messages(self, streaming_partial: str = None):
        """把 self.messages 全量渲染进 view，可选追加一个正在流式的 assistant 段。"""
        parts = []
        for m in self.messages:
            parts.append(self._bubble(m["role"], m["content"]))
        if streaming_partial is not None:
            parts.append(self._bubble("assistant", streaming_partial))
        self.view.setHtml("".join(parts))
        # 滚到底
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _bubble(role: str, content: str) -> str:
        safe = html.escape(content).replace("\n", "<br>")
        if role == "user":
            return (
                f'<div style="margin:6px 0;text-align:right;">'
                f'<span style="background:#ffd9a0;color:#3a2b1a;padding:6px 10px;'
                f'border-radius:10px;display:inline-block;max-width:78%;text-align:left;">'
                f'{safe}</span></div>'
            )
        return (
            f'<div style="margin:6px 0;text-align:left;">'
            f'<span style="background:#3a3340;color:#fdf6ee;padding:6px 10px;'
            f'border-radius:10px;display:inline-block;max-width:78%;">'
            f'{safe}</span></div>'
        )

    # ── 发送 / 流式 ──────────────────────────────────────────────────
    def _on_send(self):
        if self.worker is not None:  # 上一条还在跑
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()

        self.messages.append({"role": "user", "content": text})
        config.save_history(self.messages)

        self._partial = ""
        self._render_messages(streaming_partial="…")
        self.send_btn.setEnabled(False)
        self.talking.emit(True)

        system_prompt = build_system_prompt(
            self.settings.mode(), self.settings.savagery()
        )
        self.worker = AiWorker(list(self.messages), system_prompt, self)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_chunk(self, text: str):
        self._partial += text
        self._render_messages(streaming_partial=self._partial)

    def _on_done(self, full: str):
        if full.strip():
            self.messages.append({"role": "assistant", "content": full})
            config.save_history(self.messages)
        self._finish_stream()
        self._render_messages()

    def _on_failed(self, msg: str):
        # 失败时把刚加进去的 user 消息保留，错误作为一条 assistant 提示展示（但不入库）
        self._finish_stream()
        self._render_messages(streaming_partial=msg)

    def _finish_stream(self):
        self.worker = None
        self._partial = ""
        self.send_btn.setEnabled(True)
        self.talking.emit(False)
        self.input.setFocus()

    # ── 清空 / 导出 ──────────────────────────────────────────────────
    def _on_clear(self):
        self.messages = []
        config.clear_history()
        self._render_messages()

    def _on_export(self):
        if not self.messages:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出对话", "赛博出气包对话.txt", "文本文件 (*.txt)"
        )
        if path:
            config.export_history(self.messages, path)

    # ── 拖动（点标题区域拖整个窗）+ 关闭收尾 ──────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None

    def show_near(self, x: int, y: int):
        """在给定屏幕坐标附近弹出（猫的位置旁边）。"""
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def shutdown(self):
        """退出前收尾：取消在跑的 worker 并等它结束。"""
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait(2000)
            self.worker = None


_STYLE = """
#card {
    background: #2b2630;
    border: 2px solid #f7a74c;
    border-radius: 14px;
}
QLabel { color: #f0e9e0; font-size: 13px; }
#title { font-size: 15px; font-weight: bold; color: #f7a74c; }
#hint { color: #b9aeb0; font-size: 11px; }
#closeBtn {
    background: transparent; color: #b9aeb0; border: none; font-size: 14px;
}
#closeBtn:hover { color: #ff8898; }
#view {
    background: #211d26; border: 1px solid #443d4a; border-radius: 8px;
    color: #fdf6ee; font-size: 13px;
}
#input {
    background: #211d26; border: 1px solid #443d4a; border-radius: 8px;
    color: #fdf6ee; font-size: 13px; padding: 4px;
}
QComboBox, QPushButton {
    background: #3a3340; color: #fdf6ee; border: 1px solid #554d5c;
    border-radius: 8px; padding: 5px 10px; font-size: 13px;
}
QComboBox:hover, QPushButton:hover { background: #473e4f; }
#sendBtn { background: #f7a74c; color: #2b2630; font-weight: bold; border: none; }
#sendBtn:hover { background: #ffb866; }
#sendBtn:disabled { background: #6b5a44; color: #b9aeb0; }
QSlider::groove:horizontal { height: 6px; background: #443d4a; border-radius: 3px; }
QSlider::handle:horizontal {
    background: #f7a74c; width: 14px; margin: -5px 0; border-radius: 7px;
}
"""
