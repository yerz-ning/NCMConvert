import io
import unittest

from src.core.errors import NcmError
from src.core.parser import detect_image_ext, parse_header
from tests.sample import build_ncm

KEY_MATERIAL = bytes(range(1, 100))
META = {"format": "flac", "musicName": "曲目", "artist": "歌手", "album": "专辑"}
COVER = b"\xff\xd8\xff\xe0" + b"\x00" * 32
AUDIO = bytes(range(200))


class ParseHeaderTest(unittest.TestCase):
    def test_reads_all_segments(self):
        blob = build_ncm(KEY_MATERIAL, META, COVER, AUDIO)
        src = io.BytesIO(blob)
        header = parse_header(src)
        self.assertEqual(len(header["key_blob"]), 128)
        self.assertEqual(len(header["meta_blob"]), 150)
        self.assertEqual(header["cover_blob"], COVER)
        rest = src.read()
        self.assertEqual(len(rest), len(AUDIO))

    def test_empty_meta_and_cover(self):
        blob = build_ncm(KEY_MATERIAL, None, b"", AUDIO)
        src = io.BytesIO(blob)
        header = parse_header(src)
        self.assertEqual(header["meta_blob"], b"")
        self.assertEqual(header["cover_blob"], b"")
        self.assertEqual(len(src.read()), len(AUDIO))

    def test_bad_magic(self):
        blob = b"XXXXXXXX" + build_ncm(KEY_MATERIAL, META, b"", AUDIO)[8:]
        with self.assertRaises(NcmError):
            parse_header(io.BytesIO(blob))

    def test_truncated_file(self):
        blob = build_ncm(KEY_MATERIAL, META, b"", AUDIO)[:40]
        with self.assertRaises(NcmError):
            parse_header(io.BytesIO(blob))

    def test_zero_key_length(self):
        blob = b"CTENFDAM" + b"\x00" * 2 + b"\x00" * 4
        with self.assertRaises(NcmError):
            parse_header(io.BytesIO(blob))

    def test_oversized_meta_length(self):
        blob = b"CTENFDAM" + b"\x00" * 2 + b"\x10\x00\x00\x00" + b"\x00" * 16
        blob += b"\xff\xff\xff\x7f"
        with self.assertRaises(NcmError):
            parse_header(io.BytesIO(blob))


class DetectImageTest(unittest.TestCase):
    def test_jpeg(self):
        self.assertEqual(detect_image_ext(b"\xff\xd8\xff\xe0\x00\x10"), "jpg")

    def test_png(self):
        self.assertEqual(detect_image_ext(b"\x89PNG\r\n\x1a\n"), "png")

    def test_unknown(self):
        self.assertEqual(detect_image_ext(b"GIF89a"), "")
        self.assertEqual(detect_image_ext(b""), "")


if __name__ == "__main__":
    unittest.main()
