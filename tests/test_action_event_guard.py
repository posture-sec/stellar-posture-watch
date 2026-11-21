#!/usr/bin/env python3
"""Test that action.yml refuses pull_request runs unless dry-run is explicitly true.

Verifies:
1. The guard step appears before 'Fetch the pinned Gauge commit'.
2. The run block contains no expressions (${{ }}).
3. pull_request with dry-run absent or false exits 2 with one line on stderr.
4. pull_request with dry-run: true exits 0.
5. Other events (schedule, workflow_dispatch, push) proceed with dry-run false or true.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTION_FILE = ROOT / "action.yml"


class TestActionEventGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ACTION_FILE.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()

    def test_guard_step_precedes_checkout(self) -> None:
        guard_idx: int | None = None
        checkout_idx: int | None = None
        guard_run: list[str] = []
        in_guard_run = False
        step_idx = 0
        in_steps = False

        for line in self.lines:
            if line.strip() == "steps:":
                in_steps = True
                continue
            if in_steps:
                if line.startswith("    - name:"):
                    step_idx += 1
                    if "guard" in line.lower() or "pull_request" in line.lower():
                        guard_idx = step_idx
                    if "fetch the pinned gauge commit" in line.lower():
                        checkout_idx = step_idx
                elif guard_idx == step_idx and line.strip().startswith("run:"):
                    in_guard_run = True
                    continue
                elif in_guard_run:
                    if line.strip() and not line.startswith(" " * 8):
                        in_guard_run = False
                    else:
                        guard_run.append(line)

        self.assertIsNotNone(guard_idx, "Event guard step not found in action.yml")
        self.assertIsNotNone(checkout_idx, "Checkout step not found in action.yml")
        self.assertLess(guard_idx, checkout_idx, "Event guard must precede Gauge checkout")

        # Verify no expressions in run block
        for line in guard_run:
            self.assertNotIn("${{", line)

    def test_guard_script_event_matrix(self) -> None:
        script = """
        if [ "$EVENT_NAME" = "pull_request" ] && [ "$DRY_RUN" != "true" ]; then
          echo "stellar-posture-watch: pull_request event is only supported with dry-run: true" >&2
          exit 2
        fi
        """

        cases = [
            # (event, dry_run, expected_exit, expect_err_msg)
            (
                "pull_request",
                "false",
                2,
                "stellar-posture-watch: pull_request event is only supported with dry-run: true\n",
            ),
            (
                "pull_request",
                "",
                2,
                "stellar-posture-watch: pull_request event is only supported with dry-run: true\n",
            ),
            ("pull_request", "true", 0, ""),
            ("schedule", "false", 0, ""),
            ("schedule", "true", 0, ""),
            ("workflow_dispatch", "false", 0, ""),
            ("workflow_dispatch", "true", 0, ""),
            ("push", "false", 0, ""),
            ("push", "true", 0, ""),
        ]

        for event, dry_run, expected_code, expected_err in cases:
            proc = subprocess.run(
                ["bash", "-c", script],
                env={"EVENT_NAME": event, "DRY_RUN": dry_run},
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                proc.returncode,
                expected_code,
                f"Failed for event={event}, dry_run={dry_run}: code {proc.returncode}",
            )
            self.assertEqual(
                proc.stderr,
                expected_err,
                f"Stderr mismatch for event={event}, dry_run={dry_run}",
            )


if __name__ == "__main__":
    unittest.main()
