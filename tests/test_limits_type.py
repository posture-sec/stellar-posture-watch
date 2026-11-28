#!/usr/bin/env python3
"""Tests for issue #50: refuse a limits field that is not a string."""

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


class TestLimitsType(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._call = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _render(self, report_path: Path, exit_code: int = 0) -> tuple[int, str, str]:
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
        return done.returncode, body.read_text() if body.exists() else "", done.stderr

    def _make_report(self, limits_value: object) -> Path:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        report["limits"] = limits_value
        path = self.tmp / f"limits_{self._call}.json"
        path.write_text(json.dumps(report))
        return path

    def _make_report_no_limits(self) -> Path:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        del report["limits"]
        path = self.tmp / "limits_absent.json"
        path.write_text(json.dumps(report))
        return path

    def test_a_list_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report(["a", "b"]))
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_a_dict_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report({"key": "val"}))
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_a_number_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report(42))
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_a_boolean_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report(False))
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_a_null_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report(None))
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_an_absent_limits_is_refused(self) -> None:
        code, body, err = self._render(self._make_report_no_limits())
        self.assertEqual(code, 2, err)
        self.assertIn("limits", err)
        self.assertEqual(body, "")

    def test_a_string_limits_renders_normally(self) -> None:
        code, body, err = self._render(FIXTURES / "report-clean.json")
        self.assertEqual(code, 0, err)
        self.assertNotEqual(body, "")


if __name__ == "__main__":
    unittest.main()
