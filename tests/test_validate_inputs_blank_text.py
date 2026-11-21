#!/usr/bin/env python3
"""The pre-flight has to treat a value that is blank after trimming as empty.

`check_text_input()` guards the title and the label with `if not value`, which is true only for
the empty string. A title of two spaces is truthy, so it walks past every check in `validate()`
and reaches `sync_issue.py`, where `find_issue()` searches the open issues for it, matches
nothing, and the run takes the create branch. The API then either rejects a blank title on an
exit that names no input, or opens an issue whose title renders as nothing and which the next
run cannot adopt.

The refusal is the whole fix. The value is not trimmed on its way through: the action passes
what the operator wrote, and a guard that silently rewrote it would be publishing a different
title than the one that was checked.
"""

from __future__ import annotations

import unittest

from test_validate_inputs import Harness


class TestBlankText(Harness):
    def problems(self, err: str) -> list[str]:
        return [line.removeprefix("  - ") for line in err.splitlines() if line.startswith("  - ")]

    def test_a_title_of_spaces_is_refused(self) -> None:
        code, out, err = self.run_cli(title="  ")
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertIn("title must not be blank", err)

    def test_a_label_of_spaces_is_refused(self) -> None:
        code, _, err = self.run_cli(issue_label="   ")
        self.assertEqual(code, 2, err)
        self.assertIn("issue-label must not be blank", err)

    def test_a_tab_only_value_is_blank(self) -> None:
        # A tab is not in the control-character class this script already refuses, and it is
        # not a newline either, so before this guard it passed every check in the file.
        code, _, err = self.run_cli(title="\t")
        self.assertEqual(code, 2, err)
        self.assertEqual(self.problems(err), ["title must not be blank"])

    def test_a_mixed_whitespace_value_is_refused_once(self) -> None:
        # `  \n ` carries a line break, which the guard below it also refuses. Reporting both
        # would tell the operator to fix two things about one input, so blank returns first.
        code, _, err = self.run_cli(title="  \n ")
        self.assertEqual(code, 2, err)
        self.assertEqual(self.problems(err), ["title must not be blank"])

    def test_the_empty_string_keeps_its_own_message(self) -> None:
        code, _, err = self.run_cli(title="")
        self.assertEqual(code, 2, err)
        self.assertIn("title must not be empty", err)
        self.assertNotIn("must not be blank", err)

    def test_blank_is_refused_before_the_length_limit(self) -> None:
        code, _, err = self.run_cli(title=" " * 257)
        self.assertEqual(code, 2, err)
        self.assertEqual(self.problems(err), ["title must not be blank"])

    def test_a_padded_valid_title_still_passes(self) -> None:
        # The guard looks at the value; it does not edit it. An operator who typed the title
        # with a stray space around it gets a run, and the issue carries what they wrote.
        code, _, err = self.run_cli(title=" Account posture watch ")
        self.assertEqual(code, 0, err)

    def test_a_blank_title_and_a_blank_label_are_two_lines(self) -> None:
        code, _, err = self.run_cli(title="  ", issue_label=" ")
        self.assertEqual(code, 2, err)
        self.assertEqual(
            self.problems(err),
            ["issue-label must not be blank", "title must not be blank"],
        )

    def test_a_valid_policy_still_passes_with_a_plain_title(self) -> None:
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
