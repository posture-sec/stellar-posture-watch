#!/usr/bin/env python3
"""Tests that render_report.py emits all expected summary keys and that
sync_issue.py's read_summary and comment_body accept the output.

Issue #42.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_issue import comment_body, read_summary  # noqa: E402
from test_render_report import Renderer  # noqa: E402

EXPECTED_KEYS = {
    "changed",
    "new",
    "resolved",
    "open",
    "high",
    "warn",
    "accepted",
    "omitted",
    "as_of",
}
INT_KEYS = {"new", "resolved", "open", "high", "warn", "accepted", "omitted"}


class TestSummaryKeys(Renderer):
    def test_summary_has_exactly_the_expected_keys(self) -> None:
        _, _, summary, err = self.render("report-findings.json")
        self.assertEqual(set(summary.keys()), EXPECTED_KEYS, err)

    def test_count_fields_are_integers(self) -> None:
        _, _, summary, _ = self.render("report-findings.json")
        for key in INT_KEYS:
            with self.subTest(key=key):
                self.assertIsInstance(summary[key], int, f"{key!r}: {summary[key]!r}")

    def test_changed_is_bool(self) -> None:
        _, _, summary, _ = self.render("report-findings.json")
        self.assertIsInstance(summary["changed"], bool)

    def test_as_of_is_string(self) -> None:
        _, _, summary, _ = self.render("report-findings.json")
        self.assertIsInstance(summary["as_of"], str)

    def test_read_summary_accepts_the_written_file(self) -> None:
        _, _, _, _ = self.render("report-findings.json")
        summary_file = self.tmp / "summary1.json"
        self.assertTrue(summary_file.exists(), "render must write summary1.json")
        result = read_summary(summary_file)
        for key in ("changed", "new", "resolved", "open", "as_of"):
            self.assertIn(key, result)

    def test_comment_body_names_the_as_of_date(self) -> None:
        _, _, summary, _ = self.render("report-findings.json")
        text = comment_body(summary)
        self.assertIn(summary["as_of"], text)


if __name__ == "__main__":
    unittest.main()
