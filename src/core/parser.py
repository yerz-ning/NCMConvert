from src.core.constants import (
    COVER_JPEG_EXT,
    COVER_JPEG_MAGIC,
    COVER_PNG_EXT,
    COVER_PNG_MAGIC,
    GAP_AFTER_CRC,
    GAP_AFTER_MAGIC,
    MAGIC,
    MAX_BLOB_LEN,
)
from src.core.errors import NcmError


def read_exact(src, length, what):
    data = src.read(length)
    if data is None:
        data = b""
    if len(data) != length:
        raise NcmError("读取%s %d 字节失败（文件可能被截断）" % (what, length))
    return data


def read_uint32(src, what):
    return int.from_bytes(read_exact(src, 4, what), "little")


def parse_header(src):
    magic = read_exact(src, 8, "魔数")
    if magic != MAGIC:
        raise NcmError("魔数校验失败，期望 %r，实际 %r" % (MAGIC, magic))

    read_exact(src, GAP_AFTER_MAGIC, "2 字节 gap")

    key_len = read_uint32(src, "密钥段长度")
    if key_len == 0:
        raise NcmError("密钥段长度为 0，文件不合法")
    if key_len > MAX_BLOB_LEN:
        raise NcmError("密钥段长度 %d 超出上限 %d，文件可能已损坏" % (key_len, MAX_BLOB_LEN))
    key_blob = read_exact(src, key_len, "密钥段")

    meta_len = read_uint32(src, "元数据段长度")
    if meta_len > MAX_BLOB_LEN:
        raise NcmError("元数据段长度 %d 超出上限 %d，文件可能已损坏" % (meta_len, MAX_BLOB_LEN))
    meta_blob = read_exact(src, meta_len, "元数据段") if meta_len > 0 else b""

    read_exact(src, 4, "4 字节 CRC32")
    read_exact(src, GAP_AFTER_CRC, "5 字节 gap")

    cover_len = read_uint32(src, "封面段长度")
    if cover_len > MAX_BLOB_LEN:
        raise NcmError("封面段长度 %d 超出上限 %d，文件可能已损坏" % (cover_len, MAX_BLOB_LEN))
    cover_blob = read_exact(src, cover_len, "封面段") if cover_len > 0 else b""

    return {
        "key_blob": key_blob,
        "meta_blob": meta_blob,
        "cover_blob": cover_blob,
    }


def detect_image_ext(data):
    if len(data) >= len(COVER_JPEG_MAGIC) and data[:len(COVER_JPEG_MAGIC)] == COVER_JPEG_MAGIC:
        return COVER_JPEG_EXT
    if len(data) >= len(COVER_PNG_MAGIC) and data[:len(COVER_PNG_MAGIC)] == COVER_PNG_MAGIC:
        return COVER_PNG_EXT
    return ""
