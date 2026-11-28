#!/usr/bin/env python3
"""Tests for the zero-budget state marker path in scripts/render_report.py.

Issue #39: render with --max-state-entries 0, assert the body announces the omission,
the marker is present and decodes to [], and the summary counts omitted == 1.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import unittest
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))

from test_render_report import Renderer

MARKER_RE = re.compile(r"<!-- posture-watch:state v1 ([A-Za-z0-9_-]*) -->")


class TestStateBudgetZero(Renderer):
    def test_body_says_carries_zero_of_one(self) -> None:
        code, body, _summary, err = self.render(
            "report-findings.json", extra={"max-state-entries": 0}
        )
        self.assertEqual(code, 0, err)
        self.assertIn("carries 0 of 1", body)

    def test_marker_is_present_and_matches_marker_re(self) -> None:
        _, body, _, _ = self.render("report-findings.json", extra={"max-state-entries": 0})
        self.assertIsNotNone(MARKER_RE.search(body), "body must contain a state marker")

    def test_marker_decodes_to_empty_list(self) -> None:
        _, body, _, _ = self.render("report-findings.json", extra={"max-state-entries": 0})
        match = MARKER_RE.search(body)
        self.assertIsNotNone(match)
        encoded = match.group(1)
        padding = "=" * (-len(encoded) % 4)
        entries = json.loads(base64.urlsafe_b64decode(encoded + padding))
        self.assertEqual(entries, [])

    def test_summary_omitted_is_one(self) -> None:
        _, _, summary, _ = self.render("report-findings.json", extra={"max-state-entries": 0})
        self.assertEqual(summary["omitted"], 1)

    def test_summary_changed_is_true(self) -> None:
        _, _, summary, _ = self.render("report-findings.json", extra={"max-state-entries": 0})
        self.assertTrue(summary["changed"])


if __name__ == "__main__":
    unittest.main()
