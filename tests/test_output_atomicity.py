#!/usr/bin/env python3
"""Test that render_report writes body and summary atomically with tempfiles.

Verifies:
1. Both outputs are staged as temporaries in destination directories and moved via os.replace.
2. The body is replaced before the summary, with the summary as the commit point.
3. A staging failure leaves both previous files untouched and removes temporaries.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import render_report

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class TestOutputAtomicity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.report_path = FIXTURES / "report-clean.json"
        self.out_path = self.tmp / "issue-body.md"
        self.summary_path = self.tmp / "summary.json"
        self.base_args = [
            "--report",
            str(self.report_path),
            "--out",
            str(self.out_path),
            "--summary-out",
            str(self.summary_path),
            "--as-of",
            "2026-11-03",
            "--config",
            "example/gauge.toml",
            "--gauge-ref",
            "da656733fff839d5cf20f795460f4365a7254257",
            "--exit-code",
            "0",
        ]

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_successful_write_leaves_no_temporaries_and_creates_matching_outputs(self) -> None:
        code = render_report.main(self.base_args)
        self.assertEqual(code, 0)
        self.assertTrue(self.out_path.exists())
        self.assertTrue(self.summary_path.exists())

        # No stray temp files left behind in destination directory
        stray = [p.name for p in self.tmp.iterdir() if p not in (self.out_path, self.summary_path)]
        self.assertEqual(stray, [])

        summary = json.loads(self.summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["open"], 0)
        self.assertTrue(summary["changed"])

    def test_failure_staging_summary_leaves_previous_files_untouched_and_cleans_temporaries(
        self,
    ) -> None:
        # Pre-seed existing files
        old_body = "Old body content\n"
        old_summary = '{"changed": false, "open": 99}\n'
        self.out_path.write_text(old_body, encoding="utf-8")
        self.summary_path.write_text(old_summary, encoding="utf-8")

        # Force a failure during the staging of the summary file
        original_named_temp = tempfile.NamedTemporaryFile
        call_count = 0

        def failing_named_temp(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # 1st call is for body, 2nd call is for summary
                raise OSError(13, "Permission denied while staging summary")
            return original_named_temp(*args, **kwargs)

        with patch("tempfile.NamedTemporaryFile", side_effect=failing_named_temp):
            code = render_report.main(self.base_args)

        self.assertEqual(code, 2)
        # Previous files must remain completely untouched
        self.assertEqual(self.out_path.read_text(encoding="utf-8"), old_body)
        self.assertEqual(self.summary_path.read_text(encoding="utf-8"), old_summary)

        # All temporary files must be cleaned up
        stray = [p.name for p in self.tmp.iterdir() if p not in (self.out_path, self.summary_path)]
        self.assertEqual(stray, [])

    def test_body_is_replaced_before_summary(self) -> None:
        replace_calls: list[Path] = []
        original_replace = os.replace

        def recording_replace(src, dst):
            replace_calls.append(Path(dst))
            return original_replace(src, dst)

        with patch("os.replace", side_effect=recording_replace):
            code = render_report.main(self.base_args)

        self.assertEqual(code, 0)
        self.assertEqual(replace_calls, [self.out_path, self.summary_path])


if __name__ == "__main__":
    unittest.main()
