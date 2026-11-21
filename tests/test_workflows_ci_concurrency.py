#!/usr/bin/env python3
"""Tests asserting .github/workflows/ci.yml declares concurrency group with main exemption.

Issue #88 / Roadmap 9.11.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class TestWorkflowsCiConcurrency(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_concurrency_block_placement_above_jobs(self) -> None:
        conc_idx = self.text.find("concurrency:")
        jobs_idx = self.text.find("jobs:")
        self.assertNotEqual(conc_idx, -1)
        self.assertNotEqual(jobs_idx, -1)
        self.assertLess(conc_idx, jobs_idx)

    def test_concurrency_group(self) -> None:
        self.assertIn("group: ${{ github.workflow }}-${{ github.ref }}", self.text)

    def test_concurrency_cancel_in_progress_main_exempt(self) -> None:
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
