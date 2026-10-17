import os
import shutil
import struct

from src.core.constants import (
    AUDIO_CHUNK_SIZE,
    COVER_EXT_MIME,
    EMBED_TEMP_SUFFIX,
    FLAC_BLOCK_HEADER_SIZE,
    FLAC_BLOCK_PICTURE,
    FLAC_BLOCK_TYPE_MASK,
    FLAC_LAST_BLOCK_FLAG,
    FLAC_MAGIC,
    FLAC_PICTURE_TYPE_FRONT_COVER,
    ID3_APIC_FRAME_ID,
    ID3_FLAG_EXTENDED_HEADER,
    ID3_FLAG_UNSYNCHRONISATION,
    ID3_FRAME_HEADER_SIZE,
    ID3_HEADER_SIZE,
    ID3_MAGIC,
    ID3_OLD_IMAGE_FRAME_ID,
    ID3_PICTURE_TYPE_FRONT_COVER,
    ID3_TAG_PADDING,
    ID3_TEXT_ENCODING,
    ID3_TEXT_FRAMES,
    ID3_VERSION_3,
    ID3_VERSION_4,
    JPEG_MARKER_PREFIX,
    JPEG_SOF_MARKERS,
    MAX_FLAC_BLOCK_LEN_BYTES,
    MAX_FLAC_BLOCK_SIZE,
    MAX_ID3_TAG_SIZE,
    MIME_JPEG,
    MIME_PNG,
    PNG_CHANNELS,
    PNG_IHDR_MIN_LEN,
    PNG_IHDR_OFFSET,
)
from src.core.errors import NcmError

UTF16_BOM_LE = b"\xff\xfe"
LATIN1_ENCODING = 0x00


def embed_cover(path, audio_ext, image_ext, image_bytes, meta):
    mime = COVER_EXT_MIME.get(image_ext)
    if not mime:
        raise NcmError("封面图片类型 %s 不支持内嵌" % (image_ext or "未知"))

    if audio_ext == "mp3":
        return _embed_id3v2(path, mime, image_bytes, meta)
    if audio_ext == "flac":
        return _embed_flac(path, mime, image_bytes)
    raise NcmError("音频格式 %s 暂不支持内嵌封面" % audio_ext)


def _syncsafe_encode(value):
    return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F))


def _syncsafe_decode(data):
    return ((data[0] & 0x7F) << 21) | ((data[1] & 0x7F) << 14) | \
           ((data[2] & 0x7F) << 7) | (data[3] & 0x7F)


def _remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _close_quietly(handle):
    try:
        handle.close()
    except OSError:
        pass


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError as exc:
        raise NcmError("读取音频文件 %s 大小失败: %s" % (path, exc))


def _rewrite(path, start, head_chunks):
    temp_path = path + EMBED_TEMP_SUFFIX
    try:
        source = open(path, "rb")
    except OSError as exc:
        raise NcmError("打开音频文件 %s 失败: %s" % (path, exc))

    try:
        try:
            source.seek(start)
        except (OSError, ValueError) as exc:
            raise NcmError("定位音频文件 %s 的数据区失败: %s" % (path, exc))
        try:
            target = open(temp_path, "wb")
        except OSError as exc:
            raise NcmError("创建临时文件 %s 失败: %s" % (temp_path, exc))
        try:
            for chunk in head_chunks:
                target.write(chunk)
            shutil.copyfileobj(source, target, AUDIO_CHUNK_SIZE)
            target.flush()
        except OSError as exc:
            _close_quietly(target)
            _remove(temp_path)
            raise NcmError("写入音频文件 %s 失败: %s" % (path, exc))
        try:
            target.close()
        except OSError as exc:
            _remove(temp_path)
            raise NcmError("关闭音频文件 %s 失败: %s" % (path, exc))
    finally:
        _close_quietly(source)

    try:
        os.replace(temp_path, path)
    except OSError as exc:
        _remove(temp_path)
        raise NcmError("替换音频文件 %s 失败: %s" % (path, exc))


def _text_payload(text):
    return bytes([ID3_TEXT_ENCODING]) + UTF16_BOM_LE + text.encode("utf-16-le")


