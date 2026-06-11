# -*- coding: utf-8 -*-
"""
Windows 全局热键：用 ctypes 调 RegisterHotKey + QAbstractNativeEventFilter
捕获 WM_HOTKEY，无第三方依赖。

注册失败（热键被占用 / 非 Windows / 无权限）一律优雅降级——只记一句日志、
回调失效，绝不让程序崩。外部仍可用托盘和点击操作。

用法：
    mgr = HotKeyManager(app, "Ctrl+Alt+C", on_trigger)
    mgr.register()
    ...
    mgr.unregister()   # 退出前
"""

import sys
import ctypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MOD_NAMES = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN, "meta": MOD_WIN,
}

# 常用功能键名 → 虚拟键码
_VK_NAMES = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A,
    "f12": 0x7B,
}

_HOTKEY_ID = 1


def parse_hotkey(spec: str):
    """
    把 "Ctrl+Alt+C" 解析成 (modifiers, vk)。解析失败返回 None。
    """
    if not spec:
        return None
    mods = 0
    vk = None
    for part in spec.split("+"):
        key = part.strip().lower()
        if not key:
            continue
        if key in _MOD_NAMES:
            mods |= _MOD_NAMES[key]
        elif key in _VK_NAMES:
            vk = _VK_NAMES[key]
        elif len(key) == 1 and (key.isalpha() or key.isdigit()):
            vk = ord(key.upper())
        else:
            return None
    if vk is None or mods == 0:
        return None
    return mods | MOD_NOREPEAT, vk


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class _HotKeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id, callback):
        super().__init__()
        self._id = hotkey_id
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            if event_type == b"windows_generic_MSG":
                msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
                if msg.message == WM_HOTKEY and int(msg.wParam or 0) == self._id:
                    self._callback()
        except Exception:
            pass
        return False, 0


class HotKeyManager:
    def __init__(self, app, spec: str, callback):
        self._app = app
        self._spec = spec
        self._callback = callback
        self._filter = None
        self._registered = False

    def register(self) -> bool:
        """注册全局热键，成功返回 True，失败返回 False（已降级）。"""
        if sys.platform != "win32":
            print(f"[hotkey] 非 Windows，跳过全局热键（{self._spec}）。")
            return False
        parsed = parse_hotkey(self._spec)
        if parsed is None:
            print(f"[hotkey] 热键格式无法解析：{self._spec!r}，已跳过。")
            return False
        mods, vk = parsed
        try:
            ok = ctypes.windll.user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk)
        except Exception as e:
            print(f"[hotkey] 注册异常：{e}，已降级。")
            return False
        if not ok:
            print(f"[hotkey] 热键 {self._spec} 可能已被占用，已降级（可改 CYBERCAT_HOTKEY）。")
            return False
        self._filter = _HotKeyFilter(_HOTKEY_ID, self._callback)
        self._app.installNativeEventFilter(self._filter)
        self._registered = True
        print(f"[hotkey] 已注册全局热键 {self._spec}。")
        return True

    def unregister(self):
        if not self._registered:
            return
        try:
            if self._filter is not None:
                self._app.removeNativeEventFilter(self._filter)
            ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
        except Exception:
            pass
        self._registered = False
        self._filter = None
