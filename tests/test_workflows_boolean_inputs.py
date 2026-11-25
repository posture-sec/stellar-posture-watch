from __future__ import annotations

import io
import os
import subprocess
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts import validate_inputs

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "action.yml"
PIN = "da656733fff839d5cf20f795460f4365a7254257"
BOOLEAN_INPUTS = ("break-build", "dry-run", "update-on-no-change")


class TestBooleanInputs(unittest.TestCase):
    def run_validator(self, *options: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = validate_inputs.main(
                ["--config", "example/gauge.toml", "--gauge-ref", PIN, *options]
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_invalid_values_are_refused(self) -> None:
        for name in BOOLEAN_INPUTS:
            for value in ("yes", "True", "1", "", "-unexpected", " true", "false "):
                with self.subTest(name=name, value=value):
                    code, stdout, stderr = self.run_validator(f"--{name}={value}")
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("validate_inputs: refused\n", stderr)
                    self.assertIn(f"{name} must be true or false, got {value}\n", stderr)

    def test_true_and_false_are_accepted(self) -> None:
        for name in BOOLEAN_INPUTS:
            for value in ("true", "false"):
                with self.subTest(name=name, value=value):
                    code, _, stderr = self.run_validator(f"--{name}={value}")
                    self.assertEqual(code, 0, stderr)

    def test_invalid_booleans_are_reported_together(self) -> None:
        code, _, stderr = self.run_validator(
            "--break-build=yes", "--dry-run=True", "--update-on-no-change=1"
        )
        self.assertEqual(code, 2)
        for name, value in zip(BOOLEAN_INPUTS, ("yes", "True", "1"), strict=True):
            self.assertIn(f"{name} must be true or false, got {value}\n", stderr)

    def test_omitted_booleans_default_to_false(self) -> None:
        args = validate_inputs.parse_args([])
        for name in BOOLEAN_INPUTS:
            with self.subTest(name=name):
                self.assertEqual(getattr(args, name.replace("-", "_")), "false")
        code, _, stderr = self.run_validator()
        self.assertEqual(code, 0, stderr)

    def test_action_binds_and_passes_all_booleans_before_gauge_checkout(self) -> None:
        action = ACTION.read_text(encoding="utf-8")
        check_start = action.index("    - name: Check the inputs\n")
        checkout_start = action.index("    - name: Fetch the pinned Gauge commit\n")
        self.assertLess(check_start, checkout_start)
        step = action[check_start:].split("\n    - name:", 1)[0]
        env, run = step.split("      run: |\n", 1)
        self.assertNotIn("\n      if:", env)
        self.assertNotIn("\n      continue-on-error:", env)
        for name in BOOLEAN_INPUTS:
            variable = name.upper().replace("-", "_")
            with self.subTest(name=name):
                self.assertIn(f"{variable}: ${{{{ inputs.{name} }}}}", env)
                self.assertIn(f'--{name}="${variable}"', run)
        self.assertNotIn("${{", run)

    def test_break_build_yes_fails_in_the_actual_check_step(self) -> None:
        action = ACTION.read_text(encoding="utf-8")
        step = action.split("    - name: Check the inputs\n", 1)[1].split("\n    - name:", 1)[0]
        script = textwrap.dedent(step.split("      run: |\n", 1)[1])
        env = {
            "PATH": os.environ["PATH"],
            "GITHUB_ACTION_PATH": str(ROOT),
            "CONFIG": "example/gauge.toml",
            "GAUGE_REPO": "posture-sec/guage",
            "GAUGE_REF": PIN,
            "FAIL_ON": "high",
            "ISSUE_LABEL": "account-posture",
            "TITLE": "Account posture watch",
            "BREAK_BUILD": "yes",
            "DRY_RUN": "true",
            "UPDATE_ON_NO_CHANGE": "false",
            "OUTPUT_FORMAT": "markdown",
            "MODE": "schedule",
        }
        result = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            result.stderr,
            "validate_inputs: refused\n  - break-build must be true or false, got yes\n",
        )


if __name__ == "__main__":
    unittest.main()
