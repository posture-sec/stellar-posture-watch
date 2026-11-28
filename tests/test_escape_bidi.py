#!/usr/bin/env python3
"""Tests for bidi and zero-width character stripping in render_report.escape()."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from render_report import escape  # type: ignore[import-not-found]  # noqa: E402


class TestEscapeBidi(unittest.TestCase):
    def test_right_to_left_override_is_stripped(self) -> None:
        self.assertEqual(escape("abc‮def"), "abcdef")

    def test_lre_and_rle_are_stripped(self) -> None:
        self.assertEqual(escape("a‪b‫c"), "abc")

    def test_lro_rlo_pdf_are_stripped(self) -> None:
        self.assertEqual(escape("x‬y‭z‮"), "xyz")

    def test_bidi_isolates_are_stripped(self) -> None:
        self.assertEqual(escape("⁦a⁧b⁨c⁩"), "abc")

    def test_zero_width_space_is_stripped(self) -> None:
        self.assertEqual(escape("a​b"), "ab")

    def test_zwnj_and_zwj_are_stripped(self) -> None:
        self.assertEqual(escape("a‌b‍c"), "abc")

    def test_word_joiner_and_bom_are_stripped(self) -> None:
        self.assertEqual(escape("⁠a﻿b"), "ab")

    def test_mention_rewrite_still_emits_zero_width_entity(self) -> None:
        result = escape("@somebody")
        self.assertIn("@&#8203;somebody", result)

    def test_ascii_and_normal_unicode_pass_through(self) -> None:
        self.assertEqual(escape("hello world"), "hello world")
        self.assertEqual(escape("こんにちは"), "こんにちは")

    def test_markdown_escape_still_applied_after_strip(self) -> None:
        result = escape("‮*bold*")
        self.assertIn(r"\*bold\*", result)
        self.assertNotIn("‮", result)


if __name__ == "__main__":
    unittest.main()
