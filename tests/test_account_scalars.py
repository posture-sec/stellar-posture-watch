#!/usr/bin/env python3
"""Tests for check_snapshot_scalars in render_report.account_rows."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SCRIPT = ROOT / "scripts" / "render_report.py"
PIN = "da656733fff839d5cf20f795460f4365a7254257"


class TestAccountScalars(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._n = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _render(self, report_path: Path) -> tuple[int, str]:
        self._n += 1
        body = self.tmp / f"body{self._n}.md"
        exit_code = json.loads(report_path.read_text())["exit_code"]
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--report",
                str(report_path),
                "--out",
                str(body),
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
        return done.returncode, done.stderr

    def _make_report(self, **overrides: object) -> Path:
        base = json.loads((FIXTURES / "report-clean.json").read_text())
        snapshot = base["accounts"][0].setdefault("snapshot", {})
        snapshot.setdefault("ledger", 1)
        snapshot.setdefault("thresholds", {"low": 0, "medium": 0, "high": 0})
        snapshot.update(overrides)
        self._n += 1
        path = self.tmp / f"custom{self._n}.json"
        path.write_text(json.dumps(base))
        return path

    def test_string_ledger_is_refused(self) -> None:
        code, err = self._render(self._make_report(ledger="2233445 | 0"))
        self.assertEqual(code, 2)
        self.assertIn("snapshot.ledger", err)

    def test_string_threshold_is_refused(self) -> None:
        code, err = self._render(self._make_report(thresholds={"low": "1", "medium": 2, "high": 3}))
        self.assertEqual(code, 2)
        self.assertIn("snapshot.thresholds.low", err)

    def test_boolean_ledger_is_refused(self) -> None:
        code, err = self._render(self._make_report(ledger=True))
        self.assertEqual(code, 2)
        self.assertIn("snapshot.ledger", err)

    def test_boolean_threshold_is_refused(self) -> None:
        code, err = self._render(
            self._make_report(thresholds={"low": False, "medium": 0, "high": 0})
        )
        self.assertEqual(code, 2)
        self.assertIn("snapshot.thresholds.low", err)

    def test_existing_fixtures_render_successfully(self) -> None:
        for name in sorted(p.name for p in FIXTURES.glob("report-*.json")):
            with self.subTest(fixture=name):
                code, err = self._render(FIXTURES / name)
                self.assertEqual(code, 0, f"{name}: {err}")


if __name__ == "__main__":
    unittest.main()
