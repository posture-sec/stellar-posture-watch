#!/usr/bin/env python3
"""Tests asserting .github/workflows/self-check.yml exit-3 probe asserts 4 post-conditions.

Issue #92 / Roadmap 9.10.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF_CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "self-check.yml"


def extract_probe_assertion_script(text: str) -> str:
    """Extract the run: script for the probe assertion step."""
    lines = text.splitlines()
    in_step = False
    in_run = False
    run_lines: list[str] = []
    for line in lines:
        if "Require that the unreadable read stopped before any body existed" in line:
            in_step = True
            continue
        if in_step:
            if re.match(r"^\s+run:\s*\|", line):
                in_run = True
                continue
            if in_run:
                if line.strip() and not line.startswith(" " * 8):
                    break
                run_lines.append(line.strip())
    if not run_lines:
        raise ValueError("Could not find assertion step script in self-check.yml")
    return "\n".join(run_lines)


class TestWorkflowsExit3Probe(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SELF_CHECK_WORKFLOW.read_text(encoding="utf-8")
        self.script = extract_probe_assertion_script(self.text)

    def test_probe_step_continues_on_error(self) -> None:
        self.assertIn("continue-on-error: true", self.text)

    def test_claim_1_outcome_failure(self) -> None:
        self.assertIn('[ "$OUTCOME" = "failure" ]', self.script)
        self.assertIn("the run survived an endpoint that cannot be read", self.script)

    def test_claim_2_report_file_exists(self) -> None:
        self.assertIn('[ -f "$RUNNER_TEMP/report.json" ]', self.script)
        self.assertIn("no report file exists", self.script)

    def test_claim_3_report_file_is_empty(self) -> None:
        self.assertIn('[ ! -s "$RUNNER_TEMP/report.json" ]', self.script)
        self.assertIn("bytes of report against an unreadable endpoint", self.script)

    def test_claim_4_body_never_rendered(self) -> None:
        self.assertIn('[ ! -e "$RUNNER_TEMP/issue-body.md" ]', self.script)
        self.assertIn("a body was rendered from a run that could not read anything", self.script)

    def test_gauge_exit_code_checked(self) -> None:
        self.assertIn('"$GAUGE_EXIT" != "3"', self.script)

    def test_missing_claim_fails(self) -> None:
        mutated_script = self.script.replace('[ ! -s "$RUNNER_TEMP/report.json" ]', "")
        self.assertNotIn('[ ! -s "$RUNNER_TEMP/report.json" ]', mutated_script)


if __name__ == "__main__":
    unittest.main()
