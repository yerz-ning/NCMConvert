import base64
import json

from src.core.constants import (
    AES_BLOCK_SIZE,
    CORE_KEY,
    DEFAULT_FORMAT,
    KEY_PREFIX,
    KEY_XOR,
    META_PREFIX_AES,
    META_PREFIX_RAW,
    META_XOR,
    MODIFY_KEY,
)
from src.core.crypto import aes_ecb_decrypt
from src.core.errors import NcmError

_JSON_TRAILING_BYTES = (0x00, 0x20, 0x0D, 0x0A, 0x09)
_WHITESPACE = " \t\r\n\v\f"


def xor_each(data, mask):
    return bytes([b ^ mask for b in data])


def strip_pkcs7(data):
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= AES_BLOCK_SIZE and len(data) > pad and data[-pad:] == bytes([pad]) * pad:
        return data[:-pad]
    return data


def decode_key_material(key_blob):
    if len(key_blob) == 0:
        raise NcmError("密钥段为空")

    xored = xor_each(key_blob, KEY_XOR)
    if len(xored) % AES_BLOCK_SIZE != 0:
        raise NcmError("密钥密文长度 %d 不是 16 的整数倍" % len(xored))

    try:
        plain = aes_ecb_decrypt(CORE_KEY, xored)
    except NcmError as exc:
        raise NcmError("密钥段 AES 解密失败: %s" % exc)

    if len(plain) < len(KEY_PREFIX):
        raise NcmError("密钥明文长度 %d 小于前缀长度 %d" % (len(plain), len(KEY_PREFIX)))
    if plain[:len(KEY_PREFIX)] != KEY_PREFIX:
        raise NcmError("密钥前缀校验失败，实际前缀为 %r" % plain[:len(KEY_PREFIX)])

    return strip_pkcs7(plain[len(KEY_PREFIX):])


def _remove_whitespace(text):
    return "".join(ch for ch in text if ch not in _WHITESPACE)


def _decode_base64(text):
    try:
        return base64.b64decode(text, validate=False)
    except Exception as exc:
        raise NcmError("元数据 Base64 解码失败: %s" % exc)


def _trim_json_tail(data):
    end = len(data)
    while end > 0 and data[end - 1] in _JSON_TRAILING_BYTES:
        end -= 1
    data = data[:end]
    index = data.rfind(b"}")
    if index >= 0:
        data = data[:index + 1]
    return data


def _decode_artist_item(item):
    if isinstance(item, dict):
        name = item.get("name")
        if isinstance(name, str):
            return name.strip()
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        for element in item:
            if isinstance(element, str) and element.strip():
                return element.strip()
    return ""


def _decode_artist(raw):
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        names = []
        for item in raw:
            name = _decode_artist_item(item)
            if name:
                names.append(name)
        return "、".join(names)
    return ""


def _decode_album(raw):
    if isinstance(raw, str):
        return raw.strip()
    return ""


def decode_meta(meta_blob):
    if len(meta_blob) == 0:
        return {"format": DEFAULT_FORMAT, "musicName": "", "artist": "", "album": ""}

    xored = xor_each(meta_blob, META_XOR)
    if len(xored) < len(META_PREFIX_RAW):
        raise NcmError("元数据段长度 %d 小于前缀长度 %d" % (len(xored), len(META_PREFIX_RAW)))
    if xored[:len(META_PREFIX_RAW)] != META_PREFIX_RAW:
        raise NcmError("元数据前缀校验失败，实际前缀为 %r" % xored[:len(META_PREFIX_RAW)])

    try:
        text = xored[len(META_PREFIX_RAW):].decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise NcmError("元数据 Base64 解码失败: %s" % exc)

    encoded = _remove_whitespace(text)
    if encoded == "":
        raise NcmError("元数据 Base64 内容为空")

    cipher_text = _decode_base64(encoded)
    try:
        plain = aes_ecb_decrypt(MODIFY_KEY, cipher_text)
    except NcmError as exc:
        raise NcmError("元数据 AES 解密失败: %s" % exc)

    if len(plain) < len(META_PREFIX_AES):
        raise NcmError("元数据明文长度 %d 小于前缀长度 %d" % (len(plain), len(META_PREFIX_AES)))
    if plain[:len(META_PREFIX_AES)] != META_PREFIX_AES:
        raise NcmError("元数据前缀校验失败，实际前缀为 %r" % plain[:len(META_PREFIX_AES)])

    json_bytes = _trim_json_tail(plain[len(META_PREFIX_AES):])
    if len(json_bytes) == 0:
        raise NcmError("元数据 JSON 内容为空")

    try:
        raw = json.loads(json_bytes.decode("utf-8", "strict"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise NcmError("元数据 JSON 解析失败: %s" % exc)

    if not isinstance(raw, dict):
        raise NcmError("元数据 JSON 解析失败: 顶层不是对象")

    fmt = raw.get("format")
    fmt = fmt.strip() if isinstance(fmt, str) else ""
    name = raw.get("musicName")
    name = name.strip() if isinstance(name, str) else ""

    return {
        "format": fmt or DEFAULT_FORMAT,
        "musicName": name,
        "artist": _decode_artist(raw.get("artist")),
        "album": _decode_album(raw.get("album")),
    }
