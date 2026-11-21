#!/usr/bin/env python3
"""Tests asserting .github/workflows/ci.yml runs python 3.11 and 3.12 matrix with exact check name.

Issue #87 / Roadmap 9.10.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class TestWorkflowsPythonMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_matrix_contains_311_and_312(self) -> None:
        self.assertIn('python-version: ["3.11", "3.12"]', self.text)

    def test_name_expression_preserves_required_check(self) -> None:
        expected = (
            "${{ matrix.python-version == '3.11' && 'ci / python' || "
            "format('ci / python ({0})', matrix.python-version) }}"
        )
        self.assertIn(expected, self.text)

    def test_setup_python_reads_matrix(self) -> None:
        self.assertIn("python-version: ${{ matrix.python-version }}", self.text)

    def test_no_step_duplication(self) -> None:
        # Exactly one setup-python step
        setup_count = self.text.count("uses: actions/setup-python@")
        self.assertEqual(setup_count, 1)


if __name__ == "__main__":
    unittest.main()
