#!/usr/bin/env python3
"""Focused tests for issue #63: each specific boolean value that must be refused.

`test_workflows_boolean_inputs.py` covers the general pattern and the shell
integration.  This file proves each concrete rejected value — `True`, `yes`, `1` —
individually, so a check that only guards one spelling cannot slip through.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts import validate_inputs

ROOT = Path(__file__).resolve().parent.parent
PIN = "da656733fff839d5cf20f795460f4365a7254257"


class BooleanChecker(unittest.TestCase):
    def run_validator(self, *options: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = validate_inputs.main(
                ["--config", "example/gauge.toml", "--gauge-ref", PIN, *options]
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_refused(self, name: str, value: str) -> None:
        code, stdout, stderr = self.run_validator(f"--{name}={value}")
        self.assertEqual(code, 2, f"expected exit 2 for {name}={value!r}")
        self.assertEqual(stdout, "")
        self.assertIn("validate_inputs: refused\n", stderr)
        self.assertIn(f"{name} must be true or false, got {value}\n", stderr)

    def assert_accepted(self, name: str, value: str) -> None:
        code, _, stderr = self.run_validator(f"--{name}={value}")
        self.assertEqual(code, 0, f"expected exit 0 for {name}={value!r}; stderr: {stderr}")


class TestDryRunBooleanValues(BooleanChecker):
    def test_dry_run_True_is_refused(self) -> None:
        self.assert_refused("dry-run", "True")

    def test_dry_run_yes_is_refused(self) -> None:
        self.assert_refused("dry-run", "yes")

    def test_dry_run_1_is_refused(self) -> None:
        self.assert_refused("dry-run", "1")

    def test_dry_run_true_is_accepted(self) -> None:
        self.assert_accepted("dry-run", "true")

    def test_dry_run_false_is_accepted(self) -> None:
        self.assert_accepted("dry-run", "false")


class TestUpdateOnNoChangeBooleanValues(BooleanChecker):
    def test_update_on_no_change_yes_is_refused(self) -> None:
        self.assert_refused("update-on-no-change", "yes")

    def test_update_on_no_change_True_is_refused(self) -> None:
        self.assert_refused("update-on-no-change", "True")

    def test_update_on_no_change_1_is_refused(self) -> None:
        self.assert_refused("update-on-no-change", "1")

    def test_update_on_no_change_true_is_accepted(self) -> None:
        self.assert_accepted("update-on-no-change", "true")

    def test_update_on_no_change_false_is_accepted(self) -> None:
        self.assert_accepted("update-on-no-change", "false")


class TestBreakBuildBooleanValues(BooleanChecker):
    def test_break_build_1_is_refused(self) -> None:
        self.assert_refused("break-build", "1")

    def test_break_build_True_is_refused(self) -> None:
        self.assert_refused("break-build", "True")

    def test_break_build_yes_is_refused(self) -> None:
        self.assert_refused("break-build", "yes")

    def test_break_build_true_is_accepted(self) -> None:
        self.assert_accepted("break-build", "true")

    def test_break_build_false_is_accepted(self) -> None:
        self.assert_accepted("break-build", "false")


if __name__ == "__main__":
    unittest.main()
