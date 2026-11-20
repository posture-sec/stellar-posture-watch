#!/usr/bin/env python3
"""Tests asserting watch.yml stays local (uses: ./) while example/workflow.yml stays pinned.

Issue #89 / Roadmap 9.8.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH_WORKFLOW = ROOT / ".github" / "workflows" / "watch.yml"
EXAMPLE_WORKFLOW = ROOT / "example" / "workflow.yml"


def validate_watch_reference(text: str) -> None:
    """Validate watch.yml action reference is strictly local."""
    if "posture-sec/stellar-posture-watch@" in text:
        raise ValueError("watch.yml must not reference a published remote repository")
    match = re.search(r"uses:\s*\./\s*", text)
    if not match:
        raise ValueError("watch.yml must use the local action reference 'uses: ./'")


def validate_example_reference(text: str) -> None:
    """Validate example/workflow.yml action reference is pinned, not local or tagged."""
    if "uses: ./" in text:
        raise ValueError("example/workflow.yml must not use local action reference 'uses: ./'")
    refs = re.findall(r"uses:\s*posture-sec/stellar-posture-watch@(\S+)", text)
    if len(refs) != 1:
        raise ValueError(
            f"example/workflow.yml must contain exactly 1 action ref, found {len(refs)}"
        )
    ref = refs[0]
    if ref.startswith("v") or ref.startswith("main"):
        raise ValueError(f"example/workflow.yml must not use a mutable tag: {ref}")
    # Must be placeholder or 40-hex commit
    valid_placeholders = {"<commit-sha>", "REPLACE-WITH-A-SHA-YOU-READ"}
    if ref not in valid_placeholders and not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError(f"example/workflow.yml ref must be placeholder or 40-hex: {ref}")


class TestWorkflowsLocalVsPinned(unittest.TestCase):
    def setUp(self) -> None:
        self.watch_text = WATCH_WORKFLOW.read_text(encoding="utf-8")
        self.example_text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")

    def test_watch_workflow_is_local(self) -> None:
        validate_watch_reference(self.watch_text)

    def test_example_workflow_is_pinned(self) -> None:
        validate_example_reference(self.example_text)

    def test_watch_mutation_published_ref_fails(self) -> None:
        mutated = self.watch_text.replace(
            "uses: ./",
            "uses: posture-sec/stellar-posture-watch@da656733fff839d5cf20f795460f4365a7254257",
        )
        with self.assertRaises(ValueError):
            validate_watch_reference(mutated)

    def test_example_mutation_local_ref_fails(self) -> None:
        mutated = re.sub(
            r"uses:\s*posture-sec/stellar-posture-watch@\S+",
            "uses: ./",
            self.example_text,
        )
        with self.assertRaises(ValueError):
            validate_example_reference(mutated)

    def test_example_mutation_tag_ref_fails(self) -> None:
        mutated = re.sub(
            r"uses:\s*posture-sec/stellar-posture-watch@\S+",
            "uses: posture-sec/stellar-posture-watch@v0.1.0",
            self.example_text,
        )
        with self.assertRaises(ValueError):
            validate_example_reference(mutated)


if __name__ == "__main__":
    unittest.main()
