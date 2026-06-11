# -*- coding: utf-8 -*-
"""
悬浮在桌面上的像素猫本体。

- 透明无边框、永远置顶、不进任务栏（Qt.Tool）。
- QTimer 驱动：随机眨眼；说话时在 talk 帧间切换。
- 左键拖动并记忆位置；位移很小时算「单击」→ 唤出聊天面板。
- 闲着时偶尔冒泡吐槽一句（毒舌打工人嘴替金句）。
"""

import random

from PySide6.QtCore import Qt, QTimer, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

import config
import cat_sprite

SCALE = 6  # 像素放大倍数
CAT_W = cat_sprite.GRID_W * SCALE
CAT_H = cat_sprite.GRID_H * SCALE
BUBBLE_MAX_W = 200  # 气泡最大宽度
CLICK_THRESHOLD = 5  # 位移小于这个像素算单击而非拖动

# 闲时随机冒泡的金句
_IDLE_LINES = [
    "老板又在画饼了吧？",
    "摸鱼使我快乐 🐟",
    "这班是一秒都不想上了。",
    "你没错，错的是这个班。",
    "KPI 是老板的，不是你的。",
    "累了就歇会儿，地球照样转。",
    "甲方又改需求了？损他！",
    "今天也辛苦了，靠过来吧。",
    "想骂谁？我陪你。",
    "周一已经够惨了，对自己好点。",
]


class PetWindow(QWidget):
    # 单击猫：把猫当前的屏幕坐标传出去，让外部决定在哪弹聊天面板
    clicked = Signal(int, int)

    def __init__(self, settings: config.Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(CAT_W + 2 * BUBBLE_MAX_W, CAT_H + 90)
        # 窗口比猫大一圈，给气泡留空间；猫画在底部居中区域。
        self._cat_origin = ((self.width() - CAT_W) // 2, self.height() - CAT_H)

        self._frame = "idle"
        self._talking = False
        self._talk_toggle = False
        self._bubble_text = ""

        self._drag_offset = None
        self._press_pos = None

        # 恢复上次位置，否则放右下角
        pos = self.settings.pet_pos()
        if pos is None:
            screen = self.screen().availableGeometry()
            pos = (screen.right() - self.width() + BUBBLE_MAX_W,
                   screen.bottom() - self.height())
        self.move(*pos)

        # 眨眼定时器：随机间隔
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._do_blink)
        self._schedule_blink()

        # 说话动画定时器
        self._talk_timer = QTimer(self)
        self._talk_timer.timeout.connect(self._tick_talk)

        # 气泡自动消失
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._clear_bubble)

        # 闲时随机冒泡
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._maybe_idle_chatter)
        self._idle_timer.start(20000)  # 每 20s 掷一次骰子

    # ── 绘制 ─────────────────────────────────────────────────────────
    def paintEvent(self, _):
        painter = QPainter(self)
        ox, oy = self._cat_origin
        # 画猫
        pm = cat_sprite.render_frame(self._frame, SCALE)
        painter.drawPixmap(ox, oy, pm)
        # 画气泡
        if self._bubble_text:
            self._paint_bubble(painter)
        painter.end()

    def _paint_bubble(self, painter: QPainter):
        font = QFont()
        font.setPixelSize(13)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # 计算换行后的文本区域
        pad = 10
        text_rect = fm.boundingRect(
            QRect(0, 0, BUBBLE_MAX_W, 1000),
            Qt.TextWordWrap, self._bubble_text,
        )
        w = text_rect.width() + 2 * pad
        h = text_rect.height() + 2 * pad
        # 气泡放在猫正上方居中
        ox, oy = self._cat_origin
        bx = ox + (CAT_W - w) // 2
        by = oy - h - 8
        if bx < 4:
            bx = 4

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(255, 251, 245))
        painter.setPen(QColor(247, 167, 76))
        painter.drawRoundedRect(bx, by, w, h, 10, 10)
        # 小尾巴（三角）
        painter.setPen(Qt.NoPen)
        tail_cx = ox + CAT_W // 2
        painter.drawPolygon(
            *[
                QPoint(tail_cx - 6, by + h - 1),
                QPoint(tail_cx + 6, by + h - 1),
                QPoint(tail_cx, by + h + 8),
            ]
        )
        painter.setPen(QColor(58, 43, 26))
        painter.drawText(
            QRect(bx + pad, by + pad, w - 2 * pad, h - 2 * pad),
            Qt.TextWordWrap, self._bubble_text,
        )

    # ── 眨眼 ─────────────────────────────────────────────────────────
    def _schedule_blink(self):
        self._blink_timer.start(random.randint(2500, 6000))

    def _do_blink(self):
        if self._talking:
            self._schedule_blink()
            return
        self._frame = "blink"
        self.update()
        QTimer.singleShot(140, self._end_blink)

    def _end_blink(self):
        if not self._talking:
            self._frame = "idle"
            self.update()
        self._schedule_blink()

    # ── 说话动画（由聊天面板的 talking 信号驱动）──────────────────────
    def set_talking(self, on: bool):
        self._talking = on
        if on:
            self._talk_timer.start(220)
        else:
            self._talk_timer.stop()
            self._frame = "idle"
            self.update()

    def _tick_talk(self):
        self._talk_toggle = not self._talk_toggle
        self._frame = "talk1" if self._talk_toggle else "talk2"
        self.update()

    # ── 气泡 ─────────────────────────────────────────────────────────
    def say(self, text: str, ms: int = 4000):
        self._bubble_text = text
        self.update()
        self._bubble_timer.start(ms)

    def _clear_bubble(self):
        self._bubble_text = ""
        self.update()

    def _maybe_idle_chatter(self):
        # 没说话且没气泡时，约 1/3 概率冒一句
        if not self._talking and not self._bubble_text and random.random() < 0.35:
            self.say(random.choice(_IDLE_LINES))

    # ── 拖动 / 单击 ──────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press_pos is None:
            return
        moved = (e.globalPosition().toPoint() - self._press_pos).manhattanLength()
        self._drag_offset = None
        if moved <= CLICK_THRESHOLD:
            # 算单击 → 唤出聊天，传猫头左上角屏幕坐标
            ox, oy = self._cat_origin
            gp = self.mapToGlobal(QPoint(ox, oy))
            self.clicked.emit(gp.x(), gp.y())
        else:
            # 算拖动 → 记忆新位置
            self.settings.set_pet_pos(self.x(), self.y())
        self._press_pos = None

    def cat_top_left_global(self):
        """猫头左上角的屏幕坐标，供外部定位聊天面板。"""
        ox, oy = self._cat_origin
        gp = self.mapToGlobal(QPoint(ox, oy))
        return gp.x(), gp.y()
