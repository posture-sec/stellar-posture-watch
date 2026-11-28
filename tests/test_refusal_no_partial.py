#!/usr/bin/env python3
"""Tests for issue #54: no refusal path leaves an output file behind."""

from __future__ import annotations

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


class TestRefusalNoPartial(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._call = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _render(self, report_path: Path, exit_code: int = 1) -> tuple[int, Path, Path, str]:
        self._call += 1
        body = self.tmp / f"body{self._call}.md"
        summary = self.tmp / f"summary{self._call}.json"
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--report",
                str(report_path),
                "--out",
                str(body),
                "--summary-out",
                str(summary),
                "--as-of",
                "2026-11-03",
                "--config",
                "policy.toml",
                "--gauge-ref",
                PIN,
                "--exit-code",
                str(exit_code),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode, body, summary, done.stderr

    def _assert_no_outputs(self, body: Path, summary: Path, label: str = "") -> None:
        self.assertFalse(body.exists(), f"body must not exist after refusal: {label}")
        self.assertFalse(summary.exists(), f"summary must not exist after refusal: {label}")

    def test_bad_json_leaves_no_output(self) -> None:
        path = self.tmp / "bad.json"
        path.write_text('{"tool_version": "x", ')
        code, body, summary, err = self._render(path)
        self.assertEqual(code, 2, err)
        self._assert_no_outputs(body, summary, "bad JSON")

    def test_missing_field_leaves_no_output(self) -> None:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        del report["ledger"]
        path = self.tmp / "noledger.json"
        path.write_text(json.dumps(report))
        code, body, summary, err = self._render(path, exit_code=0)
        self.assertEqual(code, 2, err)
        self._assert_no_outputs(body, summary, "missing field")

    def test_non_string_limits_leaves_no_output(self) -> None:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        report["limits"] = [1, 2, 3]
        path = self.tmp / "listlimits.json"
        path.write_text(json.dumps(report))
        code, body, summary, err = self._render(path, exit_code=0)
        self.assertEqual(code, 2, err)
        self._assert_no_outputs(body, summary, "non-string limits")

    def test_exit_code_mismatch_leaves_no_output(self) -> None:
        code, body, summary, err = self._render(FIXTURES / "report-clean.json", exit_code=1)
        self.assertEqual(code, 2, err)
        self._assert_no_outputs(body, summary, "exit code mismatch")

    def test_summary_out_as_directory_cleans_up_body(self) -> None:
        self._call += 1
        body = self.tmp / f"body{self._call}.md"
        summary_dir = self.tmp / f"summary_dir{self._call}"
        summary_dir.mkdir()
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--report",
                str(FIXTURES / "report-clean.json"),
                "--out",
                str(body),
                "--summary-out",
                str(summary_dir),
                "--as-of",
                "2026-11-03",
                "--config",
                "policy.toml",
                "--gauge-ref",
                PIN,
                "--exit-code",
                "0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertFalse(body.exists(), "body must not remain when summary write fails")


if __name__ == "__main__":
    unittest.main()
