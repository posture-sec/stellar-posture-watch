#!/usr/bin/env python3
"""The renderer's own body ceiling (task 9.19).

An over-limit report has to leave the issue body under the API limit, name how many
finding rows it left out, and keep the state marker last and decodable. A body that
already fits is rendered unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_report.py"
FIXTURES = ROOT / "tests" / "fixtures"
PIN = "da656733fff839d5cf20f795460f4365a7254257"
MARKER_PREFIX = "<!-- posture-watch:state v1 "
MARKER_SUFFIX = " -->"

sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402


def over_limit_report(path: Path, accounts: int = 3, per_account: int = 120) -> None:
    """A synthetic report whose rendered body is far past the ceiling.

    Built from the fixture's own envelope so every required field is the real shape;
    only accounts and findings are multiplied.
    """
    base = json.loads((FIXTURES / "report-findings.json").read_text(encoding="utf-8"))
    template = base["accounts"][0]["snapshot"]
    message = "a chain-written message that is long enough to matter " * 5
    base["accounts"] = []
    for a in range(accounts):
        snapshot = dict(template)
        snapshot["id"] = f"G{'A' * 10}{a:02d}{'B' * 44}"
        findings = []
        for f in range(per_account):
            digest = hashlib.sha256(f"{a}-{f}".encode()).hexdigest()
            findings.append(
                {
                    "rule_id": "acct-missing",
                    "severity": "high",
                    "fingerprint": digest,
                    "message": message,
                }
            )
        base["accounts"].append({"snapshot": snapshot, "findings": findings})
    path.write_text(json.dumps(base), encoding="utf-8")


class BodySize(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self.calls = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def render(self, report: Path, previous: Path | None = None) -> tuple[int, str, dict[str, Any]]:
        self.calls += 1
        body = self.tmp / f"body{self.calls}.md"
        summary = self.tmp / f"summary{self.calls}.json"
        payload = json.loads(report.read_text(encoding="utf-8"))
        argv = [
            sys.executable,
            str(SCRIPT),
            "--report",
            str(report),
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
            str(payload["exit_code"]),
        ]
        if previous is not None:
            argv += ["--previous-body", str(previous)]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        data: dict[str, Any] = {}
        if summary.exists() and done.returncode == 0:
            data = json.loads(summary.read_text(encoding="utf-8"))
        text = body.read_text(encoding="utf-8") if body.exists() else ""
        return done.returncode, text, data

    def test_an_over_limit_report_is_cut_to_the_ceiling(self) -> None:
        report = self.tmp / "large.json"
        over_limit_report(report)
        code, body, summary = self.render(report)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(body), render_report.BODY_LIMIT)
        self.assertGreater(summary.get("dropped", 0), 0)

    def test_the_notice_names_the_rows_it_left_out(self) -> None:
        report = self.tmp / "large.json"
        over_limit_report(report)
        _, body, summary = self.render(report)
        dropped = summary["dropped"]
        self.assertIn(f"{dropped} finding row(s) were left out", body)
        self.assertIn("the state marker still carries the full open set", body)

    def test_the_marker_stays_last_and_decodable(self) -> None:
        report = self.tmp / "large.json"
        over_limit_report(report)
        _, body, _ = self.render(report)
        lines = [line for line in body.splitlines() if line.strip()]
        self.assertTrue(lines[-1].startswith(MARKER_PREFIX), lines[-1][:80])
        self.assertTrue(lines[-1].endswith(MARKER_SUFFIX))
        encoded = lines[-1][len(MARKER_PREFIX) : -len(MARKER_SUFFIX)]
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        self.assertIsInstance(decoded, list)
        self.assertTrue(decoded, "the marker must keep the open set it was handed")

    def test_a_body_under_the_ceiling_is_rendered_unchanged(self) -> None:
        code, body, summary = self.render(FIXTURES / "report-findings.json")
        self.assertEqual(code, 0)
        self.assertLess(len(body), render_report.BODY_LIMIT)
        self.assertNotIn("were left out", body)
        self.assertNotIn("dropped", summary)
        self.assertEqual(render_report.fit_body(body), (body, 0))

    def test_fit_body_leaves_a_short_document_alone(self) -> None:
        text = "| high | `rule` | `acct` | `abc` | message |\n"
        self.assertEqual(render_report.fit_body(text), (text, 0))


if __name__ == "__main__":
    unittest.main()
