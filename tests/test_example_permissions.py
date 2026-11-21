#!/usr/bin/env python3
"""Tests asserting example/workflow.yml permissions map is minimal and exact.

Issue #86 / Roadmap 9.9.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "example" / "workflow.yml"


def parse_workflow_permissions(text: str) -> dict[str, str]:
    """Parse top-level permissions block from workflow text without YAML parser."""
    lines = text.splitlines()
    in_perm = False
    perms: dict[str, str] = {}
    for line in lines:
        if line.startswith("permissions:"):
            in_perm = True
            continue
        if in_perm:
            if line and not line.startswith("  "):
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                perms[k.strip()] = v.strip()
    return perms


def check_for_job_permissions(text: str) -> list[str]:
    """Check if any job declares a permissions block."""
    lines = text.splitlines()
    in_jobs = False
    violations: list[str] = []
    for idx, line in enumerate(lines, 1):
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if in_jobs and (line.startswith("    permissions:") or line.startswith("  permissions:")):
            violations.append(f"Line {idx}: {line}")
    return violations


class TestExamplePermissions(unittest.TestCase):
    def setUp(self) -> None:
        self.text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_level_permissions_exact(self) -> None:
        perms = parse_workflow_permissions(self.text)
        expected = {
            "contents": "read",
            "issues": "write",
        }
        self.assertEqual(perms, expected)

    def test_no_job_permissions(self) -> None:
        violations = check_for_job_permissions(self.text)
        self.assertEqual(violations, [])

    def test_third_key_or_write_all_rejected(self) -> None:
        # Verify parser detects unexpected keys or write-all
        bad_sample1 = "permissions:\n  contents: read\n  issues: write\n  pull-requests: write\n"
        perms1 = parse_workflow_permissions(bad_sample1)
        self.assertNotEqual(perms1, {"contents": "read", "issues": "write"})
        self.assertIn("pull-requests", perms1)

        bad_sample2 = "permissions: write-all\n"
        perms2 = parse_workflow_permissions(bad_sample2)
        self.assertNotEqual(perms2, {"contents": "read", "issues": "write"})


if __name__ == "__main__":
    unittest.main()
