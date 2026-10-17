from src.core.constants import (
    COVER_MAX_EXT_LEN,
    DEFAULT_FORMAT,
    DEVICE_NAMES,
    MAX_BASE_RUNES,
    WINDOWS_RESERVED,
)


def sanitize(text):
    if not text:
        return ""
    chars = []
    for ch in text:
        code = ord(ch)
        if code == 0x00:
            continue
        if code < 0x20 or code == 0x7F:
            chars.append("_")
            continue
        if ch in WINDOWS_RESERVED:
            chars.append("_")
            continue
        chars.append(ch)

    out = "".join(chars).strip()
    out = out.rstrip(". ")
    if out == "":
        return ""
    if out.lower() in DEVICE_NAMES:
        out = "_" + out
    if len(out) > MAX_BASE_RUNES:
        out = out[:MAX_BASE_RUNES].rstrip(". ")
    return out


def build_base_name(title, artist, fallback):
    name = sanitize(title)
    if name == "":
        name = sanitize(fallback)
    if name == "":
        name = "unknown"

    singer = sanitize(artist)
    if singer == "" or singer == name:
        return name

    remain = MAX_BASE_RUNES - len(name) - 3
    if remain <= 0:
        return name
    if len(singer) > remain:
        singer = singer[:remain]
    truncated = singer.rstrip(". ")
    if truncated == "":
        return name
    return name + " - " + truncated


def normalize_ext(fmt):
    ext = (fmt or "").strip()
    if ext.startswith("."):
        ext = ext[1:]
    ext = ext.lower()
    ext = sanitize(ext).lstrip(".").rstrip(". ")
    if ext == "":
        return DEFAULT_FORMAT
    if len(ext) > COVER_MAX_EXT_LEN:
        ext = ext[:COVER_MAX_EXT_LEN]
    return ext
