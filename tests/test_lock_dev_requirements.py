#!/usr/bin/env python3
"""Tests for scripts/lock_dev_requirements.py.

The generator's network half is not exercised here, which is the point: the staleness
check has to decide from the two files alone, so a bumped pin fails in CI before anything
is installed. The module is loaded by path because `scripts/` is not a package.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "lock_dev_requirements.py"

_spec = importlib.util.spec_from_file_location("lock_dev_requirements", SCRIPT)
assert _spec and _spec.loader
lock_dev = importlib.util.module_from_spec(_spec)
sys.modules["lock_dev_requirements"] = lock_dev
_spec.loader.exec_module(lock_dev)


class Staleness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.write_text(text)
        return path

    def lock(self, *pairs: str) -> Path:
        """A lock file from `name==version` pairs, one hash each."""
        text = "".join(
            f"{pair} \\\n    --hash=sha256:{index:02d}\n" for index, pair in enumerate(pairs)
        )
        return self.write("lock.txt", text)

    def test_a_lock_matching_the_pins_is_current(self) -> None:
        requirements = self.write("req.txt", "ruff==0.17.3\nmypy==2.4.0\n")
        lock = self.lock("ruff==0.17.3", "mypy==2.4.0")
        self.assertEqual(lock_dev.stale(requirements, lock), [])

    def test_a_bumped_pin_without_a_regenerated_lock_is_stale(self) -> None:
        requirements = self.write("req.txt", "ruff==0.18.0\n")
        lock = self.lock("ruff==0.17.3")
        problems = lock_dev.stale(requirements, lock)
        self.assertEqual(len(problems), 1)
        self.assertIn("ruff==0.18.0 is not in the lock", problems[0])

    def test_a_missing_lock_is_stale(self) -> None:
        requirements = self.write("req.txt", "ruff==0.17.3\n")
        problems = lock_dev.stale(requirements, self.tmp / "absent.txt")
        self.assertEqual(len(problems), 1)

    def test_a_pin_with_no_hash_is_stale(self) -> None:
        requirements = self.write("req.txt", "ruff==0.17.3\n")
        lock = self.write("lock.txt", "ruff==0.17.3\n")
        self.assertIn("at least one pin carries no hash", lock_dev.stale(requirements, lock))

    def test_transitive_pins_are_allowed(self) -> None:
        requirements = self.write("req.txt", "mypy==2.4.0\n")
        lock = self.lock("mypy==2.4.0", "typing_extensions==4.16.0")
        self.assertEqual(lock_dev.stale(requirements, lock), [])

    def test_underscore_and_hyphen_names_are_the_same_package(self) -> None:
        requirements = self.write("req.txt", "mypy-extensions==1.2.0\n")
        lock = self.lock("mypy_extensions==1.2.0")
        self.assertEqual(lock_dev.stale(requirements, lock), [])

    def test_the_committed_lock_covers_the_committed_pins(self) -> None:
        problems = lock_dev.stale(ROOT / "requirements-dev.txt", ROOT / "requirements-dev.lock.txt")
        self.assertEqual(problems, [])

    def test_every_committed_pin_is_exact(self) -> None:
        for name, version in lock_dev.pinned(ROOT / "requirements-dev.txt"):
            self.assertRegex(version, r"^\d+\.\d+\.\d+$", f"{name} is not pinned to a version")


if __name__ == "__main__":
    unittest.main()
