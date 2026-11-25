#!/usr/bin/env python3
"""Tests for previous-body error handling in render_report."""

from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_report.py"
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"


class TestPreviousBodyErrors(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._n = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def _run_subprocess(self, previous_path: str) -> tuple[int, str, bool]:
        self._n += 1
        body = self.tmp / f"body{self._n}.md"
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--report",
                str(FIXTURES / "report-clean.json"),
                "--out",
                str(body),
                "--previous-body",
                previous_path,
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
        return done.returncode, done.stderr, body.exists()

    def test_directory_as_previous_body_exits_2(self) -> None:
        code, err, has_body = self._run_subprocess(str(self.tmp))
        self.assertEqual(code, 2)
        self.assertIn("cannot read it", err)
        self.assertFalse(has_body, "a refusal must not leave a body behind")

    def test_file_removed_between_check_and_read_exits_2(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import render_report as rr  # type: ignore[import-not-found]

        previous = self.tmp / "previous.md"
        previous.write_text("content")
        orig = Path.read_text

        def _raise_on_previous(self_path: Path, **kw: object) -> str:
            if self_path == previous:
                raise FileNotFoundError(2, "No such file or directory")
            return orig(self_path, **kw)  # type: ignore[return-value]

        args = argparse.Namespace(
            report=str(FIXTURES / "report-clean.json"),
            previous_body=str(previous),
            as_of="2026-11-03",
            config="policy.toml",
            gauge_repo="posture-sec/gauge",
            gauge_ref=PIN,
            fail_on="high",
            exit_code=0,
            max_state_entries=200,
        )
        with (
            patch.object(Path, "read_text", _raise_on_previous),
            self.assertRaises(rr.Refused) as ctx,
        ):
            rr.render(args)
        self.assertIn("cannot read it", str(ctx.exception))

    def test_absent_previous_body_is_not_an_error(self) -> None:
        code, err, _ = self._run_subprocess(str(self.tmp / "ghost.md"))
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
