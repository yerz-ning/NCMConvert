import os
import subprocess
import sys
import webbrowser

from src.core.constants import APP_NAME


def open_url(url):
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def open_directory(path):
    if not path or not os.path.isdir(path):
        raise OSError("目录不存在: %s" % path)
    if hasattr(os, "startfile"):
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


def fatal_error(message, title=APP_NAME):
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    try:
        sys.stderr.write(message + "\n")
    except Exception:
        pass
