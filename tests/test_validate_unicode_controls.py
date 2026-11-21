#!/usr/bin/env python3
"""Tests for issue #71: refuse bidi and zero-width characters in title and label.

`CONTROL_CHARS` is an ASCII range, so it passes Unicode category Cf untouched. A title
carrying U+202E RIGHT-TO-LEFT OVERRIDE renders differently from the bytes the workflow
file holds, and a zero-width joiner makes two titles that compare equal look different on
the issue list. In a repository whose whole product is one scheduled write into a trusted
issue, the rendered title is the thing an operator reads, so a refusal belongs here.

The rule is by category, not by alphabet: accented Latin and non-Latin scripts are Lo/Lu/Ll
and must pass. The renderer is a separate surface and keeps its deliberate zero-width break.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402
import validate_inputs  # noqa: E402

PIN = "da656733fff839d5cf20f795460f4365a7254257"
ACCOUNT = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"

POLICY = f"""version = 1
network = "testnet"
endpoints = ["https://horizon-test-stellar.org"]

[[account]]
id = "{ACCOUNT}"
name = "treasury"
"""

# Each entry is (character, code point, Unicode name). All four are category Cf: they carry
# no glyph and change the direction or the width of what follows them.
INVISIBLE = [
    ("‮", 0x202E, "RIGHT-TO-LEFT OVERRIDE"),
    ("​", 0x200B, "ZERO WIDTH SPACE"),
    ("‍", 0x200D, "ZERO WIDTH JOINER"),
    ("⁦", 0x2066, "LEFT-TO-RIGHT ISOLATE"),
]

# Cc outside ASCII: a C1 control, invisible in the same way and missed by an ASCII range.
C1_CONTROL = ("\x85", 0x85, "NEXT LINE")

VISIBLE_NON_LATIN = [
    "Café treasury watch",  # accented Latin
    "账户监控",  # Han
    "Εποπτεία λογαριασμού",  # Greek
    "مراقبة الحساب",  # Arabic, with no bidi override character
    "Ñoño — café",  # tilde-n, en dash, combining-free accented e
]


def _strings(node: object) -> list[str]:
    """Every string in a decoded report, however deeply nested."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [item for value in node.values() for item in _strings(value)]
    if isinstance(node, list):
        return [item for value in node for item in _strings(value)]
    return []


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self._prior = Path.cwd()
        os.chdir(self._directory.name)
        Path("gauge.toml").write_text(POLICY, encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self._prior)
        self._directory.cleanup()

    def run_cli(self, **overrides: Any) -> tuple[int, str, str]:
        args: dict[str, Any] = {
            "config": "gauge.toml",
            "gauge_repo": "posture-sec/guage",
            "gauge_ref": PIN,
            "fail_on": "high",
            "issue_label": "account-posture",
            "title": "Account posture watch",
        }
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


class TestTitleRefusals(Harness):
    def test_each_invisible_character_is_refused_by_code_point_in_the_title(self) -> None:
        for char, point, name in INVISIBLE:
            with self.subTest(char=name):
                code, _, err = self.run_cli(title=f"Treasury {char}watch")
                self.assertEqual(code, 2, err)
                self.assertIn(f"U+{point:04X}", err)
                self.assertIn(name, err)

    def test_a_c1_control_outside_the_ascii_range_is_refused(self) -> None:
        char, point, _ = C1_CONTROL
        code, _, err = self.run_cli(title=f"Treasury{char}watch")
        self.assertEqual(code, 2, err)
        self.assertIn(f"U+{point:04X}", err)
        # C1 controls have no Unicode name to quote, so the category is what the message
        # has to carry.
        self.assertIn("category Cc", err)

    def test_a_leading_override_is_refused_not_only_an_embedded_one(self) -> None:
        code, _, err = self.run_cli(title="‮Account posture watch")
        self.assertEqual(code, 2, err)
        self.assertIn("U+202E", err)


class TestLabelRefusals(Harness):
    def test_the_same_characters_are_refused_in_the_label(self) -> None:
        for char, point, name in INVISIBLE:
            with self.subTest(char=name):
                code, _, err = self.run_cli(issue_label=f"account{char}-posture")
                self.assertEqual(code, 2, err)
                self.assertIn("issue-label", err)
                self.assertIn(f"U+{point:04X}", err)


