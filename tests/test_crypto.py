import io
import unittest

from src.core import crypto
from src.core.constants import AUDIO_CHUNK_SIZE
from src.core.errors import NcmError
from tests import aes_ref
from tests.sample import audio_pattern, encrypt_audio

FIPS_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
FIPS_PLAIN = bytes.fromhex("00112233445566778899aabbccddeeff")
FIPS_CIPHER = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")


class AesTest(unittest.TestCase):
    def test_fips197_vector(self):
        self.assertEqual(aes_ref.encrypt(FIPS_KEY, FIPS_PLAIN), FIPS_CIPHER)
        self.assertEqual(crypto.aes_ecb_decrypt(FIPS_KEY, FIPS_CIPHER), FIPS_PLAIN)

    def test_sbox_matches_standard_table(self):
        self.assertEqual(bytes(crypto.aes_sbox()), aes_ref.sbox())

    def test_multi_block_roundtrip(self):
        key = bytes(range(16, 32))
        plain = bytes((i * 37 + 11) & 0xFF for i in range(16 * 9))
        cipher = aes_ref.encrypt(key, plain)
        self.assertEqual(crypto.aes_ecb_decrypt(key, cipher), plain)

    def test_length_not_multiple_of_block(self):
        with self.assertRaises(NcmError):
            crypto.aes_ecb_decrypt(FIPS_KEY, b"\x00" * 15)

    def test_empty_cipher(self):
        with self.assertRaises(NcmError):
            crypto.aes_ecb_decrypt(FIPS_KEY, b"")


class KeyBoxTest(unittest.TestCase):
    def test_box_is_permutation(self):
        # 因版权问题密钥不在此公开
        box = crypto.build_key_box(b"0123456789abcdef")
        self.assertEqual(sorted(box), list(range(256)))

    def test_empty_key_keeps_identity(self):
        self.assertEqual(crypto.build_key_box(b""), list(range(256)))

    def test_keystream_length(self):
        key = b"0123456789abcdef"
        stream = crypto.build_keystream(crypto.build_key_box(key))
        self.assertEqual(len(stream), 256)
        self.assertEqual(len(set(stream)) > 1, True)

    def test_chunk_keystream_is_periodic(self):
        key = b"0123456789abcdef"
        stream = crypto.build_keystream(crypto.build_key_box(key))
        for offset in (0, 1, 255, 256, 257, 4096):
            chunk = crypto.chunk_keystream(400, offset, stream)
            expected = bytes(stream[(offset + i) & 0xFF] for i in range(400))
            self.assertEqual(chunk, expected)

    def test_xor_bytes_matches_bytewise(self):
        data = bytes(range(256)) * 3
        key_data = bytes((i * 7 + 3) & 0xFF for i in range(len(data)))
        self.assertEqual(crypto.xor_bytes(data, key_data),
                         bytes(a ^ b for a, b in zip(data, key_data)))

    def test_decrypt_audio_stream_spans_chunks(self):
        key_material = bytes(range(1, 100))
        plain = audio_pattern(AUDIO_CHUNK_SIZE * 2 + 123)
        cipher = encrypt_audio(plain, key_material)
        stream = crypto.build_keystream(crypto.build_key_box(key_material))
        out = io.BytesIO()
        crypto.decrypt_audio_stream(io.BytesIO(cipher), out, stream)
        self.assertEqual(out.getvalue(), plain)


if __name__ == "__main__":
    unittest.main()
