#!/usr/bin/env python3
"""Property and fuzz tests for render_report.py using stdlib only.

No hypothesis or other third-party library. Each test drives a randomly seeded
set of hostile inputs through the render path and asserts structural invariants
that must hold for every output the action would put in an issue body.
"""

from __future__ import annotations

import json
import os
import random
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
SEED = int(os.environ.get("PROPERTY_TEST_SEED", "42"))
ITERATIONS = int(os.environ.get("PROPERTY_TEST_ITERS", "30"))

# Characters that are meaningful in GitHub-flavoured markdown
HOSTILE_CHARS = "\\*_[]<>#|~`&@\x00\x01\x07\x08\x0b\x1f\x7f‮​‍⁦"


def hostile_string(rng: random.Random, length: int = 20) -> str:
    chars = list(HOSTILE_CHARS) + list("abcdefghijklmnopqrstuvwxyz0123456789 _-")
    return "".join(rng.choice(chars) for _ in range(length))


def make_report(
    rng: random.Random,
    *,
    n_findings: int = 0,
    exit_code: int = 0,
) -> dict:
    account_id = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"
    findings = []
    for _ in range(n_findings):
        fp = "".join(rng.choice("0123456789abcdef") for _ in range(64))
        findings.append(
            {
                "severity": rng.choice(("high", "warn")),
                "fingerprint": fp,
                "rule_id": hostile_string(rng, 8),
                "message": hostile_string(rng, 40),
                "accepted": False,
            }
        )
    return {
        "tool_version": f"v{rng.randint(0, 9)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}",
        "network": "testnet",
        "ledger": rng.randint(1_000_000, 9_000_000),
        "exit_code": exit_code,
        "limits": hostile_string(rng, 60),
        "accounts": [
            {
                "snapshot": {
                    "id": account_id,
                    "ledger": rng.randint(1_000_000, 9_000_000),
                    "thresholds": {"low": 1, "medium": 2, "high": 3},
                    "flags": {"auth_required": False},
                    "signers": [],
                    "balances": [],
                    "home_domain": hostile_string(rng, 15),
                },
                "findings": findings,
            }
        ],
    }


class PropertyHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._rng = random.Random(SEED)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write_report(self, data: dict, name: str = "report.json") -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def render_from_dict(self, data: dict) -> tuple[str, dict]:
        import argparse

        path = self.write_report(data)
        args = argparse.Namespace(
            report=str(path),
            out=str(self.tmp / "body.md"),
            previous_body="",
            as_of="2026-11-21",
            config="gauge.toml",
            gauge_repo="posture-sec/guage",
            gauge_ref="da656733fff839d5cf20f795460f4365a7254257",
            fail_on="high",
            exit_code=data["exit_code"],
            max_state_entries=200,
            summary_out="",
        )
        body, summary = render_report.render(args)
        return body, summary


class TestBodyInvariantsOverHostileInputs(PropertyHarness):
    def test_body_always_carries_the_state_marker(self) -> None:
        for _ in range(ITERATIONS):
            n = self._rng.randint(0, 10)
            data = make_report(self._rng, n_findings=n, exit_code=1 if n else 0)
            body, _ = self.render_from_dict(data)
            self.assertIn(render_report.MARKER_PREFIX, body)

    def test_body_never_exceeds_the_issue_limit(self) -> None:
        for _ in range(ITERATIONS):
            n = self._rng.randint(0, 50)
            data = make_report(self._rng, n_findings=n, exit_code=1 if n else 0)
            body, _ = self.render_from_dict(data)
            self.assertLessEqual(
                len(body),
                render_report.BODY_LIMIT,
                f"body of {len(body)} chars with {n} findings",
            )

    def test_hostile_message_does_not_break_the_state_marker(self) -> None:
        for _ in range(ITERATIONS):
            data = make_report(self._rng, n_findings=5, exit_code=1)
            body, _ = self.render_from_dict(data)
            decoded = render_report.decode_state(body)
            self.assertIsNotNone(decoded, "state marker could not be decoded")

    def test_hostile_home_domain_cannot_close_the_state_comment(self) -> None:
        for _ in range(ITERATIONS):
            data = make_report(self._rng, n_findings=2, exit_code=1)
            for account in data["accounts"]:
                snap = account.get("snapshot", {})
                snap["home_domain"] = "-->" + hostile_string(self._rng, 10)
            body, _ = self.render_from_dict(data)
            decoded = render_report.decode_state(body)
            self.assertIsNotNone(decoded, "state marker not decodable after hostile home_domain")


class TestSummaryInvariantsOverHostileInputs(PropertyHarness):
    def test_summary_counts_are_consistent(self) -> None:
        for _ in range(ITERATIONS):
            n_high = self._rng.randint(0, 5)
            n_warn = self._rng.randint(0, 5)
            data = make_report(
                self._rng, n_findings=n_high + n_warn, exit_code=1 if (n_high + n_warn) else 0
            )
            # Force severities to match counts
            for i, finding in enumerate(data["accounts"][0]["findings"]):
                finding["severity"] = "high" if i < n_high else "warn"
            _, summary = self.render_from_dict(data)
            self.assertEqual(summary["high"] + summary["warn"], summary["open"])


if __name__ == "__main__":
    unittest.main()
