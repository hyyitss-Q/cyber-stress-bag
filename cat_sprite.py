# -*- coding: utf-8 -*-
"""
纯代码绘制的像素风小猫，不依赖任何外部图片素材。

每帧是一组等宽字符串（ASCII 像素图），配一张调色板（字符 → 颜色）。
render_frame() 用 QPainter 把每个像素放大成方块画到透明 QPixmap 上。

帧：
  idle    默认睁眼
  blink   眨眼（闭眼一线）
  talk1   张嘴 A
  talk2   张嘴 B（和 talk1 交替形成说话动画）

同一套绘制也用来生成托盘小图标。
"""

from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from PySide6.QtCore import Qt

# 调色板：字符 → RGBA。'.' 表示透明，不画。
PALETTE = {
    "B": QColor(45, 35, 40),      # 描边/深色
    "O": QColor(247, 167, 76),    # 橘猫主体
    "D": QColor(214, 124, 45),    # 暗部
    "W": QColor(255, 251, 245),   # 奶白肚皮/嘴周
    "P": QColor(255, 150, 170),   # 粉（耳内/鼻/舌）
    "E": QColor(55, 45, 50),      # 眼睛
    "H": QColor(255, 255, 255),   # 眼睛高光
}

# 所有帧宽 16、高 16。'.' = 透明。
_IDLE = [
    "...B........B...",
    "..BPB......BPB..",
    "..BOBBBBBBBBOB..",
    ".BOOOOOOOOOOOOB.",
    ".BOOOOOOOOOOOOB.",
    ".BOEHEOOOOEHEOB.",
    ".BOEEEOOOOEEEOB.",
    ".BOOOOODDOOOOOB.",
    ".BOOOOOPPOOOOOB.",
    ".BOOOOWWWWOOOOB.",
    "..BOOOOOOOOOOB..",
    "..BOWWWWWWWWOB..",
    ".BOOWWWWWWWWOOB.",
    ".BOOWWWWWWWWOOB.",
    ".BDOWWWWWWWWODB.",
    "..BBBBBBBBBBBB..",
]

_BLINK = [
    "...B........B...",
    "..BPB......BPB..",
    "..BOBBBBBBBBOB..",
    ".BOOOOOOOOOOOOB.",
    ".BOOOOOOOOOOOOB.",
    ".BOOOOOOOOOOOOB.",
    ".BOBBOOOOOOBBOB.",
    ".BOOOOODDOOOOOB.",
    ".BOOOOOPPOOOOOB.",
    ".BOOOOWWWWOOOOB.",
    "..BOOOOOOOOOOB..",
    "..BOWWWWWWWWOB..",
    ".BOOWWWWWWWWOOB.",
    ".BOOWWWWWWWWOOB.",
    ".BDOWWWWWWWWODB.",
    "..BBBBBBBBBBBB..",
]

_TALK1 = [
    "...B........B...",
    "..BPB......BPB..",
    "..BOBBBBBBBBOB..",
    ".BOOOOOOOOOOOOB.",
    ".BOOOOOOOOOOOOB.",
    ".BOEHEOOOOEHEOB.",
    ".BOEEEOOOOEEEOB.",
    ".BOOOOODDOOOOOB.",
    ".BOOOOBPPBOOOOB.",
    ".BOOOOBPPBOOOOB.",
    "..BOOOBBBBOOOB..",
    "..BOWWWWWWWWOB..",
    ".BOOWWWWWWWWOOB.",
    ".BOOWWWWWWWWOOB.",
    ".BDOWWWWWWWWODB.",
    "..BBBBBBBBBBBB..",
]

_TALK2 = [
    "...B........B...",
    "..BPB......BPB..",
    "..BOBBBBBBBBOB..",
    ".BOOOOOOOOOOOOB.",
    ".BOOOOOOOOOOOOB.",
    ".BOEHEOOOOEHEOB.",
    ".BOEEEOOOOEEEOB.",
    ".BOOOOODDOOOOOB.",
    ".BOOOOOPPOOOOOB.",
    ".BOOOOBPPBOOOOB.",
    "..BOOOBPPBOOOB..",
    "..BOWWWBBWWWOB..",
    ".BOOWWWWWWWWOOB.",
    ".BOOWWWWWWWWOOB.",
    ".BDOWWWWWWWWODB.",
    "..BBBBBBBBBBBB..",
]

FRAMES = {
    "idle": _IDLE,
    "blink": _BLINK,
    "talk1": _TALK1,
    "talk2": _TALK2,
}

# 网格尺寸（所有帧必须一致），启动时校验，miscount 会立刻报错而不是默默画歪。
GRID_W = 16
GRID_H = 16


def _validate():
    for name, frame in FRAMES.items():
        if len(frame) != GRID_H:
            raise ValueError(f"帧 {name} 应有 {GRID_H} 行，实际 {len(frame)} 行")
        for i, row in enumerate(frame):
            if len(row) != GRID_W:
                raise ValueError(
                    f"帧 {name} 第 {i} 行应有 {GRID_W} 列，实际 {len(row)} 列：{row!r}"
                )


_validate()


def render_frame(name: str = "idle", scale: int = 6) -> QPixmap:
    """把指定帧渲染成放大 scale 倍的透明 QPixmap。"""
    frame = FRAMES.get(name, _IDLE)
    pm = QPixmap(GRID_W * scale, GRID_H * scale)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    for y, row in enumerate(frame):
        for x, ch in enumerate(row):
            color = PALETTE.get(ch)
            if color is not None:
                painter.fillRect(x * scale, y * scale, scale, scale, color)
    painter.end()
    return pm


def make_icon(scale: int = 2) -> QIcon:
    """生成托盘用的小猫图标。"""
    return QIcon(render_frame("idle", scale))
