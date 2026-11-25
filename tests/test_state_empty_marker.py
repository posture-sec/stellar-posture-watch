#!/usr/bin/env python3
"""Tests for change detection when the previous body carries an empty-list marker.

Issue #41: a previous body whose marker encodes [] (no prior findings) should read
as unchanged when re-rendered against a clean report, and should detect one new
finding when rendered against report-findings.json.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_render_report import Renderer

# base64url of b'[]' (no padding needed for the 3-character result)
EMPTY_LIST_ENCODED = "W10"
EMPTY_LIST_MARKER = f"<!-- posture-watch:state v1 {EMPTY_LIST_ENCODED} -->"

MARKER_RE = re.compile(r"<!-- posture-watch:state v1 ([A-Za-z0-9_-]*) -->")


def _empty_marker_body(tmp: Path) -> Path:
    """Write a previous-body file whose state marker encodes an empty finding list."""
    path = tmp / "empty_marker_previous.md"
    path.write_text(f"Previous run header.\n\n{EMPTY_LIST_MARKER}\n", encoding="utf-8")
    return path


class TestStateEmptyMarker(Renderer):
    def test_clean_report_with_empty_marker_is_not_changed(self) -> None:
        previous = _empty_marker_body(self.tmp)
        code, _body, summary, err = self.render("report-clean.json", previous)
        self.assertEqual(code, 0, err)
        self.assertFalse(summary["changed"])

    def test_clean_report_with_empty_marker_says_unchanged(self) -> None:
        previous = _empty_marker_body(self.tmp)
        _, body, _, _ = self.render("report-clean.json", previous)
        self.assertIn("unchanged since the previous run", body)

    def test_clean_report_with_empty_marker_has_no_baseline_sentence(self) -> None:
        previous = _empty_marker_body(self.tmp)
        _, body, _, _ = self.render("report-clean.json", previous)
        self.assertNotIn("establishes the baseline", body)

    def test_findings_report_with_empty_marker_shows_one_new_finding(self) -> None:
        previous = _empty_marker_body(self.tmp)
        code, _, summary, err = self.render("report-findings.json", previous)
        self.assertEqual(code, 0, err)
        self.assertEqual(summary["new"], 1)
        self.assertTrue(summary["changed"])


if __name__ == "__main__":
    unittest.main()
