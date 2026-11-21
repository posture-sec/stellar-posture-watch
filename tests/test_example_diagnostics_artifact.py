#!/usr/bin/env python3
"""Tests asserting example/workflow.yml uploads posture-watch-run artifact.

Issue #85 / Roadmap 9.8.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "example" / "workflow.yml"
ACTION_YML = ROOT / "action.yml"


class TestExampleDiagnosticsArtifact(unittest.TestCase):
    def setUp(self) -> None:
        self.text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
        self.action_text = ACTION_YML.read_text(encoding="utf-8")

    def test_record_step_writes_run_json(self) -> None:
        self.assertIn("posture-watch-run.json", self.text)
        self.assertIn('"exit-code": "$GAUGE_EXIT"', self.text)
        self.assertIn('"issue-number": "$ISSUE"', self.text)
        self.assertIn('"changed": "$CHANGED"', self.text)
        self.assertIn('"report-path": "$REPORT_PATH"', self.text)

    def test_upload_artifact_pin_reuses_action_pin(self) -> None:
        pattern = r"actions/upload-artifact@([0-9a-f]{40}\s*#\s*v[0-9.]+)"
        action_match = re.search(pattern, self.action_text)
        self.assertIsNotNone(action_match)
        expected_pin = action_match.group(0)

        self.assertIn(expected_pin, self.text)

    def test_upload_artifact_properties(self) -> None:
        self.assertIn("name: posture-watch-run", self.text)
        self.assertNotIn("name: gauge-diagnostics", self.text)
        self.assertIn("retention-days: 7", self.text)
        self.assertIn("if-no-files-found: ignore", self.text)

    def test_step_order(self) -> None:
        record_idx = self.text.find("name: Record what the run saw")
        upload_idx = self.text.find("name: Upload the run record")
        self.assertNotEqual(record_idx, -1)
        self.assertNotEqual(upload_idx, -1)
        self.assertLess(record_idx, upload_idx)

    def test_comment_names_gauge_diagnostics(self) -> None:
        self.assertIn("gauge-diagnostics", self.text)
        self.assertIn("exit-3 stderr", self.text)


if __name__ == "__main__":
    unittest.main()
