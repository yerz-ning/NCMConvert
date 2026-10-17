import unittest

from src.core.errors import NcmError
from src.core.meta import decode_key_material, decode_meta, strip_pkcs7, xor_each
from src.core.constants import DEFAULT_FORMAT, KEY_PREFIX, META_XOR
from tests.sample import build_key_blob, build_meta_blob

KEY_MATERIAL = bytes(range(1, 100))


class KeyMaterialTest(unittest.TestCase):
    def test_strips_pkcs7_padding(self):
        material = decode_key_material(build_key_blob(KEY_MATERIAL))
        self.assertEqual(material, KEY_MATERIAL)

    def test_keeps_material_without_padding(self):
        material = bytes(range(1, 16))
        material = material[:-1] + b"\xff"
        self.assertEqual(decode_key_material(build_key_blob(material)),
                         material)

    def test_strip_pkcs7_directly(self):
        self.assertEqual(strip_pkcs7(b"AAAA" + bytes([12]) * 12), b"AAAA")
        self.assertEqual(strip_pkcs7(b"AAAA"), b"AAAA")
        self.assertEqual(strip_pkcs7(bytes([16]) * 16), bytes([16]) * 16)

    def test_bad_prefix(self):
        blob = build_key_blob(KEY_MATERIAL)
        blob = bytes([blob[0] ^ 0x01]) + blob[1:]
        with self.assertRaises(NcmError):
            decode_key_material(blob)

    def test_empty_blob(self):
        with self.assertRaises(NcmError):
            decode_key_material(b"")


class DecodeMetaTest(unittest.TestCase):
    def test_empty_blob_returns_defaults(self):
        self.assertEqual(decode_meta(b""), {"format": DEFAULT_FORMAT, "musicName": "",
                                            "artist": "", "album": ""})

    def test_artist_as_string(self):
        blob = build_meta_blob({"format": "mp3", "musicName": "稻香", "artist": "卡罗尔",
                                "album": "专辑"})
        meta = decode_meta(blob)
        self.assertEqual(meta["format"], "mp3")
        self.assertEqual(meta["musicName"], "稻香")
        self.assertEqual(meta["artist"], "卡罗尔")
        self.assertEqual(meta["album"], "专辑")

    def test_artist_as_object_list(self):
        blob = build_meta_blob({"format": "flac", "musicName": "曲目",
                                "artist": [{"id": 1, "name": "张三"}, {"id": 2, "name": "李四"}]})
        meta = decode_meta(blob)
        self.assertEqual(meta["format"], "flac")
        self.assertEqual(meta["artist"], "张三、李四")

    def test_artist_as_nested_list(self):
        blob = build_meta_blob({"musicName": "曲目", "artist": [["卡罗尔", "59235151"]]})
        meta = decode_meta(blob)
        self.assertEqual(meta["artist"], "卡罗尔")
        self.assertEqual(meta["format"], DEFAULT_FORMAT)

    def test_bad_prefix(self):
        with self.assertRaises(NcmError):
            decode_meta(xor_each(b"A" * 40, META_XOR))

    def test_truncated_prefix(self):
        with self.assertRaises(NcmError):
            decode_meta(xor_each(b"abc", META_XOR))

    def test_key_prefix_constant_matches_spec(self):
        self.assertEqual(KEY_PREFIX, b"neteasecloudmusic")


if __name__ == "__main__":
    unittest.main()
