#!/usr/bin/env python3
"""Tests for scripts/check_action.py.

The checker guards the two rules a reviewer can miss in a diff of `action.yml` and a runner
will not complain about until the workflow has already run with the caller's token: an
expression reaching a shell, and a step that is not pinned by commit sha. So the cases here
are mutations of a small valid action file, each one expected to break exactly the rule it
names, plus the real `action.yml` as the case that must stay green.

Nothing here reaches the network, installs a package or parses YAML: the checker is text
scanning on purpose, and so is this suite.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_action  # noqa: E402

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"

GOOD = """name: Test posture watch
description: A minimal action with the shape the checker expects.

inputs:
  gauge-ref:
    description: Full commit sha.
    required: true
  config:
    description: Policy path.
    required: false
    default: gauge.toml
  github-token:
    description: Token for the issue API.
    required: false
    default: ${{ github.token }}

outputs:
  exit-code:
    description: Gauge's exit code.
    value: ${{ steps.audit.outputs.exit-code }}

runs:
  using: composite
  steps:
    - name: Check the inputs
      shell: bash
      env:
        CONFIG: ${{ inputs.config }}
        GAUGE_REF: ${{ inputs.gauge-ref }}
      run: |
        echo "$CONFIG" "$GAUGE_REF"

    - name: Fetch Gauge
      uses: %s
      with:
        persist-credentials: false

    - name: Run the audit
      id: audit
      shell: bash
      run: |
        echo "exit-code=0" >> "$GITHUB_OUTPUT"
""".replace("%s", CHECKOUT)


class Checker(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write(self, text: str) -> Path:
        path = self.tmp / "action.yml"
        path.write_text(text, encoding="utf-8")
        return path

    def problems(self, text: str) -> list[str]:
        return check_action.check(self.write(text))

    def mentions(self, problems: list[str], needle: str) -> list[str]:
        return [line for line in problems if needle in line]

    def test_valid_file_has_no_problems(self) -> None:
        self.assertEqual(self.problems(GOOD), [])

    def test_the_shipped_action_holds(self) -> None:
        self.assertEqual(check_action.check(ROOT / "action.yml"), [])

    def test_empty_file_is_refused(self) -> None:
        problems = self.problems("")
        self.assertEqual(len(problems), 1)
        self.assertIn("is empty", problems[0])

    def test_missing_file_is_refused(self) -> None:
        problems = check_action.check(self.tmp / "nope.yml")
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read it", problems[0])

    def test_inputs_block_missing(self) -> None:
        text = GOOD.replace("inputs:\n", "not_inputs:\n")
        self.assertTrue(self.mentions(self.problems(text), "names no input"))

    def test_gauge_ref_needs_to_exist(self) -> None:
        text = re.sub(r"  gauge-ref:\n(    .*\n)+", "", GOOD)
        self.assertTrue(self.mentions(self.problems(text), "gauge-ref is not declared"))

    def test_gauge_ref_must_be_required(self) -> None:
        text = GOOD.replace(
            "    description: Full commit sha.\n    required: true",
            "    description: Full commit sha.\n    required: false",
        )
        self.assertTrue(self.mentions(self.problems(text), "must be required: true"))

    def test_gauge_ref_must_have_no_default(self) -> None:
        text = GOOD.replace("    required: true\n", "    required: true\n    default: main\n")
        self.assertTrue(self.mentions(self.problems(text), "no default"))

    def test_input_expression_in_a_run_block_is_refused(self) -> None:
        text = GOOD.replace('        echo "$CONFIG"', '        echo "${{ inputs.config }}"')
        problems = self.problems(text)
        self.assertTrue(self.mentions(problems, "reaches the shell"))
        self.assertTrue(any("line " in line for line in problems))

    def test_any_expression_in_a_run_block_is_refused(self) -> None:
        # The rule is about inputs, but the check refuses any expression in a run block: the
        # caller's workflow file is not the thing that was reviewed, and a github.* value can
        # carry a branch name or a title straight into a shell.
        text = GOOD.replace('        echo "$CONFIG"', '        echo "${{ github.ref_name }}"')
        self.assertTrue(self.mentions(self.problems(text), "reaches the shell"))

    def test_undeclared_input_used_in_run(self) -> None:
        text = GOOD.replace(
            'echo "$CONFIG"', 'echo "$GITHUB_ACTION_PATH" --x "${{ inputs.extra }}"'
        )
        problems = self.problems(text)
        self.assertTrue(self.mentions(problems, "extra is used in a run: block"))

    def test_declared_input_never_bound(self) -> None:
        extra = "  fail-on:\n    description: Severity.\n    required: false\n    default: high\n"
        text = GOOD.replace("  config:\n", f"{extra}  config:\n")
        self.assertTrue(self.mentions(self.problems(text), "fail-on is declared but never bound"))

    def test_github_token_is_exempt_from_binding(self) -> None:
        # It arrives through the step's env in the real action, but as a credential it is the
        # one input the checker does not require a step to name. Removing every other binding
        # leaves only github-token unused, and that alone must not be a problem.
        config_block = (
            "  config:\n    description: Policy path.\n"
            "    required: false\n    default: gauge.toml\n"
        )
        text = (
            GOOD.replace(config_block, "")
            .replace("        CONFIG: ${{ inputs.config }}\n", "")
            .replace('echo "$CONFIG" "$GAUGE_REF"', 'echo "$GAUGE_REF"')
        )
        self.assertEqual(self.problems(text), [])

    def test_unpinned_action_is_refused(self) -> None:
        text = GOOD.replace(CHECKOUT, "actions/checkout@v7.0.1")
        self.assertTrue(self.mentions(self.problems(text), "not pinned by a full 40-character"))

    def test_pinned_action_without_a_comment_is_refused(self) -> None:
        text = GOOD.replace(CHECKOUT, CHECKOUT.split(" #")[0])
        self.assertTrue(self.mentions(self.problems(text), "no comment naming the release"))

    def test_short_sha_is_refused(self) -> None:
        short = CHECKOUT.replace("3d3c42e5aac5ba805825da76410c181273ba90b1", "3d3c42e")
        self.assertTrue(self.mentions(self.problems(GOOD.replace(CHECKOUT, short)), "not pinned"))

    def test_local_action_is_allowed(self) -> None:
        step = f"      uses: {CHECKOUT}\n      with:\n        persist-credentials: false\n"
        self.assertEqual(self.problems(GOOD.replace(step, "      uses: ./\n")), [])

    def test_output_naming_a_missing_step_is_refused(self) -> None:
        text = GOOD.replace("steps.audit.outputs", "steps.nobody.outputs")
        self.assertTrue(self.mentions(self.problems(text), "no step in the file carries"))

    def test_every_problem_reports_in_one_pass(self) -> None:
        text = GOOD.replace(CHECKOUT, "actions/checkout@v7").replace(
            "    required: true\n", "    required: false\n"
        )
        problems = self.problems(text)
        self.assertEqual(len(problems), 2, problems)

    def test_main_exit_codes(self) -> None:
        errors = io.StringIO()
        good = self.write(GOOD)
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            self.assertEqual(check_action.main([str(good)]), 0)
        broken = self.write(GOOD.replace(CHECKOUT, "actions/checkout@v7"))
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            self.assertEqual(check_action.main([str(broken)]), 2)
        self.assertIn("breaks 1 rule", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