def _frame(version, frame_id, payload):
    if version == ID3_VERSION_4:
        size = _syncsafe_encode(len(payload))
    else:
        size = struct.pack(">I", len(payload))
    return frame_id + size + b"\x00\x00" + payload


def _parse_frames(version, flags, body):
    if flags & (ID3_FLAG_UNSYNCHRONISATION | ID3_FLAG_EXTENDED_HEADER):
        return []
    frames = []
    pos = 0
    while pos + ID3_FRAME_HEADER_SIZE <= len(body):
        frame_id = body[pos:pos + 4]
        if not frame_id.strip(b"\x00"):
            break
        raw_size = body[pos + 4:pos + 8]
        if version == ID3_VERSION_4:
            size = _syncsafe_decode(raw_size)
        else:
            size = int.from_bytes(raw_size, "big")
        if size <= 0 or pos + ID3_FRAME_HEADER_SIZE + size > len(body):
            break
        frames.append((frame_id, body[pos:pos + ID3_FRAME_HEADER_SIZE + size]))
        pos += ID3_FRAME_HEADER_SIZE + size
    return frames


def _build_text_frames(version, frames, meta):
    existing = set(frame_id for frame_id, _ in frames)
    chunks = bytearray()
    for key, frame_id in ID3_TEXT_FRAMES:
        if frame_id in existing:
            continue
        text = meta.get(key) if isinstance(meta, dict) else ""
        if not isinstance(text, str) or not text.strip():
            continue
        chunks += _frame(version, frame_id, _text_payload(text.strip()))
    return bytes(chunks)


def _build_apic(version, mime, image):
    payload = bytearray()
    payload += bytes([LATIN1_ENCODING])
    payload += mime.encode("ascii")
    payload += b"\x00"
    payload += bytes([ID3_PICTURE_TYPE_FRONT_COVER])
    payload += b"\x00"
    payload += image
    return _frame(version, ID3_APIC_FRAME_ID, bytes(payload))


def _build_tag(version, frames, meta, mime, image):
    body = bytearray()
    for frame_id, raw in frames:
        if frame_id in (ID3_APIC_FRAME_ID, ID3_OLD_IMAGE_FRAME_ID):
            continue
        body += raw
    body += _build_text_frames(version, frames, meta)
    body += _build_apic(version, mime, image)
    header = ID3_MAGIC + bytes([version, 0, 0]) + _syncsafe_encode(len(body) + ID3_TAG_PADDING)
    return bytes(header) + bytes(body) + b"\x00" * ID3_TAG_PADDING


def _read_id3_state(path, total):
    version = ID3_VERSION_3
    frames = []
    audio_start = 0
    try:
        handle = open(path, "rb")
    except OSError as exc:
        raise NcmError("打开音频文件 %s 失败: %s" % (path, exc))
    try:
        header = handle.read(ID3_HEADER_SIZE)
        if len(header) == ID3_HEADER_SIZE and header[:3] == ID3_MAGIC:
            tag_size = _syncsafe_decode(header[6:10])
            if tag_size > MAX_ID3_TAG_SIZE or ID3_HEADER_SIZE + tag_size > total:
                raise NcmError("音频文件 %s 的 ID3v2 标签长度异常，已放弃内嵌" % path)
            if header[3] == ID3_VERSION_4:
                version = ID3_VERSION_4
            body = handle.read(tag_size)
            frames = _parse_frames(version, header[5], body)
            audio_start = ID3_HEADER_SIZE + tag_size
    finally:
        _close_quietly(handle)
    return version, frames, audio_start


def _embed_id3v2(path, mime, image, meta):
    total = _file_size(path)
    version, frames, audio_start = _read_id3_state(path, total)
    tag = _build_tag(version, frames, meta, mime, image)
    _rewrite(path, audio_start, [tag])
    return "已内嵌封面到 ID3v2 标签（%s，%d 字节）" % (mime, len(image))


def _build_picture_block(mime, image):
    width, height, depth = image_size(mime, image)
    mime_bytes = mime.encode("ascii")
    payload = bytearray()
    payload += struct.pack(">I", FLAC_PICTURE_TYPE_FRONT_COVER)
    payload += struct.pack(">I", len(mime_bytes)) + mime_bytes
    payload += struct.pack(">I", 0)
    payload += struct.pack(">IIII", width, height, depth, 0)
    payload += struct.pack(">I", len(image)) + image
    if len(payload) > MAX_FLAC_BLOCK_LEN_BYTES:
        raise NcmError("封面数据过大，无法写入 FLAC PICTURE 块")
    return bytes(payload)


