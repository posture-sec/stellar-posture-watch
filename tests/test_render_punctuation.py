#!/usr/bin/env python3
"""Tests that rendered bodies contain no em dash (U+2014).

The em-dash rule comes from CONTRIBUTING.md: body literals must use a plain
hyphen, never the typographic em dash.  This test enforces that the renderer's
own static text obeys the rule.  It is applied to the rendered output rather
than to ``escape()``, because chain-derived text passes through ``escape()``
unchanged with respect to dashes, and checking ``escape()`` directly would
not catch an em dash inserted into the template strings in render_report.py.
"""

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
EM_DASH = "—"


class TestNoPunctuation(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._n = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _render(self, fixture: str, previous: Path | None = None) -> str:
        self._n += 1
        body = self.tmp / f"body{self._n}.md"
        exit_code = json.loads((FIXTURES / fixture).read_text())["exit_code"]
        argv = [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(FIXTURES / fixture),
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
        ]
        if previous is not None:
            argv += ["--previous-body", str(previous)]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        return body.read_text()

    def test_no_fixture_body_contains_em_dash(self) -> None:
        for name in sorted(p.name for p in FIXTURES.glob("report-*.json")):
            with self.subTest(fixture=name):
                body = self._render(name)
                for lineno, line in enumerate(body.splitlines(), 1):
                    self.assertNotIn(EM_DASH, line, f"{name}: em dash on line {lineno}: {line!r}")

    def test_no_change_body_contains_no_em_dash(self) -> None:
        first = self.tmp / "previous.md"
        first.write_text(self._render("report-clean.json"))
        body = self._render("report-clean.json", previous=first)
        for lineno, line in enumerate(body.splitlines(), 1):
            self.assertNotIn(EM_DASH, line, f"no-change render: em dash on line {lineno}: {line!r}")


if __name__ == "__main__":
    unittest.main()
