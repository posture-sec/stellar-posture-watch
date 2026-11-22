#!/usr/bin/env python3
"""Tests for issue #48: decode_state reads the last marker occurrence, not the first.

The renderer appends the live marker last. A quoted or fenced older marker earlier in
the body must not drive change detection: it would compare the current run against an
old run and report spurious diffs.
"""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"

sys.path.insert(0, str(ROOT / "scripts"))
import render_report  # noqa: E402

MARKER_PREFIX = render_report.MARKER_PREFIX
MARKER_SUFFIX = render_report.MARKER_SUFFIX


def make_marker(findings: list[render_report.Finding]) -> str:
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(findings, separators=(",", ":"), sort_keys=True).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{MARKER_PREFIX}{encoded}{MARKER_SUFFIX}"


OLD_FINDING: render_report.Finding = {
    "account": "GOLD",
    "fingerprint": "a" * 64,
    "message": "",
    "rule": "old-rule",
    "severity": "high",
}

NEW_FINDING: render_report.Finding = {
    "account": "GNEW",
    "fingerprint": "b" * 64,
    "message": "",
    "rule": "new-rule",
    "severity": "warn",
}


class TestDecodeStateLastMarker(unittest.TestCase):
    def test_body_with_two_markers_uses_the_last_one(self) -> None:
        old_marker = make_marker([OLD_FINDING])
        new_marker = make_marker([NEW_FINDING])
        body = f"Some earlier text\n\n{old_marker}\n\nMore text\n\n{new_marker}\n"
        result = render_report.decode_state(body)
        self.assertIsNotNone(result, "should decode the last marker")
        assert result is not None
        fps = [f["fingerprint"] for f in result]
        self.assertIn("b" * 64, fps, "last marker's fingerprint must be present")
        self.assertNotIn("a" * 64, fps, "first marker's fingerprint must not be used")

    def test_single_marker_body_is_unchanged(self) -> None:
        marker = make_marker([OLD_FINDING])
        body = f"body text\n\n{marker}\n"
        result = render_report.decode_state(body)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual([f["fingerprint"] for f in result], ["a" * 64])

    def test_corrupt_last_marker_returns_none(self) -> None:
        good_marker = make_marker([OLD_FINDING])
        # Encode a JSON object (not a list) as base64url — valid base64 chars but
        # fails the isinstance(entries, list) check inside decode_state.
        not_a_list = base64.urlsafe_b64encode(b'{"not":"alist"}').decode().rstrip("=")
        corrupt_marker = f"{MARKER_PREFIX}{not_a_list}{MARKER_SUFFIX}"
        body = f"text\n\n{good_marker}\n\nmore text\n\n{corrupt_marker}\n"
        result = render_report.decode_state(body)
        self.assertIsNone(result, "corrupt last marker must return None, not fall back to first")

    def test_body_with_no_marker_returns_none(self) -> None:
        self.assertIsNone(render_report.decode_state("no marker here at all"))


if __name__ == "__main__":
    unittest.main()
