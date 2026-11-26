#!/usr/bin/env python3
"""Tests that a pipe inside a fenced value cannot end its table cell.

GFM reads an unescaped pipe as a cell boundary even inside a code span, and the hidden
state accepts any string for `rule` and `account` (`decode_state`), so a hand-edited
marker can feed the finding table a value the report never produced. `fenced()` escapes
the pipe, so the row keeps five cells and the cells after it do not shift.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from render_report import fenced  # type: ignore[import-not-found]  # noqa: E402
from test_render_report import ACCOUNT, FIXTURES, MARKER_RE, Renderer  # noqa: E402

CELL_SPLIT = re.compile(r"(?<!\\)\|")


class TestFencedPipes(unittest.TestCase):
    def test_a_pipe_is_escaped_inside_the_backticks(self) -> None:
        self.assertEqual(fenced("a|b"), "`a\\|b`")

    def test_every_pipe_is_escaped(self) -> None:
        self.assertEqual(fenced("a|b|c"), "`a\\|b\\|c`")

    def test_a_normal_rule_id_is_unchanged(self) -> None:
        self.assertEqual(fenced("flag-drift"), "`flag-drift`")
        self.assertEqual(fenced("signer-threshold"), "`signer-threshold`")

    def test_the_pipe_is_escaped_before_the_backtick_is_neutralised(self) -> None:
        self.assertEqual(fenced("a`b|c"), "`a&#96;b\\|c`")

    def test_a_mention_is_still_broken_alongside_the_pipe(self) -> None:
        self.assertEqual(fenced("@all|x"), "`@&#8203;all\\|x`")


class TestRenderedRows(Renderer):
    def _render_with_piped_rule(self) -> tuple[int, str, dict, str]:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        report["exit_code"] = 1
        report["accounts"][0]["findings"] = [
            {
                "rule_id": "flag|drift",
                "severity": "high",
                "account": ACCOUNT,
                "message": "a piped rule",
                "evidence": "x",
                "fingerprint": "a" * 64,
                "accepted": False,
            }
        ]
        path = self.tmp / "piped-rule.json"
        path.write_text(json.dumps(report))
        return self.render(path)

    def test_a_piped_rule_keeps_one_row_and_five_cells(self) -> None:
        code, body, _, err = self._render_with_piped_rule()
        self.assertEqual(code, 0, err)
        self.assertIn("flag\\|drift", body)
        rows = [ln for ln in body.splitlines() if ln.startswith("|") and "flag\\|drift" in ln]
        self.assertEqual(len(set(rows)), 1, "the row must render identically wherever it is listed")
        for row in rows:
            cells = CELL_SPLIT.split(row.strip())[1:-1]
            self.assertEqual(len(cells), 5, row)
            self.assertIn("flag\\|drift", cells[1])

    def test_the_state_marker_still_decodes(self) -> None:
        _, body, _, _ = self._render_with_piped_rule()
        match = MARKER_RE.search(body)
        assert match is not None
        decoded = json.loads(base64.urlsafe_b64decode(match.group(1) + "=="))
        self.assertEqual(decoded[0]["rule"], "flag|drift")


if __name__ == "__main__":
    unittest.main()