def _read_flac_blocks(path):
    blocks = []
    audio_start = 0
    try:
        handle = open(path, "rb")
    except OSError as exc:
        raise NcmError("打开音频文件 %s 失败: %s" % (path, exc))
    try:
        if handle.read(len(FLAC_MAGIC)) != FLAC_MAGIC:
            raise NcmError("音频文件 %s 不是有效的 FLAC 文件" % path)
        while True:
            head = handle.read(FLAC_BLOCK_HEADER_SIZE)
            if len(head) != FLAC_BLOCK_HEADER_SIZE:
                raise NcmError("读取音频文件 %s 的 FLAC 元数据块头失败" % path)
            last = head[0] & FLAC_LAST_BLOCK_FLAG
            block_type = head[0] & FLAC_BLOCK_TYPE_MASK
            length = int.from_bytes(head[1:4], "big")
            if length > MAX_FLAC_BLOCK_SIZE:
                raise NcmError("音频文件 %s 的 FLAC 元数据块长度 %d 异常" % (path, length))
            data = handle.read(length)
            if len(data) != length:
                raise NcmError("读取音频文件 %s 的 FLAC 元数据块内容失败" % path)
            if block_type != FLAC_BLOCK_PICTURE:
                blocks.append((block_type, data))
            if last:
                break
        audio_start = handle.tell()
    finally:
        _close_quietly(handle)
    return blocks, audio_start


def _embed_flac(path, mime, image):
    blocks, audio_start = _read_flac_blocks(path)
    picture = _build_picture_block(mime, image)
    if blocks:
        blocks.insert(1, (FLAC_BLOCK_PICTURE, picture))
    else:
        blocks.append((FLAC_BLOCK_PICTURE, picture))

    meta_bytes = bytearray()
    last_index = len(blocks) - 1
    for index, (block_type, data) in enumerate(blocks):
        flag = FLAC_LAST_BLOCK_FLAG if index == last_index else 0
        meta_bytes += bytes([flag | block_type])
        meta_bytes += len(data).to_bytes(3, "big")
        meta_bytes += data

    _rewrite(path, audio_start, [FLAC_MAGIC + bytes(meta_bytes)])
    return "已内嵌封面到 FLAC PICTURE 块（%s，%d 字节）" % (mime, len(image))


def image_size(mime, image):
    if mime == MIME_PNG:
        return _png_size(image)
    if mime == MIME_JPEG:
        return _jpeg_size(image)
    return (0, 0, 0)


def _png_size(image):
    if len(image) < PNG_IHDR_MIN_LEN or image[PNG_IHDR_OFFSET - 4:PNG_IHDR_OFFSET] != b"IHDR":
        return (0, 0, 0)
    width = int.from_bytes(image[PNG_IHDR_OFFSET:PNG_IHDR_OFFSET + 4], "big")
    height = int.from_bytes(image[PNG_IHDR_OFFSET + 4:PNG_IHDR_OFFSET + 8], "big")
    bit_depth = image[PNG_IHDR_OFFSET + 8]
    color_type = image[PNG_IHDR_OFFSET + 9]
    channels = PNG_CHANNELS.get(color_type, 0)
    return (width, height, bit_depth * channels)


def _jpeg_size(image):
    total = len(image)
    index = 2
    while index + 10 <= total:
        if image[index] != JPEG_MARKER_PREFIX:
            index += 1
            continue
        marker = image[index + 1]
        if marker in (JPEG_MARKER_PREFIX, 0x01) or 0xD0 <= marker <= 0xD9:
            index += 2
            continue
        segment_len = int.from_bytes(image[index + 2:index + 4], "big")
        if segment_len < 2:
            break
        if marker in JPEG_SOF_MARKERS:
            height = int.from_bytes(image[index + 5:index + 7], "big")
            width = int.from_bytes(image[index + 7:index + 9], "big")
            precision = image[index + 4]
            components = image[index + 9]
            return (width, height, precision * components)
        index += 2 + segment_len
    return (0, 0, 0)
