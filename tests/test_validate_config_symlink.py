#!/usr/bin/env python3
"""Tests for issue #69: `check_config_path()` must resolve before it accepts.

The lexical checks read the string; a symlink is not a string. A committed link at the
default config name can point outside the checkout, and `exists()`/`is_file()` follow it,
so the old code accepted it and `action.yml` handed the target to Gauge as `--config`.
`SECURITY.md` states the confinement promise these three cases hold.

The harness runs the CLI from inside a temporary workspace, the way the Action runs it from
inside a checkout, and every test skips where `os.symlink` is unavailable rather than
passing a platform it cannot exercise.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_inputs  # noqa: E402

PIN = "da656733fff839d5cf20f795460f4365a7254257"
ACCOUNT = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"

POLICY = f"""version = 1
network = "testnet"
endpoints = ["https://horizon-testnet.stellar.org"]

[[account]]
id = "{ACCOUNT}"
name = "treasury"
"""


class Harness(unittest.TestCase):
    """Runs the CLI with the temporary directory as the workspace."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self._outside = TemporaryDirectory()
        self._prior = Path.cwd()
        os.chdir(self._directory.name)
        self.workspace = Path(self._directory.name)
        self.outside = Path(self._outside.name)

    def tearDown(self) -> None:
        os.chdir(self._prior)
        self._outside.cleanup()
        self._directory.cleanup()

    def need_symlink(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("this platform has no os.symlink")

    def write_policy(self, name: str = "gauge.toml") -> str:
        Path(name).write_text(POLICY, encoding="utf-8")
        return name

    def run_cli(self, **overrides: Any) -> tuple[int, str, str]:
        args: dict[str, Any] = {
            "gauge_repo": "posture-sec/guage",
            "gauge_ref": PIN,
            "fail_on": "high",
            "issue_label": "account-posture",
            "title": "Account posture watch",
        }
        # Only when the test did not name a config: writing gauge.toml over a symlink the
        # case just created would follow the link and create its target instead of testing it.
        if "config" not in overrides:
            args["config"] = self.write_policy()
        args.update(overrides)
        argv = [
            "--config",
            str(args["config"]),
            "--gauge-repo",
            str(args["gauge_repo"]),
            "--gauge-ref",
            str(args["gauge_ref"]),
            "--fail-on",
            str(args["fail_on"]),
            "--issue-label",
            str(args["issue_label"]),
            "--title",
            str(args["title"]),
        ]
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = validate_inputs.main(argv)
        return code, out.getvalue(), err.getvalue()


class TestSymlinkEscape(Harness):
    def test_a_link_out_of_the_workspace_is_refused_and_names_its_target(self) -> None:
        self.need_symlink()
        target = Path(self._outside.name) / "outside.toml"
        target.write_text(POLICY, encoding="utf-8")
        Path("gauge.toml").symlink_to(target)

        code, _, err = self.run_cli(config="gauge.toml")

        self.assertEqual(code, 2, err)
        self.assertIn("outside the workspace", err)
        self.assertIn(str(target.resolve()), err)
        # One refusal, not one per check: the escape is decided before anything is read.
        self.assertEqual(len([line for line in err.splitlines() if line.startswith("  - ")]), 1)

    def test_a_link_that_lands_in_the_workspace_still_passes(self) -> None:
        self.need_symlink()
        self.write_policy("real-gauge.toml")
        Path("gauge.toml").symlink_to("real-gauge.toml")

        code, out, err = self.run_cli(config="gauge.toml")

        self.assertEqual(code, 0, err)
        self.assertIn("config gauge.toml parsed", out)

    def test_a_nested_link_that_climbs_out_is_refused(self) -> None:
        """The escape does not have to be one hop: `..` is refused in the given string, not
        in the resolved one, so a link two directories in can still land outside."""
        self.need_symlink()
        nested = self.workspace / "config"
        nested.mkdir()
        outside_file = Path(self._outside.name) / "climber.toml"
        outside_file.write_text(POLICY, encoding="utf-8")
        (nested / "gauge.toml").symlink_to(outside_file)

        code, _, err = self.run_cli(config=str(Path("config") / "gauge.toml"))

        self.assertEqual(code, 2, err)
        self.assertIn("outside the workspace", err)
        self.assertIn(str(outside_file.resolve()), err)


class TestDanglingSymlink(Harness):
    def test_a_dangling_link_says_it_cannot_be_resolved_not_that_it_is_missing(self) -> None:
        self.need_symlink()
        Path("gauge.toml").symlink_to("gone.toml")

        code, _, err = self.run_cli(config="gauge.toml")

        self.assertEqual(code, 2, err)
        self.assertIn("cannot be resolved", err)
        self.assertNotIn("does not exist", err)

    def test_a_plain_missing_file_still_reports_that_it_does_not_exist(self) -> None:
        code, _, err = self.run_cli(config="nowhere.toml")

        self.assertEqual(code, 2, err)
        self.assertIn("does not exist in the workspace", err)
        self.assertNotIn("cannot be resolved", err)


class TestNonFileStillRefused(Harness):
    def test_a_directory_symlink_is_not_a_regular_file(self) -> None:
        self.need_symlink()
        Path("configs").mkdir()
        Path("gauge.toml").symlink_to("configs")

        code, _, err = self.run_cli(config="gauge.toml")

        self.assertEqual(code, 2, err)
        self.assertIn("is not a regular file", err)


class TestResolverIsUsedOnce(Harness):
    def test_a_link_to_a_file_inside_hands_on_the_target_not_the_link(self) -> None:
        """`check_config_path()` resolves once and hands on the canonical target, so
        `check_policy()` reads the inode the check accepted instead of re-following the link.

        The handover stays relative to the workspace: the containment check proved the target
        is inside it, and every refusal message names the policy the way the operator wrote it
        rather than the runner's checkout path.
        """
        self.need_symlink()
        real = self.write_policy("real-gauge.toml")
        Path("gauge.toml").symlink_to(real)

        handed_on = validate_inputs.check_config_path("gauge.toml", [])

        self.assertIsNotNone(handed_on)
        assert handed_on is not None
        self.assertEqual(handed_on, Path("real-gauge.toml"))
        self.assertFalse(handed_on.is_symlink(), "the path handed on is still a link")
        self.assertEqual(os.stat(handed_on).st_ino, os.stat(real).st_ino)


if __name__ == "__main__":
    unittest.main()
