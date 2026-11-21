#!/usr/bin/env python3
"""Tests asserting .github/workflows/watch.yml sets timeout-minutes under ceiling.

Issue #90 / Roadmap 9.9.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH_WORKFLOW = ROOT / ".github" / "workflows" / "watch.yml"


def parse_watch_timeout(text: str) -> int:
    """Parse timeout-minutes from the watch job in watch.yml without YAML parser."""
    lines = text.splitlines()
    in_watch_job = False
    for line in lines:
        if line.startswith("  watch:") or line.startswith("  audit:"):
            in_watch_job = True
            continue
        if in_watch_job:
            if line and not line.startswith("    ") and not line.startswith("  "):
                break
            match = re.match(r"^\s+timeout-minutes:\s*(\d+)", line)
            if match:
                return int(match.group(1))
    raise ValueError("watch.yml does not set timeout-minutes on the watch job")


class TestWorkflowsWatchTimeout(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATCH_WORKFLOW.read_text(encoding="utf-8")

    def test_timeout_minutes_exists_and_in_range(self) -> None:
        timeout = parse_watch_timeout(self.text)
        # Runner ceiling is 360 (6 hours), weekly gap is 10080 minutes.
        self.assertGreaterEqual(timeout, 1)
        self.assertLessEqual(timeout, 360)

    def test_comment_explains_observed_duration(self) -> None:
        self.assertTrue(
            "Observed duration" in self.text
            or "30 minutes" in self.text
            or "Gauge build" in self.text
        )
        self.assertTrue("timeout-minutes: 15" in self.text or "timeout-minutes: 30" in self.text)

    def test_covers_both_triggers(self) -> None:
        self.assertIn("schedule:", self.text)
        self.assertIn("workflow_dispatch:", self.text)

    def test_missing_timeout_mutation_fails(self) -> None:
        mutated = self.text.replace("timeout-minutes: 30", "").replace("timeout-minutes: 15", "")
        with self.assertRaises(ValueError):
            parse_watch_timeout(mutated)


if __name__ == "__main__":
    unittest.main()
