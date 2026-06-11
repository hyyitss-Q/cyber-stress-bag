# -*- coding: utf-8 -*-
"""
赛博出气包 · 桌面像素猫 —— 程序入口。

一只常驻桌面的像素小猫：单击它跟它吐槽，它会眨眼、随机冒泡。
托盘图标和全局热键随时呼出/隐藏。四种损友模式 + 毒舌强度可调。

运行前先设好 API key（任选一种）：
  bash:   export ANTHROPIC_API_KEY="sk-ant-..."
  或在同目录建 .env 文件写一行：ANTHROPIC_API_KEY=sk-ant-...

启动：python main.py
"""

import sys

from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
)
from PySide6.QtGui import QAction, QActionGroup

import config
import autostart
import cat_sprite
from prompts import MODE_LABELS
from pet_window import PetWindow
from chat_window import ChatWindow
from hotkey import HotKeyManager


class CyberCatApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.settings = config.Settings()

        # 把保存的自启意愿同步到注册表实际状态（防手动改注册表后不一致）
        if autostart.is_supported():
            autostart.set_enabled(self.settings.autostart())

        self.pet = PetWindow(self.settings)
        self.chat = ChatWindow(self.settings)

        # 猫被单击 → 在猫旁边弹聊天面板
        self.pet.clicked.connect(self._open_chat)
        # 聊天说话状态 → 猫张嘴动画
        self.chat.talking.connect(self.pet.set_talking)

        self._build_tray()

        # 全局热键：切换猫显隐
        self.hotkey = HotKeyManager(app, config.HOTKEY, self._toggle_pet)
        self.hotkey.register()

        self.pet.show()

    # ── 托盘 ─────────────────────────────────────────────────────────
    def _build_tray(self):
        self.tray = QSystemTrayIcon(cat_sprite.make_icon(2), self.app)
        self.tray.setToolTip("赛博出气包 · 桌面损友猫")
        menu = QMenu()

        act_chat = QAction("打开聊天", menu)
        act_chat.triggered.connect(lambda: self._open_chat(*self.pet.cat_top_left_global()))
        menu.addAction(act_chat)

        act_toggle = QAction("显示 / 隐藏猫", menu)
        act_toggle.triggered.connect(self._toggle_pet)
        menu.addAction(act_toggle)

        menu.addSeparator()

        # 模式子菜单（单选）
        mode_menu = menu.addMenu("模式")
        self._mode_group = QActionGroup(menu)
        self._mode_group.setExclusive(True)
        cur_mode = self.settings.mode()
        for label in MODE_LABELS:
            a = QAction(label, mode_menu, checkable=True)
            a.setChecked(label == cur_mode)
            a.triggered.connect(lambda _=False, m=label: self._set_mode(m))
            self._mode_group.addAction(a)
            mode_menu.addAction(a)

        menu.addSeparator()

        act_clear = QAction("清空对话", menu)
        act_clear.triggered.connect(self.chat._on_clear)
        menu.addAction(act_clear)

        act_export = QAction("导出对话…", menu)
        act_export.triggered.connect(self.chat._on_export)
        menu.addAction(act_export)

        menu.addSeparator()

        # 开机自启（可勾选）
        self.act_autostart = QAction("开机自启", menu, checkable=True)
        self.act_autostart.setChecked(self.settings.autostart())
        self.act_autostart.setEnabled(autostart.is_supported())
        self.act_autostart.triggered.connect(self._toggle_autostart)
        menu.addAction(self.act_autostart)

        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        # 双击托盘也能开聊天
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_chat(*self.pet.cat_top_left_global())

    # ── 行为 ─────────────────────────────────────────────────────────
    def _open_chat(self, cat_x: int, cat_y: int):
        # 聊天面板尽量贴着猫的左上方弹出，避免跑出屏幕
        screen = self.pet.screen().availableGeometry()
        x = cat_x - self.chat.width() - 10
        if x < screen.left():
            x = cat_x + 10
        y = cat_y - self.chat.height() + 60
        if y < screen.top():
            y = screen.top() + 10
        if y + self.chat.height() > screen.bottom():
            y = screen.bottom() - self.chat.height()
        self.chat.show_near(x, y)

    def _toggle_pet(self):
        if self.pet.isVisible():
            self.pet.hide()
        else:
            self.pet.show()
            self.pet.raise_()

    def _set_mode(self, mode: str):
        self.settings.set_mode(mode)
        self.chat.mode_box.setCurrentText(mode)

    def _toggle_autostart(self, checked: bool):
        ok = autostart.set_enabled(checked)
        if ok:
            self.settings.set_autostart(checked)
        else:
            # 写注册表失败，回滚勾选状态
            self.act_autostart.setChecked(self.settings.autostart())

    def _quit(self):
        self.hotkey.unregister()
        self.chat.shutdown()
        self.tray.hide()
        self.app.quit()


def _check_api_key() -> bool:
    """没设 API key 时给个友好弹窗，让用户知道怎么办。返回是否继续。"""
    if config.has_api_key():
        return True
    box = QMessageBox()
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("还没设 API key")
    box.setText("没找到 ANTHROPIC_API_KEY，猫能出来但还不能说话。")
    box.setInformativeText(
        "设置方法（任选其一）：\n"
        "1. 在程序目录建 .env 文件，写一行：\n"
        "   ANTHROPIC_API_KEY=sk-ant-你的key\n"
        "2. 设环境变量 ANTHROPIC_API_KEY 后重启。\n\n"
        "key 去 platform.claude.com 申请。\n\n"
        "现在仍可让猫先待在桌面上，设好 key 重启即可聊天。"
    )
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()
    return True


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关窗不退出，托盘常驻

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("[warn] 系统托盘不可用，仍可用猫和热键。")

    _check_api_key()

    cat = CyberCatApp(app)
    # 持引用，别被 GC 掉
    app._cybercat = cat

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
