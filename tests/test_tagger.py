import os
import shutil
import struct
import tempfile
import unittest

from src.core import tagger
from src.core.constants import (
    EMBED_TEMP_SUFFIX,
    FLAC_BLOCK_PICTURE,
    FLAC_BLOCK_STREAMINFO,
    FLAC_BLOCK_TYPE_MASK,
    FLAC_LAST_BLOCK_FLAG,
    FLAC_MAGIC,
    ID3_APIC_FRAME_ID,
    ID3_MAGIC,
    MIME_JPEG,
    MIME_PNG,
)
from src.core.errors import NcmError
from tests import sample

META = {"musicName": "新歌名", "artist": "新歌手", "album": "新专辑"}
PNG = sample.png_cover(320, 240)
JPEG = sample.jpeg_cover(640, 480)


def flac_blocks(data):
    blocks = []
    pos = len(FLAC_MAGIC)
    while True:
        head = data[pos]
        length = int.from_bytes(data[pos + 1:pos + 4], "big")
        body = data[pos + 4:pos + 4 + length]
        blocks.append((head & FLAC_BLOCK_TYPE_MASK, head & FLAC_LAST_BLOCK_FLAG, body))
        pos += 4 + length
        if head & FLAC_LAST_BLOCK_FLAG:
            break
    return blocks, data[pos:]


class SyncsafeTest(unittest.TestCase):
    def test_round_trip(self):
        for value in (0, 1, 127, 128, 8191, 16384, 2097151, 262144, 268435455):
            self.assertEqual(tagger._syncsafe_decode(tagger._syncsafe_encode(value)), value)

    def test_high_bits_cleared(self):
        data = tagger._syncsafe_encode(0x0FFFFFFF)
        self.assertEqual(len(data), 4)
        for byte in data:
            self.assertTrue(byte < 0x80)


class ImageSizeTest(unittest.TestCase):
    def test_png_size(self):
        self.assertEqual(tagger.image_size(MIME_PNG, sample.png_cover(320, 240)), (320, 240, 32))

    def test_png_gray_size(self):
        cover = sample.png_cover(16, 8, bit_depth=8, color_type=0)
        self.assertEqual(tagger.image_size(MIME_PNG, cover), (16, 8, 8))

    def test_jpeg_size(self):
        self.assertEqual(tagger.image_size(MIME_JPEG, sample.jpeg_cover(640, 480)), (640, 480, 24))

    def test_jpeg_gray_size(self):
        cover = sample.jpeg_cover(64, 32, components=1)
        self.assertEqual(tagger.image_size(MIME_JPEG, cover), (64, 32, 8))

    def test_broken_images(self):
        self.assertEqual(tagger.image_size(MIME_PNG, b"\x89PNG"), (0, 0, 0))
        self.assertEqual(tagger.image_size(MIME_JPEG, b"\xff\xd8\xff"), (0, 0, 0))
        self.assertEqual(tagger.image_size(MIME_PNG, b""), (0, 0, 0))

    def test_unknown_mime(self):
        self.assertEqual(tagger.image_size("image/bmp", b"BM"), (0, 0, 0))


class EmbedCoverArgumentsTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")
        self.path = os.path.join(self.work, "out.mp3")
        with open(self.path, "wb") as handle:
            handle.write(sample.audio_pattern(512))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_unsupported_image_type(self):
        with self.assertRaises(NcmError):
            tagger.embed_cover(self.path, "mp3", "bmp", b"BM", META)

    def test_unsupported_audio_format(self):
        with self.assertRaises(NcmError):
            tagger.embed_cover(self.path, "wav", "png", PNG, META)

    def test_missing_file(self):
        with self.assertRaises(NcmError):
            tagger.embed_cover(os.path.join(self.work, "none.mp3"), "mp3", "png", PNG, META)


