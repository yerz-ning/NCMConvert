import unittest

from src.core.constants import DEFAULT_FORMAT, MAX_BASE_RUNES
from src.core.naming import build_base_name, normalize_ext, sanitize


class SanitizeTest(unittest.TestCase):
    def test_replaces_reserved_characters(self):
        self.assertEqual(sanitize('A<B>C:D"E/F\\G|H?I*J'), "A_B_C_D_E_F_G_H_I_J")

    def test_replaces_control_characters(self):
        self.assertEqual(sanitize("a\tb\nc"), "a_b_c")
        self.assertEqual(sanitize("a\x00b"), "ab")
        self.assertEqual(sanitize("a\x7fb"), "a_b")

    def test_strips_trailing_dots_and_spaces(self):
        self.assertEqual(sanitize("name. . "), "name")

    def test_avoids_device_names(self):
        self.assertEqual(sanitize("con"), "_con")
        self.assertEqual(sanitize("NUL"), "_NUL")
        self.assertEqual(sanitize("lpt9"), "_lpt9")

    def test_empty_input(self):
        self.assertEqual(sanitize(""), "")
        self.assertEqual(sanitize("   "), "")
        self.assertEqual(sanitize(None), "")

    def test_length_limit(self):
        self.assertEqual(len(sanitize("あ" * 300)), MAX_BASE_RUNES)

    def test_keeps_chinese_characters(self):
        self.assertEqual(sanitize("《稻香》童声"), "《稻香》童声")


class BaseNameTest(unittest.TestCase):
    def test_title_and_artist(self):
        self.assertEqual(build_base_name("稻香", "卡罗尔", "source"), "稻香 - 卡罗尔")

    def test_fallback_to_input_name(self):
        self.assertEqual(build_base_name("", "", "song"), "song")

    def test_unknown_when_everything_empty(self):
        self.assertEqual(build_base_name("", "", ""), "unknown")

    def test_artist_equal_to_title(self):
        self.assertEqual(build_base_name("稻香", "稻香", "song"), "稻香")

    def test_artist_sanitized(self):
        self.assertEqual(build_base_name("曲目", "A/B", "song"), "曲目 - A_B")

    def test_total_length_capped(self):
        name = build_base_name("あ" * 200, "い" * 200, "song")
        self.assertEqual(len(name), MAX_BASE_RUNES)


class NormalizeExtTest(unittest.TestCase):
    def test_plain_format(self):
        self.assertEqual(normalize_ext("mp3"), "mp3")

    def test_dot_and_case(self):
        self.assertEqual(normalize_ext(".FLAC"), "flac")

    def test_empty_uses_default(self):
        self.assertEqual(normalize_ext(""), DEFAULT_FORMAT)
        self.assertEqual(normalize_ext(None), DEFAULT_FORMAT)
        self.assertEqual(normalize_ext("   "), DEFAULT_FORMAT)

    def test_invalid_characters_removed(self):
        self.assertEqual(normalize_ext("m?p3"), "m_p3")

    def test_too_long_ext(self):
        self.assertEqual(len(normalize_ext("x" * 40)), 16)


if __name__ == "__main__":
    unittest.main()
