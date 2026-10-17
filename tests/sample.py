import base64
import json
import struct

from src.core.constants import (
    CORE_KEY,
    FLAC_MAGIC,
    GAP_AFTER_CRC,
    GAP_AFTER_MAGIC,
    ID3_MAGIC,
    ID3_VERSION_3,
    KEY_PREFIX,
    KEY_XOR,
    MAGIC,
    META_PREFIX_AES,
    META_PREFIX_RAW,
    META_XOR,
    MODIFY_KEY,
)
from src.core.crypto import build_key_box, build_keystream, chunk_keystream, xor_bytes
from src.core.meta import xor_each
from tests import aes_ref

ENCRYPT_CHUNK = 70000
FLAC_STREAMINFO_LEN = 34
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff\xe0"


def build_key_blob(key_material, pad=True):
    plain = KEY_PREFIX + key_material
    if pad:
        plain = aes_ref.pkcs7(plain)
    cipher = aes_ref.encrypt(CORE_KEY, plain)
    return xor_each(cipher, KEY_XOR)


def build_meta_blob(meta):
    plain = META_PREFIX_AES + json.dumps(meta, ensure_ascii=False).encode("utf-8")
    cipher = aes_ref.encrypt(MODIFY_KEY, aes_ref.pkcs7(plain))
    return xor_each(META_PREFIX_RAW + base64.b64encode(cipher), META_XOR)


def encrypt_audio(audio, key_material):
    box = build_key_box(key_material)
    stream = build_keystream(box)
    out = bytearray()
    offset = 0
    while offset < len(audio):
        piece = audio[offset:offset + ENCRYPT_CHUNK]
        out += xor_bytes(piece, chunk_keystream(len(piece), offset, stream))
        offset += len(piece)
    return bytes(out)


def build_ncm(key_material, meta=None, cover=b"", audio=b""):
    key_blob = build_key_blob(key_material)
    meta_blob = build_meta_blob(meta) if meta is not None else b""
    audio_cipher = encrypt_audio(audio, key_material)
    return b"".join([
        MAGIC,
        b"\x00" * GAP_AFTER_MAGIC,
        struct.pack("<I", len(key_blob)),
        key_blob,
        struct.pack("<I", len(meta_blob)),
        meta_blob,
        b"\x00" * 4,
        b"\x00" * GAP_AFTER_CRC,
        struct.pack("<I", len(cover)),
        cover,
        audio_cipher,
    ])


def audio_pattern(size):
    base = bytes(range(256))
    return (base * (size // 256 + 1))[:size]


def syncsafe(value):
    return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F,
                  (value >> 7) & 0x7F, value & 0x7F))


def png_cover(width, height, bit_depth=8, color_type=6, padding=32):
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    data = PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    data += struct.pack(">I", 0)
    return data + b"\x00" * padding


def jpeg_cover(width, height, components=3, padding=32):
    sof = struct.pack(">BHHB", 8, height, width, components)
    sof += bytes([1, 0x11, 0]) * components
    segment = b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof
    app0 = b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00"
    return JPEG_SIGNATURE[:2] + app0 + segment + b"\x00" * padding + b"\xff\xd9"


def flac_header(padding=0):
    head = FLAC_MAGIC + bytes([0x80]) + struct.pack(">I", FLAC_STREAMINFO_LEN)[1:]
    return head + b"\x00" * FLAC_STREAMINFO_LEN + b"\x00" * padding


def id3v2_text_frame(frame_id, text, encoding=0):
    if encoding == 1:
        payload = b"\x01\xff\xfe" + text.encode("utf-16-le")
    else:
        payload = b"\x00" + text.encode("latin-1")
    return frame_id + struct.pack(">I", len(payload)) + b"\x00\x00" + payload


def id3v2_tag(frames, padding=128, version=ID3_VERSION_3):
    body = b"".join(frames)
    header = ID3_MAGIC + bytes([version, 0, 0]) + syncsafe(len(body) + padding)
    return header + body + b"\x00" * padding
