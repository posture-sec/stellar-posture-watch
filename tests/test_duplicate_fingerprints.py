#!/usr/bin/env python3
"""Tests for issue #51: refuse a report whose open findings repeat a fingerprint.

render() builds current = {fingerprint: finding}. A repeated fingerprint silently
overwrites the earlier entry, so one account drops out of counts, the change list,
and the marker. The fix detects this before the dict is built and exits 2.
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
ACCOUNT_B = "GC2HHIM66CBKJFMYOHECBMKD4NWRGWJ3FEXFDPWPT4TLS7OFR43LO2II"
FP = "c0ffee" + "0" * 58

LIMITS = "Gauge reads public ledger state only."


def _base_report() -> dict:
    return {
        "tool_version": "0.1.0-dev",
        "network": "Test SDF Network ; September 2015",
        "ledger": 100,
        "exit_code": 1,
        "limits": LIMITS,
        "accounts": [
            {
                "snapshot": {"id": ACCOUNT_A, "ledger": 100},
                "findings": [
                    {
                        "rule_id": "flag-drift",
                        "severity": "high",
                        "message": "account A finding",
                        "fingerprint": FP,
                        "accepted": False,
                    }
                ],
            },
            {
                "snapshot": {"id": ACCOUNT_B, "ledger": 100},
                "findings": [],
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

    def render(self, report: dict) -> tuple[int, str, str]:
        import subprocess

        self._calls += 1
        path = self.tmp / f"report{self._calls}.json"
        body = self.tmp / f"body{self._calls}.md"
        path.write_text(json.dumps(report))
        argv = [
            sys.executable,
            str(ROOT / "scripts" / "render_report.py"),
            "--report",
            str(path),
            "--out",
            str(body),
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
        return done.returncode, body.read_text() if body.exists() else "", done.stderr


class TestDuplicateFingerprints(Harness):
    def test_same_fingerprint_in_two_accounts_exits_2(self) -> None:
        report = _base_report()
        report["accounts"][1]["findings"] = [
            {
                "rule_id": "other-rule",
                "severity": "warn",
                "message": "account B finding",
                "fingerprint": FP,
                "accepted": False,
            }
        ]
        code, body, err = self.render(report)
        self.assertEqual(code, 2, f"expected exit 2, got {code}; stderr={err!r}")
        self.assertEqual(body, "", "no body must be written on a refusal")

    def test_refusal_line_names_fingerprint_and_both_indexes(self) -> None:
        report = _base_report()
        report["accounts"][1]["findings"] = [
            {
                "rule_id": "other-rule",
                "severity": "warn",
                "message": "account B finding",
                "fingerprint": FP,
                "accepted": False,
            }
        ]
        _, _, err = self.render(report)
        self.assertIn("accounts[0]", err)
        self.assertIn("accounts[1]", err)
        self.assertIn(FP, err)

    def test_unique_fingerprints_across_accounts_renders_fine(self) -> None:
        report = _base_report()
        report["accounts"][1]["findings"] = [
            {
                "rule_id": "other-rule",
                "severity": "warn",
                "message": "account B different finding",
                "fingerprint": "d" * 64,
                "accepted": False,
            }
        ]
        report["exit_code"] = 1
        code, _, err = self.render(report)
        self.assertEqual(code, 0, f"unique fingerprints must render fine; stderr={err!r}")

    def test_within_account_duplicate_is_also_refused(self) -> None:
        report = _base_report()
        report["accounts"][0]["findings"].append(
            {
                "rule_id": "flag-drift",
                "severity": "warn",
                "message": "second finding same fp",
                "fingerprint": FP,
                "accepted": False,
            }
        )
        code, body, err = self.render(report)
        self.assertEqual(code, 2, f"within-account duplicate must also be refused; stderr={err!r}")
        self.assertEqual(body, "")


if __name__ == "__main__":
    unittest.main()
