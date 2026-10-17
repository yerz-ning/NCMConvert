import os
import sys

if not getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from src.core.constants import APP_NAME
from src.utils.system import fatal_error


def run_gui():
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY")
                                                 or os.environ.get("WAYLAND_DISPLAY")):
        fatal_error("未检测到图形环境，无法显示界面。请在桌面会话中运行本程序。")
        return 1

    try:
        import tkinter as tk

        from src.ui.app import GuiApp
    except Exception as exc:
        fatal_error("无法加载图形界面组件（tkinter），请确认 Python 安装时勾选了 tcl/tk。\n%s" % exc)
        return 1

    try:
        root = tk.Tk()
    except Exception as exc:
        fatal_error("启动图形界面失败: %s" % exc)
        return 1

    GuiApp(root)
    root.mainloop()
    return 0


def main():
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
