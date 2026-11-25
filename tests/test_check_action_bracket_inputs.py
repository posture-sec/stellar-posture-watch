#!/usr/bin/env python3
"""Tests for bracket input references in `scripts/check_action.py` (#79).

`INPUT_REF` matched `${{ inputs.name }}` and nothing else, but the runner reads
`${{ inputs['name'] }}` and `${{ inputs["name"] }}` as the same expression. A binding written in
brackets therefore contributed no binding, and the rule that every declared input has to reach a
step reported the input as never bound — a refusal the file answers by doing the thing it is
accused of not doing. Inside a `run:` block the effect was the opposite: the generic expression
refusal fired but named nothing, so the input that reached the shell stayed out of the message.

Each case puts one spelling in one place and asks for the finding that belongs there. The dot
form is included because a widened pattern must not start excusing it.

Nothing here reaches the network or parses YAML, same as the checker.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import unittest

from action_fixture import GOOD, line_of, mentions, problems

DOT_ENV = "        CONFIG: ${{ inputs.config }}"
BRACKET_ENV = """        CONFIG: ${{ inputs['config'] }}"""
QUOTED_ENV = '        CONFIG: ${{ inputs["config"] }}'
DOT_RUN = '        echo "$CONFIG" "$GAUGE_REF"'
BRACKET_RUN = """        echo "$CONFIG" "${{ inputs['extra'] }}\""""
DECLARED_BRACKET_RUN = """        echo "$CONFIG" "${{ inputs['config'] }}\""""


class BoundThroughBrackets(unittest.TestCase):
    def test_the_dot_form_still_binds(self) -> None:
        # The control: the spelling that already worked keeps working, with no findings.
        self.assertIn(DOT_ENV, GOOD)
        self.assertEqual(problems(GOOD), [])

    def test_single_quotes_bind(self) -> None:
        # Before the pattern grew, this text produced exactly one refusal:
        # `input config is declared but never bound in an env: mapping, so no step receives it`.
        found = problems(GOOD.replace(DOT_ENV, BRACKET_ENV))
        self.assertEqual(mentions(found, "never bound"), [])
        self.assertEqual(found, [])

    def test_double_quotes_bind(self) -> None:
        found = problems(GOOD.replace(DOT_ENV, QUOTED_ENV))
        self.assertEqual(mentions(found, "never bound"), [])
        self.assertEqual(found, [])


class UsedInARunBlock(unittest.TestCase):
    def test_a_bracket_reference_names_the_input_it_reaches(self) -> None:
        found = problems(GOOD.replace(DOT_RUN, BRACKET_RUN))
        self.assertEqual(len(found), 2, found)
        self.assertTrue(mentions(found, "reaches the shell"))
        self.assertTrue(mentions(found, "extra is used in a run: block"))

    def test_the_refusal_carries_the_line_of_the_bracket_expression(self) -> None:
        text = GOOD.replace(DOT_RUN, BRACKET_RUN)
        found = problems(text)
        self.assertEqual(len(mentions(found, f"line {line_of(text, BRACKET_RUN.strip())}")), 1)

    def test_a_declared_input_in_brackets_is_still_refused(self) -> None:
        # Widening what the pattern sees excuses nothing: an input that reaches the shell is a
        # refusal whether or not the file declares it.
        found = problems(GOOD.replace(DOT_RUN, DECLARED_BRACKET_RUN))
        self.assertEqual(len(found), 1, found)
        self.assertIn("reaches the shell", found[0])


if __name__ == "__main__":
    unittest.main()