class TestVisibleTextPasses(Harness):
    def test_accented_and_non_latin_titles_still_pass(self) -> None:
        for title in VISIBLE_NON_LATIN:
            with self.subTest(title=title):
                code, _, err = self.run_cli(title=title)
                self.assertEqual(code, 0, err)

    def test_the_ascii_control_and_newline_refusal_is_untouched(self) -> None:
        code, _, err = self.run_cli(issue_label="account\nposture")
        self.assertEqual(code, 2, err)
        self.assertIn("control character or a line break", err)


class TestHelperContract(unittest.TestCase):
    def test_the_helper_names_the_first_offender_only(self) -> None:
        described = validate_inputs.invisible_character("ab‮​cd")
        self.assertIsNotNone(described)
        self.assertIn("U+202E", described)
        self.assertNotIn("U+200B", described)

    def test_the_helper_is_silent_on_empty_and_plain_text(self) -> None:
        self.assertIsNone(validate_inputs.invisible_character(""))
        self.assertIsNone(validate_inputs.invisible_character("Account posture watch"))
        self.assertIsNone(validate_inputs.invisible_character("账户监控"))


class TestRendererKeepsItsOwnZeroWidthSpace(unittest.TestCase):
    """The validator refuses these characters; the renderer writes one on purpose.

    `escape()` breaks a mention with U+200B so a hostile `home_domain` cannot notify a user
    (`CONTRIBUTING.md` records that), and that behaviour must survive this change. The two
    surfaces have opposite jobs: one is an Action input the operator typed, the other is
    chain-derived text headed for markdown. A test that only looked at the validator would
    not tell them apart, so the hostile fixture is checked here as well.
    """

    def test_a_mention_is_still_broken_with_the_zero_width_entity(self) -> None:
        escaped = render_report.escape("@here")
        self.assertIn("@&#8203;", escaped)

    def test_the_hostile_fixture_values_still_render_with_the_break(self) -> None:
        path = ROOT / "tests" / "fixtures" / "report-hostile-strings.json"
        report = render_report.read_report(path)
        rendered = [render_report.escape(value) for value in _strings(report)]
        broken = [text for text in rendered if "&#8203;" in text]
        self.assertTrue(
            broken,
            "the fixture carries mentions and the renderer must still break them",
        )
        # The break is an entity, not a raw Cf character written into the body.
        for text in broken:
            self.assertNotIn("​", text)

    def render_fixture(self) -> bytes:
        """The hostile fixture through the CLI, exactly as `action.yml` runs it."""
        fixture = ROOT / "tests" / "fixtures" / "report-hostile-strings.json"
        with TemporaryDirectory() as workspace:
            argv = [
                sys.executable,
                str(ROOT / "scripts" / "render_report.py"),
                "--report",
                str(fixture),
                "--out",
                f"{workspace}/body.md",
                "--summary-out",
                f"{workspace}/summary.json",
                "--as-of",
                "2026-11-03",
                "--config",
                "policy.toml",
                "--gauge-ref",
                PIN,
                "--exit-code",
                str(json.loads(fixture.read_text(encoding="utf-8"))["exit_code"]),
            ]
            done = subprocess.run(argv, capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            return Path(f"{workspace}/body.md").read_bytes()

    def test_the_hostile_fixture_renders_byte_for_byte_as_it_did_before(self) -> None:
        """A digest, because "the renderer did not move" is a claim about bytes.

        Issue #71 touches the validator, so the body the renderer writes for the hostile
        fixture has to be the same sequence it was before this change. An edit that moved the
        zero-width break, the escaping or the row order changes this hash, and it changes it
        here rather than silently in a scheduled issue body.
        """
        digest = hashlib.sha256(self.render_fixture()).hexdigest()
        self.assertEqual(
            digest,
            "0e3c716348aeae44ea7c316fc9a4f1de2482dddd2c99fe8914042357e20b1432",
        )


if __name__ == "__main__":
    unittest.main()
