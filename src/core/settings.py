import json
import os

from src.core.constants import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DEFAULT_SETTINGS,
    LEGACY_SETTINGS_KEYS,
)
from src.core.errors import NcmError


def config_path():
    base = (os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
            or os.path.expanduser("~"))
    return os.path.join(base, CONFIG_DIR_NAME, CONFIG_FILE_NAME)


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        handle = open(config_path(), "r", encoding="utf-8")
    except Exception:
        return settings
    try:
        data = json.load(handle)
    except Exception:
        data = None
    finally:
        try:
            handle.close()
        except Exception:
            pass

    if isinstance(data, dict):
        for legacy_key, current_key in LEGACY_SETTINGS_KEYS.items():
            if legacy_key in data and current_key not in data:
                settings[current_key] = bool(data[legacy_key])
        for key in DEFAULT_SETTINGS:
            if key in data:
                settings[key] = bool(data[key])
    return settings


def save_settings(settings):
    path = config_path()
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2, sort_keys=True)
    except (OSError, ValueError) as exc:
        raise NcmError("保存设置 %s 失败: %s" % (path, exc))
    return path
