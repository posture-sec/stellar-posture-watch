#!/usr/bin/env python3
"""Tests for issue #72: the suite runs on 3.11 and 3.12, and the floor keeps its check name.

`.github/workflows/ci.yml` is the only thing that decides which interpreter the suite ever
sees, and `CONTRIBUTING.md` states 3.11 and 3.12 support. A leg dropped from the matrix, or a
matrix that renames the floor's check, is invisible to every other test in this repository.

The name is load-bearing rather than cosmetic: ruleset 26515104 binds `main` and lists
`ci / python` as a required status check, so a matrix that reports itself as
`ci / python (3.11)` leaves the required check unmatched and `main` unprotected. That is why
the assertion is on the exact string rather than on a prefix.

No YAML dependency: this file text-scans the workflow, the same rule the other workflow tests
follow, so the suite keeps running on the runner's own python3 with nothing installed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DEV_REQUIREMENTS = ROOT / "requirements-dev.txt"

FLOOR = "3.11"
OTHER = "3.12"
REQUIRED_CHECK = "ci / python"


class MatrixText(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CI_WORKFLOW.read_text(encoding="utf-8")


class TestVersions(MatrixText):
    def test_the_matrix_lists_the_floor_and_the_next_minor(self) -> None:
        match = re.search(r"python-version:\s*\[([^\]]*)\]", self.text)
        self.assertIsNotNone(match, "ci.yml declares no python-version list")
        listed = [item.strip().strip("\"'") for item in match.group(1).split(",")]
        self.assertIn(FLOOR, listed)
        self.assertIn(OTHER, listed)
        self.assertGreaterEqual(len(listed), 2, f"only {listed} run the suite")

    def test_renaming_the_floor_out_of_the_matrix_fails_here(self) -> None:
        """The list is read, not pattern-matched loosely: a leg that silently becomes 3.13
        alone is the failure this file exists to catch."""
        mutated = self.text.replace(f'"{FLOOR}",', '"3.13",', 1)
        match = re.search(r"python-version:\s*\[([^\]]*)\]", mutated)
        self.assertNotIn(FLOOR, [item.strip().strip("\"'") for item in match.group(1).split(",")])

    def test_setup_python_reads_the_matrix_rather_than_a_literal(self) -> None:
        self.assertIn("python-version: ${{ matrix.python-version }}", self.text)

    def test_the_suite_runs_once_per_leg(self) -> None:
        self.assertEqual(self.text.count("python -m unittest discover -s tests -t tests"), 1)
        self.assertEqual(self.text.count("uses: actions/setup-python@"), 1)


class TestCheckName(MatrixText):
    def test_the_floor_leg_is_named_exactly_the_required_check(self) -> None:
        expression = re.search(r"name: \$\{\{.*\}\}", self.text)
        self.assertIsNotNone(expression, "the checks job has no computed name")
        rendered = expression.group(0)
        self.assertIn(f"'{REQUIRED_CHECK}'", rendered)
        self.assertIn(f"matrix.python-version == '{FLOOR}'", rendered)

    def test_the_other_leg_gets_a_distinct_name(self) -> None:
        job_name = re.search(r"name: \$\{\{.*\}\}", self.text).group(0)
        self.assertIn("format('ci / python ({0})'", job_name)
        self.assertNotIn(f"'{REQUIRED_CHECK} ({OTHER})'", job_name)
        # The floor must not also carry the parenthesised form, or the required check is gone.
        self.assertNotIn(f"{REQUIRED_CHECK} ({FLOOR})", job_name)


class TestNoGateLoosening(MatrixText):
    def test_the_legs_install_the_pinned_dev_tools(self) -> None:
        self.assertIn("python -m pip install --quiet -r requirements-dev.txt", self.text)

    def test_the_lint_and_type_steps_are_still_present(self) -> None:
        for command in ("ruff check .", "ruff format --check .", "mypy"):
            with self.subTest(command=command):
                self.assertIn(command, self.text)


class TestDevPinsUnchanged(unittest.TestCase):
    def test_requirements_dev_still_names_the_two_pinned_tools(self) -> None:
        text = DEV_REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn("ruff==0.17.3", text)
        self.assertIn("mypy==2.4.0", text)


if __name__ == "__main__":
    unittest.main()
