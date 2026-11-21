"""Issue #57: fenced() must escape pipes before wrapping in backticks.

In GFM an unescaped pipe inside a code span still ends the table cell, so a rule id or
account id containing '|' would add columns and shift later cells. The fix is to replace
'|' with '\\|' before the backtick substitution so the two replacements do not interfere.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402


class TestFencedPipes(unittest.TestCase):
    """fenced() escapes pipes and backticks without double-escaping."""

    def test_pipe_escaped(self) -> None:
        result = render_report.fenced("a|b")
        self.assertIn(r"\|", result)
        self.assertNotIn("|", result.replace(r"\|", ""))

    def test_pipe_escaped_before_backticks(self) -> None:
        """The escaped pipe must appear inside the backtick wrapper."""
        result = render_report.fenced("a|b")
        self.assertTrue(result.startswith("`"))
        self.assertTrue(result.endswith("`"))
        inner = result[1:-1]
        self.assertIn(r"\|", inner)

    def test_plain_rule_id_unchanged(self) -> None:
        result = render_report.fenced("flag-drift")
        self.assertEqual(result, "`flag-drift`")

    def test_backticks_still_escaped(self) -> None:
        result = render_report.fenced("a`b")
        self.assertIn("&#96;", result)
        self.assertNotIn("``", result)

    def test_pipe_and_backtick_together(self) -> None:
        result = render_report.fenced("a|b`c")
        self.assertIn(r"\|", result)
        self.assertIn("&#96;", result)

    def test_pipe_in_rule_id_gives_one_row(self) -> None:
        """A rule id with '|' must render as a single five-cell table row."""
        import json
        import subprocess
        import tempfile

        # Build a minimal report with a rule_id that contains a pipe.
        report = {
            "tool_version": "0.1.0-dev",
            "network": "Test SDF Network ; September 2015",
            "ledger": 1,
            "accounts": [
                {
                    "snapshot": {
                        "id": "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP",
                        "ledger": 1,
                        "thresholds": {"low": 0, "medium": 0, "high": 0},
                        "signers": [],
                        "balances": [],
                        "flags": {},
                    },
                    "findings": [
                        {
                            "rule_id": "flag-drift|injected",
                            "severity": "high",
                            "account": "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP",
                            "message": "test",
                            "fingerprint": "a" * 64,
                            "accepted": False,
                        }
                    ],
                }
            ],
            "exit_code": 1,
            "limits": "none",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            rpt = tmpdir / "report.json"
            rpt.write_text(json.dumps(report), encoding="utf-8")
            out = tmpdir / "body.md"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_report.py"),
                    "--report",
                    str(rpt),
                    "--out",
                    str(out),
                    "--as-of",
                    "2026-11-13",
                    "--config",
                    "gauge.toml",
                    "--gauge-ref",
                    "da656733fff839d5cf20f795460f4365a7254257",
                    "--exit-code",
                    "1",
                ],
                check=True,
                capture_output=True,
            )
            body = out.read_text(encoding="utf-8")

        rows = [ln for ln in body.splitlines() if ln.startswith("| high |")]
        self.assertGreaterEqual(len(rows), 1, "Expected at least 1 row, got none")
        for row in rows:
            # Remove escaped pipes before counting structural delimiters.
            structural_pipes = row.replace(r"\|", "").count("|")
            self.assertEqual(structural_pipes, 6, f"Row has wrong cell count: {row!r}")

    def test_pipe_in_row_marker_still_decodes(self) -> None:
        """A rendered body whose rule id has a pipe must carry a decodable state marker."""
        import base64
        import json
        import subprocess
        import tempfile

        report = {
            "tool_version": "0.1.0-dev",
            "network": "Test SDF Network ; September 2015",
            "ledger": 1,
            "accounts": [
                {
                    "snapshot": {
                        "id": "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP",
                        "ledger": 1,
                        "thresholds": {"low": 0, "medium": 0, "high": 0},
                        "signers": [],
                        "balances": [],
                        "flags": {},
                    },
                    "findings": [
                        {
                            "rule_id": "rule|with|pipes",
                            "severity": "warn",
                            "account": "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP",
                            "message": "msg",
                            "fingerprint": "b" * 64,
                            "accepted": False,
                        }
                    ],
                }
            ],
            "exit_code": 1,
            "limits": "none",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            rpt = tmpdir / "report.json"
            rpt.write_text(json.dumps(report), encoding="utf-8")
            out = tmpdir / "body.md"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_report.py"),
                    "--report",
                    str(rpt),
                    "--out",
                    str(out),
                    "--as-of",
                    "2026-11-13",
                    "--config",
                    "gauge.toml",
                    "--gauge-ref",
                    "da656733fff839d5cf20f795460f4365a7254257",
                    "--exit-code",
                    "1",
                ],
                check=True,
                capture_output=True,
            )
            body = out.read_text(encoding="utf-8")

        import re

        marker_m = re.search(r"<!-- posture-watch:state v1 ([A-Za-z0-9_-]*) -->", body)
        self.assertIsNotNone(marker_m, "state marker missing")
        payload_b64 = marker_m.group(1)  # type: ignore[union-attr]
        padding = "=" * (-len(payload_b64) % 4)
        entries = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["rule"], "rule|with|pipes")


if __name__ == "__main__":
    unittest.main()
