#!/usr/bin/env python3
"""Tests for issue #55: every fixture in the provenance table is opened by a test."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
FIXTURES = TESTS / "fixtures"


def _fixture_names_in_tests() -> set[str]:
    pattern = re.compile(r"\breport-[A-Za-z0-9_-]+\.json\b")
    skip_re = re.compile(r"\.write_(?:bytes|text)\(|assertIn\(")
    found: set[str] = set()
    for path in TESTS.glob("test_*.py"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if skip_re.search(line):
                continue
            for m in pattern.finditer(line):
                found.add(m.group())
    return found


def _fixtures_on_disk() -> set[str]:
    return {p.name for p in FIXTURES.glob("report-*.json")}


def _fixtures_in_readme() -> set[str]:
    readme = (FIXTURES / "README.md").read_text()
    return set(re.findall(r"^\| `(report-[^`]+\.json)`", readme, re.MULTILINE))


class TestFixtureReachability(unittest.TestCase):
    def test_every_fixture_on_disk_is_opened_by_a_test(self) -> None:
        on_disk = _fixtures_on_disk()
        in_tests = _fixture_names_in_tests()
        unreachable = on_disk - in_tests
        self.assertEqual(
            unreachable, set(), f"fixtures on disk but not opened by any test: {unreachable}"
        )

    def test_every_fixture_named_in_a_test_exists_on_disk(self) -> None:
        on_disk = _fixtures_on_disk()
        in_tests = _fixture_names_in_tests()
        missing = in_tests - on_disk
        self.assertEqual(missing, set(), f"fixtures named in tests but not on disk: {missing}")

    def test_every_fixture_in_the_readme_exists_on_disk(self) -> None:
        on_disk = _fixtures_on_disk()
        in_readme = _fixtures_in_readme()
        missing = in_readme - on_disk
        self.assertEqual(missing, set(), f"fixtures in README but not on disk: {missing}")

    def test_every_fixture_on_disk_is_in_the_readme(self) -> None:
        on_disk = _fixtures_on_disk()
        in_readme = _fixtures_in_readme()
        undocumented = on_disk - in_readme
        self.assertEqual(undocumented, set(), f"fixtures on disk but not in README: {undocumented}")


if __name__ == "__main__":
    unittest.main()
