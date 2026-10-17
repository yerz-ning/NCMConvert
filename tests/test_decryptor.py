import os
import shutil
import tempfile
import unittest

from src.core.constants import (
    AUDIO_CHUNK_SIZE,
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
from src.core.decryptor import collect_inputs, decrypt_file, process_files, same_path
from src.core.errors import NcmError
from tests import sample
from tests.sample import audio_pattern, build_ncm, flac_header, jpeg_cover, png_cover

KEY_MATERIAL = bytes(range(1, 100))
META_MP3 = {"format": "mp3", "musicName": "曲目名",
            "artist": [{"id": 1, "name": "歌手名"}], "album": "专辑"}
META_FLAC = dict(META_MP3, format="flac")
COVER = png_cover(320, 240)
JPEG = jpeg_cover(200, 100)
AUDIO = audio_pattern(AUDIO_CHUNK_SIZE * 2 + 500)
FLAC_AUDIO = flac_header() + AUDIO


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


class DecryptFileTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self, name, data):
        path = os.path.join(self.work, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def _names(self):
        return sorted(os.listdir(self.work))

    def test_audio_kept_and_cover_embedded_for_mp3(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, COVER, AUDIO))
        info = decrypt_file(source, self.work, True)

        expected = os.path.join(self.work, "曲目名 - 歌手名.mp3")
        self.assertEqual(info["output"], expected)
        self.assertTrue(info["cover_embedded"])
        self.assertEqual(info["cover"],
                         "已内嵌封面到 ID3v2 标签（%s，%d 字节）" % (MIME_PNG, len(COVER)))

        data = read_bytes(expected)
        self.assertTrue(data.startswith(ID3_MAGIC))
        self.assertTrue(data.endswith(AUDIO))
        self.assertIn(ID3_APIC_FRAME_ID, data)
        self.assertIn(COVER, data)
        self.assertIn(MIME_PNG.encode("ascii"), data)

    def test_cover_is_not_written_as_image_file(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, JPEG, AUDIO))
        decrypt_file(source, self.work, True)
        self.assertEqual(self._names(), ["input.ncm", "曲目名 - 歌手名.mp3"])
        self.assertEqual([name for name in self._names()
                          if name.lower().endswith((".jpg", ".jpeg", ".png"))], [])

    def test_cover_embedded_for_flac(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_FLAC, JPEG, FLAC_AUDIO))
        info = decrypt_file(source, self.work, True)

        expected = os.path.join(self.work, "曲目名 - 歌手名.flac")
        self.assertEqual(info["output"], expected)
        self.assertTrue(info["cover_embedded"])

        data = read_bytes(expected)
        self.assertTrue(data.startswith(FLAC_MAGIC))
        self.assertTrue(data.endswith(AUDIO))
        self.assertEqual(data[4] & FLAC_BLOCK_TYPE_MASK, FLAC_BLOCK_STREAMINFO)
        self.assertEqual(data[4] & FLAC_LAST_BLOCK_FLAG, 0)

        picture_offset = 4 + 4 + sample.FLAC_STREAMINFO_LEN
        self.assertEqual(data[picture_offset] & FLAC_BLOCK_TYPE_MASK, FLAC_BLOCK_PICTURE)
        self.assertEqual(data[picture_offset] & FLAC_LAST_BLOCK_FLAG, FLAC_LAST_BLOCK_FLAG)
        length = int.from_bytes(data[picture_offset + 1:picture_offset + 4], "big")
        picture = data[picture_offset + 4:picture_offset + 4 + length]
        self.assertIn(JPEG, picture)
        self.assertIn(MIME_JPEG.encode("ascii"), picture)

    def test_cover_dropped_when_disabled(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, COVER, AUDIO))
        info = decrypt_file(source, self.work, False)
        self.assertEqual(info["cover"], "")
        self.assertFalse(info["cover_embedded"])
        self.assertEqual(read_bytes(info["output"]), AUDIO)
        self.assertEqual(self._names(), ["input.ncm", "曲目名 - 歌手名.mp3"])

    def test_no_cover_section_leaves_audio_untouched(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO))
        info = decrypt_file(source, self.work, True)
        self.assertEqual(info["cover"], "")
        self.assertFalse(info["cover_embedded"])
        self.assertEqual(read_bytes(info["output"]), AUDIO)

    def test_unsupported_audio_format_keeps_audio(self):
        meta = dict(META_MP3, format="wav")
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, meta, COVER, AUDIO))
        info = decrypt_file(source, self.work, True)
        self.assertTrue(info["output"].endswith(".wav"))
        self.assertFalse(info["cover_embedded"])
        self.assertIn("暂不支持", info["cover"])
        self.assertEqual(read_bytes(info["output"]), AUDIO)

    def test_existing_id3_frames_preserved(self):
        frames = [sample.id3v2_text_frame(b"TIT2", "Old Title"),
                  sample.id3v2_text_frame(b"TALB", "Old Album")]
        audio = sample.id3v2_tag(frames) + AUDIO
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, COVER, audio))
        info = decrypt_file(source, self.work, True)

        data = read_bytes(info["output"])
        self.assertIn(b"Old Title", data)
        self.assertIn(b"Old Album", data)
        self.assertIn(ID3_APIC_FRAME_ID, data)
        self.assertIn(COVER, data)
        self.assertTrue(data.endswith(AUDIO))

    def test_repeated_run_keeps_single_cover(self):
        audio = sample.id3v2_tag([sample.id3v2_text_frame(b"TIT2", "Old Title")]) + AUDIO
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_MP3, COVER, audio))
        info = decrypt_file(source, self.work, True)
        again = decrypt_file(source, self.work, True)
        self.assertEqual(info["output"], again["output"])
        self.assertEqual(read_bytes(info["output"]).count(ID3_APIC_FRAME_ID), 1)

    def test_no_temp_file_left_behind(self):
        source = self._write("input.ncm", build_ncm(KEY_MATERIAL, META_FLAC, COVER, FLAC_AUDIO))
        decrypt_file(source, self.work, True)
        self.assertEqual([name for name in self._names()
                          if name.endswith(EMBED_TEMP_SUFFIX)], [])

    def test_missing_meta_falls_back_to_input_name(self):
        source = self._write("song.ncm", build_ncm(KEY_MATERIAL, None, b"", AUDIO))
        info = decrypt_file(source, self.work, True)
        self.assertEqual(os.path.basename(info["output"]), "song.mp3")
        self.assertEqual(read_bytes(info["output"]), AUDIO)

    def test_output_directory_created(self):
        source = self._write("song.ncm", build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO))
        target = os.path.join(self.work, "deep", "nested")
        info = decrypt_file(source, target, True)
        self.assertEqual(os.path.dirname(info["output"]), target)

    def test_corrupted_file_raises(self):
        source = self._write("broken.ncm", b"NOTNCM" + b"\x00" * 64)
        with self.assertRaises(NcmError):
            decrypt_file(source, self.work, True)

    def test_truncated_file_raises(self):
        source = self._write("short.ncm", build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO)[:60])
        with self.assertRaises(NcmError):
            decrypt_file(source, self.work, True)

    def test_no_leftover_after_failure(self):
        source = self._write("broken.ncm", b"NOTNCM" + b"\x00" * 64)
        with self.assertRaises(NcmError):
            decrypt_file(source, self.work, True)
        self.assertEqual(os.listdir(self.work), ["broken.ncm"])

    def test_same_path_helper(self):
        path = os.path.join(self.work, "a.ncm")
        self.assertTrue(same_path(path, os.path.join(self.work, "a.ncm")))
        self.assertFalse(same_path(path, os.path.join(self.work, "b.ncm")))


class CollectInputsTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_recursive_and_sorted(self):
        os.makedirs(os.path.join(self.work, "sub"))
        for name in ("b.ncm", "a.ncm", "note.txt"):
            with open(os.path.join(self.work, name), "wb") as handle:
                handle.write(b"x")
        with open(os.path.join(self.work, "sub", "c.NCM"), "wb") as handle:
            handle.write(b"x")
        found = collect_inputs(self.work)
        self.assertEqual([os.path.basename(p) for p in found], ["a.ncm", "b.ncm", "c.NCM"])

    def test_single_file(self):
        path = os.path.join(self.work, "only.ncm")
        with open(path, "wb") as handle:
            handle.write(b"x")
        self.assertEqual(collect_inputs(path), [path])

    def test_missing_path(self):
        with self.assertRaises(NcmError):
            collect_inputs(os.path.join(self.work, "nope"))


class ProcessFilesTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="ncmconvert_test_")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_failure_does_not_stop_batch(self):
        good_one = os.path.join(self.work, "1.ncm")
        bad = os.path.join(self.work, "2.ncm")
        good_two = os.path.join(self.work, "3.ncm")
        for path, data in ((good_one, build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO)),
                           (bad, b"NOTNCM" + b"\x00" * 32),
                           (good_two, build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO))):
            with open(path, "wb") as handle:
                handle.write(data)

        failures = []
        summary = process_files([good_one, bad, good_two], self.work,
                                on_failure=lambda path, exc: failures.append(path))
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(failures, [bad])

    def test_stop_request_breaks_loop(self):
        path = os.path.join(self.work, "1.ncm")
        with open(path, "wb") as handle:
            handle.write(build_ncm(KEY_MATERIAL, META_MP3, b"", AUDIO))
        summary = process_files([path, path], self.work, should_stop=lambda: True)
        self.assertTrue(summary["canceled"])
        self.assertEqual(summary["success"] + summary["failed"], 0)


if __name__ == "__main__":
    unittest.main()
