#!/usr/bin/env python3
"""Tests for issue #52: accepted findings are keyed on fingerprint alone, not rule_id.

split_accepted() used to build accepted_keys as (str(rule_id), str(fingerprint)).
An accept entry with a different rule_id never matched, so the finding appeared as
open. ARCHITECTURE.md 2 now says fingerprint alone drives accepted-key matching.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"

ACCOUNT_A = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"
FP = "aabbcc" + "0" * 58

LIMITS = "Gauge reads public ledger state only."


def _report(*, rule_in_findings: str, rule_in_accepted: str) -> dict:
    """
    One account with one finding whose fingerprint is FP, accepted=True,
    but with potentially different rule_ids in the finding vs. what the accept entry used.

    Since the accept flag lives on the finding itself in this fixture format,
    we model the mismatch by having two findings with the same fingerprint:
    one with accepted=True under rule_in_accepted and one with accepted=False
    under rule_in_findings. The accepted entry drives accepted_keys; the open
    entry is what must be classified correctly.

    Actually the fixture format has a single finding entry with both rule_id and
    accepted flag. The mismatch scenario is: finding has rule_id=X and accepted=True,
    but we also test whether a finding with rule_id=Y and the same fingerprint would
    be accepted.

    The simplest test: two accounts, account[0] has the finding with accepted=True
    and rule_id=rule_in_accepted; account[1] has the same fingerprint with accepted=False
    and rule_id=rule_in_findings. The fix should mark account[1]'s finding as accepted
    since the fingerprint matches.
    """
    return {
        "tool_version": "0.1.0-dev",
        "network": "Test SDF Network ; September 2015",
        "ledger": 100,
        "exit_code": 1,
        "limits": LIMITS,
        "accounts": [
            {
                "snapshot": {"id": ACCOUNT_A},
                "findings": [
                    {
                        "rule_id": rule_in_accepted,
                        "severity": "high",
                        "message": "accepted finding",
                        "fingerprint": FP,
                        "accepted": True,
                    }
                ],
            },
        ],
    }


ACCOUNT_B = "GC2HHIM66CBKJFMYOHECBMKD4NWRGWJ3FEXFDPWPT4TLS7OFR43LO2II"


def _two_account_report(*, accepted_rule: str, open_rule: str) -> dict:
    return {
        "tool_version": "0.1.0-dev",
        "network": "Test SDF Network ; September 2015",
        "ledger": 100,
        "exit_code": 1,
        "limits": LIMITS,
        "accounts": [
            {
                "snapshot": {"id": ACCOUNT_A},
                "findings": [
                    {
                        "rule_id": accepted_rule,
                        "severity": "high",
                        "message": "accepted entry",
                        "fingerprint": FP,
                        "accepted": True,
                    }
                ],
            },
            {
                "snapshot": {"id": ACCOUNT_B},
                "findings": [
                    {
                        "rule_id": open_rule,
                        "severity": "high",
                        "message": "this finding has the same fingerprint",
                        "fingerprint": FP,
                        "accepted": False,
                    }
                ],
            },
        ],
    }


class Harness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._calls = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def render(self, report: dict) -> tuple[int, str, dict, str]:
        import subprocess

        self._calls += 1
        path = self.tmp / f"report{self._calls}.json"
        body = self.tmp / f"body{self._calls}.md"
        summary = self.tmp / f"summary{self._calls}.json"
        path.write_text(json.dumps(report))
        argv = [
            sys.executable,
            str(ROOT / "scripts" / "render_report.py"),
            "--report",
            str(path),
            "--out",
            str(body),
            "--summary-out",
            str(summary),
            "--as-of",
            "2026-11-03",
            "--config",
            "policy.toml",
            "--gauge-ref",
            PIN,
            "--exit-code",
            str(report["exit_code"]),
        ]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        data: dict = {}
        if summary.exists() and done.returncode == 0:
            data = json.loads(summary.read_text())
        return done.returncode, body.read_text() if body.exists() else "", data, done.stderr


class TestAcceptedKeyFingerprint(Harness):
    def test_accepted_flag_on_finding_accepts_it(self) -> None:
        report = _report(rule_in_findings="acct-missing", rule_in_accepted="acct-missing")
        code, body, summary, err = self.render(report)
        self.assertEqual(code, 0, err)
        self.assertEqual(summary.get("open"), 0)
        self.assertEqual(summary.get("accepted"), 1)
        self.assertIn("## Accepted in the policy", body)

    def test_same_fingerprint_different_rule_is_still_accepted(self) -> None:
        """A finding with the same fingerprint but a different rule_id must be accepted."""
        report = _two_account_report(accepted_rule="old-rule-id", open_rule="new-rule-id")
        code, body, summary, err = self.render(report)
        self.assertEqual(code, 0, err)
        self.assertEqual(summary.get("open"), 0, "finding must be accepted, not open")
        self.assertEqual(summary.get("accepted"), 2)
        self.assertIn("## Accepted in the policy", body)
        current = body.split("## Current findings")[1].split("##")[0]
        self.assertIn("None.", current, "current findings section must be empty")

    def test_different_fingerprint_stays_open(self) -> None:
        report = {
            "tool_version": "0.1.0-dev",
            "network": "Test SDF Network ; September 2015",
            "ledger": 100,
            "exit_code": 1,
            "limits": LIMITS,
            "accounts": [
                {
                    "snapshot": {"id": ACCOUNT_A},
                    "findings": [
                        {
                            "rule_id": "flag-drift",
                            "severity": "high",
                            "message": "open finding",
                            "fingerprint": "e" * 64,
                            "accepted": False,
                        }
                    ],
                }
            ],
        }
        code, _, summary, err = self.render(report)
        self.assertEqual(code, 0, err)
        self.assertEqual(summary.get("open"), 1)
        self.assertEqual(summary.get("accepted"), 0)


if __name__ == "__main__":
    unittest.main()
