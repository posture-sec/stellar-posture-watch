#!/usr/bin/env python3
"""9.47: short base64 state payloads in a previous body read as no state, not a crash.

A one-character base64 payload decodes to 0 bytes, whose json.loads raises
json.JSONDecodeError.  A padding-only payload (`=`) raises binascii.Error, which is a
subclass of ValueError.  Both must be caught by the broad except in decode_state so the
run re-baselines rather than exiting non-zero.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_report.py"
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"

MARKER_PREFIX = "<!-- posture-watch:state v1 "
MARKER_SUFFIX = " -->"


class ShortPayload(unittest.TestCase):
    """Verifies that every short or malformed payload gives exit 0 and a baseline."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._calls = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def render(self, previous_body: str) -> tuple[int, str, dict, str]:
        import subprocess

        self._calls += 1
        body_out = self.tmp / f"body{self._calls}.md"
        summary_out = self.tmp / f"summary{self._calls}.json"
        previous = self.tmp / f"prev{self._calls}.md"
        previous.write_text(previous_body, encoding="utf-8")

        argv = [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(FIXTURES / "report-findings.json"),
            "--out",
            str(body_out),
            "--summary-out",
            str(summary_out),
            "--previous-body",
            str(previous),
            "--as-of",
            "2026-11-03",
            "--config",
            "policy.toml",
            "--gauge-ref",
            PIN,
            "--exit-code",
            "1",
        ]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        data: dict = {}
        if summary_out.exists() and done.returncode == 0:
            data = json.loads(summary_out.read_text())
        body = body_out.read_text() if body_out.exists() else ""
        return done.returncode, body, data, done.stderr

    def _assert_baseline(self, payload: str, description: str) -> None:
        previous_body = f"{MARKER_PREFIX}{payload}{MARKER_SUFFIX}"
        code, body, summary, err = self.render(previous_body)
        self.assertEqual(code, 0, f"{description}: non-zero exit: {err}")
        self.assertEqual(err, "", f"{description}: unexpected stderr: {err}")
        self.assertIn(
            "establishes the baseline",
            body,
            f"{description}: 'establishes the baseline' not in body",
        )
        self.assertTrue(
            summary.get("changed"),
            f"{description}: summary['changed'] is not True",
        )

    def test_one_character_payload_reads_as_no_state(self) -> None:
        self._assert_baseline("A", "1-char payload")

    def test_two_character_payload_reads_as_no_state(self) -> None:
        self._assert_baseline("AA", "2-char payload")

    def test_padding_only_payload_reads_as_no_state(self) -> None:
        self._assert_baseline("=", "padding-only payload")

    def test_all_padding_payload_reads_as_no_state(self) -> None:
        self._assert_baseline("====", "four-equals payload")


if __name__ == "__main__":
    unittest.main()
