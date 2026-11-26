#!/usr/bin/env python3
"""Tests that a line ending in chain-written text cannot end a markdown table row.

``escape`` used to pass CR and LF through, so ``example.org\\n## Account verified``
in a home domain rendered as a row that stopped early followed by a level-2 heading
no renderer wrote (tests/fixtures/README.md:33).  Every break now collapses to the
single space it stood for, in ``escape`` and in ``fenced``, which is what a cell has
to do to stay a cell.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOSTILE = "example.org{}\\#\\# Account verified"
sys.path.insert(0, str(ROOT / "scripts"))
from render_report import account_rows, cell, escape, fenced, finding_rows  # type: ignore[import-not-found]  # noqa: E402


class TestBreakCollapse(unittest.TestCase):
    def test_line_feed_becomes_one_space(self) -> None:
        self.assertEqual(escape("example.org\n## Account verified"), HOSTILE.format(" "))

    def test_carriage_return_becomes_one_space(self) -> None:
        self.assertEqual(escape("example.org\r## Account verified"), HOSTILE.format(" "))

    def test_crlf_becomes_one_space(self) -> None:
        self.assertEqual(escape("example.org\r\n## Account verified"), HOSTILE.format(" "))

    def test_run_of_breaks_collapses_to_a_single_space(self) -> None:
        self.assertEqual(escape("a\n\n\n b"), "a b")
        self.assertEqual(escape("a\r\r b"), "a b")
        self.assertEqual(escape("a \r\n\t b"), "a b")

    def test_trailing_and_leading_breaks_leave_a_padded_value(self) -> None:
        self.assertEqual(escape("\n a \n"), " a ")

    def test_no_break_is_untouched(self) -> None:
        self.assertEqual(escape("example.org"), "example.org")

    def test_fenced_collapses_breaks_inside_the_backticks(self) -> None:
        self.assertEqual(fenced("GAB\n## Account verified"), "`GAB ## Account verified`")

    def test_fenced_still_neutralises_backticks(self) -> None:
        self.assertEqual(fenced("a`b\nc"), "`a&#96;b c`")

    def test_cell_collapses_breaks(self) -> None:
        self.assertEqual(cell("m\nn"), "m n")


class TestRowsStayRows(unittest.TestCase):
    def test_a_break_in_a_message_does_not_add_a_row(self) -> None:
        findings = [
            {
                "account": "GABC",
                "fingerprint": "a" * 64,
                "message": "first\n## Account verified",
                "rule": "r1",
                "severity": "warn",
            }
        ]
        rows = finding_rows(findings).strip().splitlines()
        self.assertEqual(len(rows), 3)  # header, separator, one finding
        self.assertNotIn("\n", rows[2])
        self.assertIn("first \\#\\# Account verified", rows[2])

    def test_a_break_in_a_home_domain_does_not_add_a_row(self) -> None:
        accounts = [
            {
                "id": "GABC",
                "snapshot": {
                    "ledger": 1,
                    "thresholds": {"low": 1, "medium": 0, "high": 0},
                    "signers": [],
                    "balances": [],
                    "flags": {},
                    "home_domain": "example.org\n## Account verified",
                },
            }
        ]
        rows = account_rows({"accounts": accounts}).strip().splitlines()
        self.assertEqual(len(rows), 3)  # header, separator, one account
        self.assertIn("example.org \\#\\# Account verified", rows[2])


if __name__ == "__main__":
    unittest.main()
