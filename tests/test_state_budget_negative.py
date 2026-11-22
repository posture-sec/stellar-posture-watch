#!/usr/bin/env python3
"""Tests for issue #49: render_report.py refuses --max-state-entries below zero.

A negative budget flows through encode_state and slices from the end of the
ordered list, so the omitted count becomes negative and the partial notice reports
a nonsense number. The fix exits 2 before the report is read.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._calls = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def render(self, budget: int | None = None) -> tuple[int, str, str]:
        import subprocess

        self._calls += 1
        body = self.tmp / f"body{self._calls}.md"
        argv = [
            sys.executable,
            str(ROOT / "scripts" / "render_report.py"),
            "--report",
            str(FIXTURES / "report-findings.json"),
            "--out",
            str(body),
            "--as-of",
            "2026-11-03",
            "--config",
            "policy.toml",
            "--gauge-ref",
            PIN,
            "--exit-code",
            "1",
        ]
        if budget is not None:
            argv += ["--max-state-entries", str(budget)]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        return done.returncode, body.read_text() if body.exists() else "", done.stderr


class TestNegativeBudget(Harness):
    def test_negative_one_exits_2_with_no_body(self) -> None:
        code, body, err = self.render(-1)
        self.assertEqual(code, 2, f"expected exit 2, got {code}; stderr={err!r}")
        self.assertEqual(body, "", "no body must be written on a refusal")

    def test_refusal_line_names_the_flag_and_the_minimum(self) -> None:
        _, _, err = self.render(-1)
        self.assertIn("--max-state-entries", err)
        self.assertIn("0", err)

    def test_zero_budget_still_renders(self) -> None:
        code, body, err = self.render(0)
        self.assertEqual(code, 0, f"expected exit 0 for budget=0, got {code}; stderr={err!r}")
        self.assertIn("Change detection is partial", body)

    def test_normal_budget_renders_unchanged(self) -> None:
        code, _, err = self.render(5)
        self.assertEqual(code, 0, f"expected exit 0 for budget=5, got {code}; stderr={err!r}")


if __name__ == "__main__":
    unittest.main()
