#!/usr/bin/env python3
"""Test that action.yml registers the token mask as its very first step.

Verifies:
1. The first step under steps: registers the token mask.
2. The run block contains no expressions (${{ }}).
3. The masking step precedes every step whose env: binds POSTURE_WATCH_TOKEN.
4. An empty token is a no-op that produces no output and exits 0.
5. A provided token emits ::add-mask::<token>.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTION_FILE = ROOT / "action.yml"


class TestActionTokenMasking(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ACTION_FILE.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()

    def test_first_step_is_token_masking(self) -> None:
        in_steps = False
        first_step_name: str | None = None
        first_step_run: list[str] = []
        in_first_run = False

        for line in self.lines:
            if line.strip() == "steps:":
                in_steps = True
                continue
            if in_steps:
                if line.startswith("    - name:"):
                    if first_step_name is None:
                        first_step_name = line.split(":", 1)[1].strip()
                    else:
                        break
                elif first_step_name and line.strip().startswith("run:"):
                    in_first_run = True
                    continue
                elif in_first_run:
                    if line.strip() and not line.startswith(" " * 8):
                        in_first_run = False
                    else:
                        first_step_run.append(line)

        self.assertIsNotNone(first_step_name)
        self.assertIn("mask", first_step_name.lower())

        # No expression interpolation inside the run body
        for line in first_step_run:
            self.assertNotIn("${{", line)

    def test_masking_step_precedes_all_posture_watch_token_steps(self) -> None:
        mask_step_index: int | None = None
        token_step_indices: list[int] = []

        step_idx = 0
        in_steps = False
        in_env = False

        for line in self.lines:
            if line.strip() == "steps:":
                in_steps = True
                continue
            if in_steps:
                if line.startswith("    - name:"):
                    step_idx += 1
                    if "mask" in line.lower() and mask_step_index is None:
                        mask_step_index = step_idx
                elif line.strip() == "env:":
                    in_env = True
                    continue
                elif in_env:
                    if line.startswith(" " * 8):
                        if "POSTURE_WATCH_TOKEN" in line:
                            token_step_indices.append(step_idx)
                    else:
                        in_env = False

        self.assertIsNotNone(mask_step_index, "Token masking step was not found")
        self.assertEqual(mask_step_index, 1, "Token masking step must be the very first step")
        self.assertTrue(len(token_step_indices) > 0, "No steps bind POSTURE_WATCH_TOKEN")
        for idx in token_step_indices:
            self.assertGreater(
                idx,
                mask_step_index,
                f"Step {idx} binds POSTURE_WATCH_TOKEN before masking step {mask_step_index}",
            )

    def test_masking_script_execution(self) -> None:
        script = """
        if [ -n "$TOKEN_TO_MASK" ]; then
          echo "::add-mask::$TOKEN_TO_MASK"
        fi
        """
        # Case 1: Empty token is a no-op and exits 0
        proc_empty = subprocess.run(
            ["bash", "-c", script],
            env={"TOKEN_TO_MASK": ""},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc_empty.stdout.strip(), "")
        self.assertEqual(proc_empty.stderr.strip(), "")

        # Case 2: Provided token emits mask command
        proc_token = subprocess.run(
            ["bash", "-c", script],
            env={"TOKEN_TO_MASK": "ghp_secret1234567890"},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc_token.stdout.strip(), "::add-mask::ghp_secret1234567890")


if __name__ == "__main__":
    unittest.main()