class Id3EmbedTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")
        self.audio = sample.audio_pattern(1024)
        self.path = os.path.join(self.work, "out.mp3")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)
        return data

    def _read(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_creates_tag_when_absent(self):
        self._write(self.audio)
        note = tagger.embed_cover(self.path, "mp3", "png", PNG, META)
        self.assertIn(MIME_PNG, note)
        data = self._read()
        self.assertTrue(data.startswith(ID3_MAGIC))
        self.assertEqual(data[3], 3)
        self.assertTrue(data.endswith(self.audio))
        self.assertIn(ID3_APIC_FRAME_ID, data)
        self.assertIn(PNG, data)
        self.assertIn(MIME_PNG.encode("ascii"), data)

    def test_metadata_written_as_text_frames(self):
        self._write(self.audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG, META)
        data = self._read()
        self.assertIn(b"TIT2", data)
        self.assertIn(b"TPE1", data)
        self.assertIn(b"TALB", data)
        self.assertIn("新歌名".encode("utf-16-le"), data)

    def test_no_text_frame_for_empty_metadata(self):
        self._write(self.audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG,
                           {"musicName": "", "artist": "  ", "album": None})
        data = self._read()
        self.assertNotIn(b"TIT2", data)
        self.assertIn(ID3_APIC_FRAME_ID, data)

    def test_existing_frames_preserved(self):
        frames = [sample.id3v2_text_frame(b"TIT2", "Old Title"),
                  sample.id3v2_text_frame(b"TCON", "Rock")]
        audio = sample.id3v2_tag(frames) + self.audio
        self._write(audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG, META)

        data = self._read()
        self.assertIn(b"Old Title", data)
        self.assertIn(b"Rock", data)
        self.assertEqual(data.count(b"TIT2"), 1)
        self.assertTrue(data.endswith(self.audio))

    def test_cover_replaced_on_second_run(self):
        self._write(self.audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG, META)
        tagger.embed_cover(self.path, "mp3", "jpg", JPEG, META)
        data = self._read()
        self.assertEqual(data.count(ID3_APIC_FRAME_ID), 1)
        self.assertIn(JPEG, data)
        self.assertNotIn(PNG, data)
        self.assertIn(MIME_JPEG.encode("ascii"), data)

    def test_version_4_tag_keeps_version(self):
        audio = sample.id3v2_tag([sample.id3v2_text_frame(b"TIT2", "V4")], version=4) + self.audio
        self._write(audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG, META)
        data = self._read()
        self.assertEqual(data[3], 4)
        self.assertIn(ID3_APIC_FRAME_ID, data)
        self.assertTrue(data.endswith(self.audio))

    def test_oversized_tag_rejected(self):
        header = ID3_MAGIC + bytes([3, 0, 0]) + sample.syncsafe(0x0FFFFFFF)
        self._write(header + self.audio)
        with self.assertRaises(NcmError):
            tagger.embed_cover(self.path, "mp3", "png", PNG, META)

    def test_no_temp_file_left(self):
        self._write(self.audio)
        tagger.embed_cover(self.path, "mp3", "png", PNG, META)
        self.assertEqual(sorted(os.listdir(self.work)), ["out.mp3"])


class FlacEmbedTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")
        self.audio = sample.audio_pattern(1024)
        self.path = os.path.join(self.work, "out.flac")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)
        return data

    def _read(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_picture_block_inserted_after_streaminfo(self):
        self._write(sample.flac_header() + self.audio)
        note = tagger.embed_cover(self.path, "flac", "png", PNG, META)
        self.assertIn(MIME_PNG, note)

        data = self._read()
        blocks, rest = flac_blocks(data)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][0], FLAC_BLOCK_STREAMINFO)
        self.assertEqual(blocks[0][1], 0)
        self.assertEqual(blocks[1][0], FLAC_BLOCK_PICTURE)
        self.assertEqual(blocks[1][1], FLAC_LAST_BLOCK_FLAG)
        self.assertIn(PNG, blocks[1][2])
        self.assertIn(MIME_PNG.encode("ascii"), blocks[1][2])
        self.assertIn(struct.pack(">II", 320, 240), blocks[1][2])
        self.assertEqual(rest, self.audio)

    def test_existing_picture_replaced(self):
        self._write(sample.flac_header() + self.audio)
        tagger.embed_cover(self.path, "flac", "png", PNG, META)
        tagger.embed_cover(self.path, "flac", "jpg", JPEG, META)

        blocks, rest = flac_blocks(self._read())
        self.assertEqual([block[0] for block in blocks],
                         [FLAC_BLOCK_STREAMINFO, FLAC_BLOCK_PICTURE])
        self.assertIn(JPEG, blocks[1][2])
        self.assertNotIn(PNG, blocks[1][2])
        self.assertEqual(rest, self.audio)

    def test_other_blocks_preserved(self):
        vorbis = b"\x00" * 40
        header = (FLAC_MAGIC + bytes([0x00]) + struct.pack(">I", 34)[1:] + b"\x00" * 34
                  + bytes([0x04]) + struct.pack(">I", len(vorbis))[1:] + vorbis
                  + bytes([0x81]) + struct.pack(">I", 0)[1:])
        self._write(header + self.audio)
        tagger.embed_cover(self.path, "flac", "png", PNG, META)

        blocks, rest = flac_blocks(self._read())
        self.assertEqual([block[0] for block in blocks],
                         [FLAC_BLOCK_STREAMINFO, FLAC_BLOCK_PICTURE, 4, 1])
        self.assertEqual(rest, self.audio)

    def test_non_flac_file_rejected(self):
        self._write(self.audio)
        with self.assertRaises(NcmError):
            tagger.embed_cover(self.path, "flac", "png", PNG, META)

    def test_truncated_file_rejected(self):
        self._write(FLAC_MAGIC + bytes([0x80]) + b"\x00\x00\x22")
        with self.assertRaises(NcmError):
            tagger.embed_cover(self.path, "flac", "png", PNG, META)

    def test_no_temp_file_left(self):
        self._write(sample.flac_header() + self.audio)
        tagger.embed_cover(self.path, "flac", "png", PNG, META)
        self.assertEqual(sorted(os.listdir(self.work)), ["out.flac"])

    def test_embed_temp_suffix_constant_used(self):
        self._write(sample.flac_header() + self.audio)
        tagger.embed_cover(self.path, "flac", "png", PNG, META)
        self.assertFalse(os.path.exists(self.path + EMBED_TEMP_SUFFIX))


if __name__ == "__main__":
    unittest.main()
