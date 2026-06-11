# -*- coding: utf-8 -*-
"""
Windows 开机自启：写 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。

区分两种运行方式：
- 打包成 exe（sys.frozen）：直接用 sys.executable。
- 脚本运行：用 pythonw.exe（无控制台）跑 main.py 的绝对路径。

非 Windows 或出错时所有函数都安全返回，不抛异常。
"""

import os
import sys

try:
    import winreg
except ImportError:  # 非 Windows
    winreg = None

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "CyberStressBagCat"


def _launch_command() -> str:
    """构造写进注册表的启动命令。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # 脚本模式：优先用同目录的 pythonw.exe（不弹黑窗）
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    return f'"{exe}" "{main_py}"'


def is_supported() -> bool:
    return winreg is not None and sys.platform == "win32"


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except OSError:
        return False


def enable() -> bool:
    """开启自启，成功返回 True。"""
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        return True
    except OSError as e:
        print(f"[autostart] 开启自启失败：{e}")
        return False


def disable() -> bool:
    """关闭自启，成功（或本来就没有）返回 True。"""
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        print(f"[autostart] 关闭自启失败：{e}")
        return False


def set_enabled(on: bool) -> bool:
    return enable() if on else disable()
