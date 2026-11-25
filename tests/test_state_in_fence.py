#!/usr/bin/env python3
"""Tests for issue #53: a state marker inside a fenced example is not state."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_report.py"
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"
KNOWN_FP = "b03faa6106f2405560196e0cad9e0bb74cab9c08d798877c0d795019bddd43d6"
KNOWN_ACCOUNT = "GC2HHIM66CBKJFMYOHECBMKD4NWRGWJ3FEXFDPWPT4TLS7OFR43LO2II"
KNOWN_ENTRY = {
    "account": KNOWN_ACCOUNT,
    "fingerprint": KNOWN_FP,
    "rule": "acct-missing",
    "severity": "high",
}


def _encode_state(findings: list) -> str:
    payload = json.dumps(findings, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


class TestStateInFence(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._call = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _render_with_previous(self, previous_body: str) -> tuple[int, str, str]:
        self._call += 1
        prev = self.tmp / f"previous{self._call}.md"
        prev.write_text(previous_body)
        body_out = self.tmp / f"body{self._call}.md"
        summary = self.tmp / f"summary{self._call}.json"
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--report",
                str(FIXTURES / "report-findings.json"),
                "--out",
                str(body_out),
                "--summary-out",
                str(summary),
                "--as-of",
                "2026-11-03",
                "--config",
                "policy.toml",
                "--gauge-ref",
                PIN,
                "--exit-code",
                "1",
                "--previous-body",
                str(prev),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode, body_out.read_text() if body_out.exists() else "", done.stderr

    def test_a_marker_inside_a_backtick_fence_is_not_decoded_as_state(self) -> None:
        payload = _encode_state([KNOWN_ENTRY])
        previous = f"```\n<!-- posture-watch:state v1 {payload} -->\n```\n"
        code, body, err = self._render_with_previous(previous)
        self.assertEqual(code, 0, err)
        self.assertIn("establishes the baseline", body)

    def test_a_marker_inside_a_tilde_fence_is_not_decoded_as_state(self) -> None:
        payload = _encode_state([KNOWN_ENTRY])
        previous = f"~~~\n<!-- posture-watch:state v1 {payload} -->\n~~~\n"
        code, body, err = self._render_with_previous(previous)
        self.assertEqual(code, 0, err)
        self.assertIn("establishes the baseline", body)

    def test_a_live_marker_after_a_fenced_copy_is_decoded(self) -> None:
        live_payload = _encode_state([KNOWN_ENTRY])
        fake_entry = {"account": "x", "fingerprint": "a" * 64, "rule": "other", "severity": "high"}
        fake_payload = _encode_state([fake_entry])
        previous = (
            f"```\n<!-- posture-watch:state v1 {fake_payload} -->\n```\n\n"
            f"<!-- posture-watch:state v1 {live_payload} -->\n"
        )
        code, body, err = self._render_with_previous(previous)
        self.assertEqual(code, 0, err)
        self.assertNotIn("establishes the baseline", body)

    def test_a_marker_after_an_unterminated_fence_is_not_decoded(self) -> None:
        payload = _encode_state([KNOWN_ENTRY])
        previous = f"```\nsome code\n<!-- posture-watch:state v1 {payload} -->\n"
        code, body, err = self._render_with_previous(previous)
        self.assertEqual(code, 0, err)
        self.assertIn("establishes the baseline", body)


if __name__ == "__main__":
    unittest.main()
