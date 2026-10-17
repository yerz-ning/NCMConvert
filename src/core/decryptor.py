import os

from src.core import tagger
from src.core.constants import EMBED_AUDIO_FORMATS, NCM_SUFFIX
from src.core.crypto import build_key_box, build_keystream, decrypt_audio_stream
from src.core.errors import NcmError
from src.core.meta import decode_key_material, decode_meta
from src.core.naming import build_base_name, normalize_ext
from src.core.parser import detect_image_ext, parse_header


def same_path(left, right):
    try:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))
    except Exception:
        return os.path.normcase(left) == os.path.normcase(right)


def embed_cover_into(output_path, audio_ext, cover_blob, meta):
    image_ext = detect_image_ext(cover_blob)
    if not image_ext:
        return "封面数据不是 JPEG/PNG 图片，未内嵌", False
    if audio_ext not in EMBED_AUDIO_FORMATS:
        return "音频格式 %s 暂不支持内嵌封面，封面已丢弃" % audio_ext, False
    try:
        note = tagger.embed_cover(output_path, audio_ext, image_ext, cover_blob, meta)
    except NcmError as exc:
        return "封面内嵌失败: %s" % exc, False
    except (OSError, ValueError) as exc:
        return "封面内嵌失败: %s" % exc, False
    return note, True


def decrypt_file(input_path, out_dir="", embed_cover=True):
    try:
        src = open(input_path, "rb")
    except OSError as exc:
        raise NcmError("打开输入文件 %s 失败: %s" % (input_path, exc))

    try:
        try:
            container = parse_header(src)
        except NcmError as exc:
            raise NcmError("解析文件 %s 头部失败: %s" % (input_path, exc))

        try:
            key_material = decode_key_material(container["key_blob"])
        except NcmError as exc:
            raise NcmError("解析文件 %s 的 RC4 密钥失败: %s" % (input_path, exc))
        if len(key_material) == 0:
            raise NcmError("解析文件 %s 失败: RC4 密钥材料为空" % input_path)

        try:
            meta = decode_meta(container["meta_blob"])
        except NcmError as exc:
            raise NcmError("解析文件 %s 的元数据失败: %s" % (input_path, exc))

        target_dir = out_dir or os.path.dirname(os.path.abspath(input_path))
        try:
            if target_dir and not os.path.isdir(target_dir):
                os.makedirs(target_dir)
        except OSError as exc:
            raise NcmError("创建输出目录 %s 失败: %s" % (target_dir, exc))

        fallback = os.path.splitext(os.path.basename(input_path))[0]
        base = build_base_name(meta["musicName"], meta["artist"], fallback)
        ext = normalize_ext(meta["format"])

        output_path = os.path.join(target_dir, base + "." + ext)
        if same_path(output_path, input_path):
            output_path = os.path.join(target_dir, base + "_decoded." + ext)

        result = {
            "input": input_path,
            "output": output_path,
            "cover": "",
            "cover_embedded": False,
            "meta": meta,
        }

        stream = build_keystream(build_key_box(key_material))

        try:
            out = open(output_path, "wb")
        except OSError as exc:
            raise NcmError("创建输出文件 %s 失败: %s" % (output_path, exc))

        try:
            try:
                decrypt_audio_stream(src, out, stream)
            except NcmError:
                raise
            except OSError as exc:
                raise NcmError("解密音频到 %s 失败: %s" % (output_path, exc))
            try:
                out.flush()
            except OSError as exc:
                raise NcmError("写入输出文件 %s 失败: %s" % (output_path, exc))
        except NcmError:
            try:
                out.close()
            except OSError:
                pass
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
            raise
        try:
            out.close()
        except OSError as exc:
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
            raise NcmError("关闭输出文件 %s 失败: %s" % (output_path, exc))

        cover_blob = container["cover_blob"]
        if embed_cover and len(cover_blob) > 0:
            note, done = embed_cover_into(output_path, ext, cover_blob, meta)
            result["cover"] = note
            result["cover_embedded"] = done

        return result
    finally:
        try:
            src.close()
        except OSError:
            pass


def collect_inputs(input_path):
    if not os.path.exists(input_path):
        raise NcmError("访问输入路径 %s 失败: 路径不存在" % input_path)

    if not os.path.isdir(input_path):
        return [input_path]

    files = []
    for root, dirs, names in os.walk(input_path):
        dirs.sort()
        for name in sorted(names):
            if name.lower().endswith(NCM_SUFFIX):
                files.append(os.path.join(root, name))
    files.sort()
    return files


def process_files(files, out_dir="", on_total=None, on_start=None, on_success=None,
                  on_failure=None, on_progress=None, should_stop=None,
                  embed_cover=True):
    summary = {"total": len(files), "success": 0, "failed": 0, "canceled": False}

    if on_total is not None:
        on_total(len(files))

    for path in files:
        if should_stop is not None and should_stop():
            summary["canceled"] = True
            break
        if on_start is not None:
            on_start(path)
        try:
            info = decrypt_file(path, out_dir, embed_cover)
        except NcmError as exc:
            info = None
            summary["failed"] += 1
            if on_failure is not None:
                on_failure(path, exc)
        except Exception as exc:
            info = None
            summary["failed"] += 1
            if on_failure is not None:
                on_failure(path, exc)
        if info is not None:
            summary["success"] += 1
            if on_success is not None:
                on_success(info)

        if on_progress is not None:
            on_progress(summary["success"] + summary["failed"], summary["total"],
                        summary["success"], summary["failed"])

    return summary
