#!/usr/bin/env python3
"""Tests asserting .github/workflows/self-check.yml scopes are strictly read-only.

Issue #96 / Roadmap 9.11.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF_CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "self-check.yml"


def parse_self_check_permissions(text: str) -> dict[str, str]:
    """Parse top-level permissions block without YAML parser."""
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
    if not in_perm:
        raise ValueError("permissions: block is missing in self-check.yml")
    return perms


def check_no_write_scope(text: str) -> None:
    """Ensure no write scope appears in permissions block and flag line number."""
    lines = text.splitlines()
    in_perm = False
    for idx, line in enumerate(lines, 1):
        if line.startswith("permissions:"):
            in_perm = True
            continue
        if in_perm:
            if line and not line.startswith("  "):
                break
            if "write" in line:
                raise ValueError(f"Line {idx} in self-check.yml grants write permission: {line}")


class TestSelfCheckPermissions(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SELF_CHECK_WORKFLOW.read_text(encoding="utf-8")

    def test_permissions_are_read_only(self) -> None:
        perms = parse_self_check_permissions(self.text)
        expected = {
            "contents": "read",
            "issues": "read",
        }
        self.assertEqual(perms, expected)
        check_no_write_scope(self.text)

    def test_comment_states_read_only_invariant(self) -> None:
        self.assertIn("Read-only permissions:", self.text)
        expected = "Elevated permissions (such as issues: write) are strictly forbidden"
        self.assertIn(expected, self.text)

    def test_write_scope_mutation_fails(self) -> None:
        mutated = self.text.replace("issues: read", "issues: write")
        with self.assertRaises(ValueError) as ctx:
            check_no_write_scope(mutated)
        self.assertIn("grants write permission", str(ctx.exception))

    def test_missing_permissions_block_fails(self) -> None:
        mutated = "\n".join(
            line
            for line in self.text.splitlines()
            if not line.startswith("permissions:")
            and "contents: read" not in line
            and "issues: read" not in line
        )
        with self.assertRaises(ValueError):
            parse_self_check_permissions(mutated)


if __name__ == "__main__":
    unittest.main()
