#!/usr/bin/env python3
"""Tests for scripts/render_report.py.

Every assertion runs against a file in tests/fixtures, whose provenance is recorded in
tests/fixtures/README.md, and one test enforces that that README still lists all of them.
"""

from __future__ import annotations

import json
import re
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
ACCOUNT = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"
ABSENT = "GC2HHIM66CBKJFMYOHECBMKD4NWRGWJ3FEXFDPWPT4TLS7OFR43LO2II"
ISSUER = "GDSX2WUFUT7KCMTUNG3IUQWIUQSC4XNKQ5NTGEZRKLTMLCSJTCUVBEVG"
MARKER_RE = re.compile(r"<!-- posture-watch:state v1 ([A-Za-z0-9_-]*) -->")


class Renderer(unittest.TestCase):
    """Runs the script the way the Action does, as a subprocess over temp files."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._calls = 0

    def tearDown(self) -> None:
        self._directory.cleanup()

    def render(
        self,
        fixture: str | Path,
        previous: str | Path | None = None,
        *,
        as_of: str = "2026-11-03",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[int, str, dict[str, Any], str]:
        report = FIXTURES / fixture if not isinstance(fixture, Path) else fixture
        if exit_code is None:
            exit_code = json.loads(report.read_text())["exit_code"]
        self._calls += 1
        body = self.tmp / f"body{self._calls}.md"
        summary = self.tmp / f"summary{self._calls}.json"
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
            as_of,
            "--config",
            "policy.toml",
            "--gauge-ref",
            PIN,
            "--exit-code",
            str(exit_code),
        ]
        if previous is not None:
            argv += ["--previous-body", str(previous)]
        for key, value in (extra or {}).items():
            argv += [f"--{key}", str(value)]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        data: dict[str, Any] = {}
        if summary.exists() and done.returncode == 0:
            data = json.loads(summary.read_text())
        return done.returncode, body.read_text() if body.exists() else "", data, done.stderr

    def fixture_body(self, name: str) -> str:
        _, body, _, _ = self.render(name)
        return body


class TestFirstRun(Renderer):
    def test_a_clean_report_establishes_a_baseline_with_no_findings(self) -> None:
        code, body, summary, err = self.render("report-clean.json")
        self.assertEqual(code, 0, err)
        self.assertIn("This run establishes the baseline", body)
        self.assertIn("No findings open", body)
        self.assertTrue(summary["changed"])
        self.assertEqual(summary["open"], 0)
        self.assertEqual(summary["new"], 0)
        self.assertEqual(summary["as_of"], "2026-11-03")

    def test_a_finding_appears_in_both_the_new_and_current_tables(self) -> None:
        _, body, summary, _ = self.render("report-findings.json")
        self.assertEqual(summary["new"], 1)
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["high"], 1)
        lists = (
            body.split("## Resolved")[0]
            + body.split("## Current findings")[1].split("## Accounts")[0]
        )
        self.assertEqual(lists.count(f"`{ABSENT}`"), 2, "once in New, once in Current")
        self.assertIn("`b03faa6106f2`", body)

    def test_a_warn_report_counts_warn_not_high(self) -> None:
        _, body, summary, _ = self.render("report-warn.json")
        self.assertEqual((summary["warn"], summary["high"]), (1, 0))
        self.assertIn("flag-undeclared-clawback", body)

    def test_a_skipped_account_is_shown_as_not_read(self) -> None:
        _, body, summary, _ = self.render("report-network-mismatch.json")
        self.assertIn("not read: the endpoint is on a different network", body)
        self.assertEqual(summary["open"], 1)
        self.assertIn("acct-network-mismatch", body)

    def test_a_missing_account_does_not_borrow_the_zero_snapshot_as_data(self) -> None:
        _, body, _, _ = self.render("report-findings.json")
        accounts = body.split("## Accounts asked about")[1].split("## What this cannot see")[0]
        row = next(line for line in accounts.splitlines() if ABSENT in line)
        self.assertIn("(not read)", row)
        self.assertNotIn("0/0/0", accounts)
        read_row = next(line for line in accounts.splitlines() if ACCOUNT in line)
        self.assertIn("3/3/3", read_row)
        self.assertIn("5535641", read_row)

    def test_the_limits_footer_survives_verbatim(self) -> None:
        _, body, _, _ = self.render("report-clean.json")
        self.assertIn(
            "> Gauge reads public ledger state only. It cannot see who holds a key,", body
        )
        self.assertIn("not proof that the account cannot be compromised", body)

    def test_a_rendered_body_never_calls_an_account_secure_or_safe(self) -> None:
        # "not safety" is the disclaimer itself, so only the standalone word is refused.
        for name in sorted(p.name for p in FIXTURES.glob("report-*.json")):
            _, body, _, _ = self.render(name)
            self.assertIsNone(re.search(r"\bsecure\w*\b", body, re.IGNORECASE), name)
            self.assertIsNone(re.search(r"\bsafe\b", body, re.IGNORECASE), name)
            self.assertIn("posture", body.lower(), name)

    def test_rendering_the_same_report_twice_gives_the_same_bytes(self) -> None:
        _, first, _, _ = self.render("report-findings.json")
        _, second, _, _ = self.render("report-findings.json")
        self.assertEqual(first, second)

    def test_an_empty_report_list_says_so(self) -> None:
        empty = self.tmp / "empty.json"
        empty.write_text(
            json.dumps(
                {
                    "tool_version": "0.1.0-dev",
                    "network": "Test SDF Network ; September 2015",
                    "ledger": 1,
                    "accounts": [],
                    "exit_code": 0,
                    "limits": "Gauge reads public ledger state only.",
                }
            )
        )
        code, body, summary, err = self.render(empty)
        self.assertEqual(code, 0, err)
        self.assertIn("The report lists no accounts.", body)
        self.assertEqual(summary["open"], 0)


class TestSummaryAccountCounts(Renderer):
    """3.6: an account the run could not read is asked about, not read.

    The first line used to count `report["accounts"]` and call the result "read", so a policy
    naming three accounts of which the endpoint had two printed "across 3 accounts read" above
    a table whose own row says "(not read)". The numerator is the accounts `account_status` calls
    read, which is the function that writes that column; the denominator is every account the
    report carries, read or not.
    """

    def test_the_tail_says_how_many_of_the_asked_were_read(self) -> None:
        cases = [
            ("report-findings.json", "across 1 account read of 2 asked about."),
            ("report-accepted.json", "across 1 account read of 2 asked about."),
            ("report-network-mismatch.json", "across 0 accounts read of 1 asked about."),
            ("report-clean.json", "across 1 account read."),
            ("report-warn.json", "across 1 account read."),
            ("report-hostile-strings.json", "across 1 account read."),
        ]
        for name, tail in cases:
            with self.subTest(fixture=name):
                _, body, _, err = self.render(name)
                first = body.splitlines()[0]
                self.assertTrue(first.endswith(tail), f"{name}: {first!r} {err}")

    def test_no_fixture_that_was_fully_read_borrows_the_denominator(self) -> None:
        for name in ("report-clean.json", "report-warn.json", "report-hostile-strings.json"):
            with self.subTest(fixture=name):
                _, body, _, _ = self.render(name)
                self.assertNotIn("asked about", body.splitlines()[0])

    def test_the_counts_behind_the_sentence_agree_with_the_table(self) -> None:
        _, body, summary, _ = self.render("report-findings.json")
        accounts = body.split("## Accounts asked about")[1].split("## What this cannot see")[0]
        rows = [line for line in accounts.splitlines() if line.startswith("| `")]
        read = [row for row in rows if row.rstrip().endswith("| read |")]
        self.assertEqual(len(read), 1, "one row the table itself calls read")
        self.assertEqual(len(rows), 2, "two accounts were asked about")
        self.assertEqual(summary["open"], 1)
        self.assertIn("across 1 account read of 2 asked about", body.splitlines()[0])

    def test_the_rewritten_sentence_is_not_read_as_changed_posture(self) -> None:
        # D-07: detection keys on the fingerprint, so a body carrying the old wording must
        # still match a fresh render of the same report, marker to marker.
        _, body, _, _ = self.render("report-findings.json")
        old = body.replace("across 1 account read of 2 asked about", "across 2 accounts read", 1)
        self.assertNotEqual(old, body, "the replacement has to have found the sentence")
        previous = self.tmp / "previous.md"
        previous.write_text(old, encoding="utf-8")
        code, again, summary, err = self.render("report-findings.json", previous)
        self.assertEqual(code, 0, err)
        self.assertFalse(summary["changed"])
        fresh, carried = MARKER_RE.search(again), MARKER_RE.search(old)
        if fresh is None or carried is None:
            self.fail("a rendered body carries no state marker")
        self.assertEqual(fresh.group(1), carried.group(1))


class TestAccountsHeading(Renderer):
    """3.7: a section title is a claim about every row underneath it.

    3.6 fixed the summary sentence and left the heading below it, so one body could say
    "across 1 account read of 2 asked about" and then title the same table "## Accounts read"
    above a row whose own Read cell says "(not read)". The section is the set the denominator
    names, so it takes the denominator's word; the Read column is where a run says what
    happened to each account in it.
    """

    @staticmethod
    def accounts_section(body: str) -> tuple[str, list[str]]:
        """The heading above the account table and the data rows beneath it."""
        head = next(
            (line for line in body.splitlines() if line.startswith("## ") and "ccount" in line),
            "",
        )
        if not head:
            return "", []
        before_footer = body.split("## What this cannot see")[0]
        rows = [
            line for line in before_footer.split(head, 1)[1].splitlines() if line.startswith("| `")
        ]
        return head, rows

    def test_the_accounts_heading_names_the_set_the_sentence_counts(self) -> None:
        cases = [
            ("report-findings.json", 2),
            ("report-accepted.json", 2),
            ("report-network-mismatch.json", 1),
            ("report-clean.json", 1),
            ("report-warn.json", 1),
        ]
        for name, asked in cases:
            with self.subTest(fixture=name):
                _, body, _, err = self.render(name)
                head, rows = self.accounts_section(body)
                self.assertEqual("## Accounts asked about", head, f"{name}: {err}")
                self.assertEqual(len(rows), asked, f"{name}: rows {rows}")

    def test_a_heading_may_claim_read_only_if_every_row_under_it_was_read(self) -> None:
        for name in sorted(p.name for p in FIXTURES.glob("report-*.json")):
            with self.subTest(fixture=name):
                _, body, _, _ = self.render(name)
                head, rows = self.accounts_section(body)
                unread = [row for row in rows if not row.rstrip().endswith("| read |")]
                if not unread:
                    continue
                self.assertIsNone(
                    re.search(r"\bread\b", head, re.IGNORECASE),
                    f"{name}: {head!r} titles {len(unread)} row(s) the table does not call read",
                )

    def test_a_row_the_table_calls_not_read_still_appears_under_the_heading(self) -> None:
        _, body, _, _ = self.render("report-findings.json")
        _, rows = self.accounts_section(body)
        unread = [row for row in rows if not row.rstrip().endswith("| read |")]
        self.assertEqual(len(unread), 1, "the absent account is in scope, so it is in the table")
        self.assertIn(ABSENT, unread[0])
        self.assertIn("(not read)", unread[0])

    def test_the_renamed_heading_is_not_read_as_changed_posture(self) -> None:
        # D-07 again, for a wording change: detection keys on the fingerprint, so the live
        # body titled "## Accounts read" must still match a render titled "## Accounts
        # asked about" for the same report, marker to marker.
        _, body, _, _ = self.render("report-findings.json")
        old = body.replace("## Accounts asked about", "## Accounts read", 1)
        self.assertTrue(old != body, "the replacement has to have found the heading")
        previous = self.tmp / "previous.md"
        previous.write_text(old, encoding="utf-8")
        code, again, summary, err = self.render("report-findings.json", previous)
        self.assertEqual(code, 0, err)
        self.assertFalse(summary["changed"])
        self.assertIn("## Accounts asked about", again)
        fresh, carried = MARKER_RE.search(again), MARKER_RE.search(old)
        if fresh is None or carried is None:
            self.fail("a rendered body carries no state marker")
        self.assertEqual(fresh.group(1), carried.group(1))


class TestChangeDetection(Renderer):
    def test_an_identical_run_again_is_marked_unchanged(self) -> None:
        previous = self.tmp / "previous.md"
        previous.write_text(self.fixture_body("report-findings.json"))
        code, body, summary, err = self.render("report-findings.json", previous)
        self.assertEqual(code, 0, err)
        self.assertFalse(summary["changed"])
        self.assertEqual((summary["new"], summary["resolved"]), (0, 0))
        self.assertIn("unchanged since the previous run", body)
        self.assertIn("None.", body)

    def test_a_resolved_finding_moves_out_of_current_and_into_resolved(self) -> None:
        previous = self.tmp / "previous.md"
        previous.write_text(self.fixture_body("report-findings.json"))
        code, body, summary, err = self.render("report-clean.json", previous)
        self.assertEqual(code, 0, err)
        self.assertTrue(summary["changed"])
        self.assertEqual((summary["new"], summary["resolved"]), (0, 1))
        self.assertIn("Posture changed since the previous run", body)
        current = body.split("## Current findings")[1].split("## Accounts asked about")[0]
        self.assertNotIn(ABSENT, current)
        resolved = body.split("## Resolved since the previous run")[1].split("## Current")[0]
        self.assertIn(ABSENT, resolved)

    def test_a_second_finding_shows_only_the_second_as_new(self) -> None:
        base = json.loads((FIXTURES / "report-warn.json").read_text())
        extra = json.loads((FIXTURES / "report-findings.json").read_text())
        base["accounts"].append(extra["accounts"][1])
        base["exit_code"] = 1
        merged = self.tmp / "merged.json"
        merged.write_text(json.dumps(base))
        previous = self.tmp / "previous.md"
        previous.write_text(self.fixture_body("report-warn.json"))
        code, _, summary, err = self.render(merged, previous)
        self.assertEqual(code, 0, err)
        self.assertEqual((summary["open"], summary["new"], summary["resolved"]), (2, 1, 0))

    def test_a_body_without_a_marker_starts_a_new_baseline_rather_than_crashing(self) -> None:
        previous = self.tmp / "previous.md"
        previous.write_text("An issue opened by a human, with no marker at all.")
        code, body, summary, err = self.render("report-findings.json", previous)
        self.assertEqual(code, 0, err)
        self.assertTrue(summary["changed"])
        self.assertIn("establishes the baseline", body)

    def test_a_corrupt_marker_is_treated_as_no_state(self) -> None:
        for payload in ("!!!not base64!!!", "", MARKER_RE.sub("", "x")):
            previous = self.tmp / "previous.md"
            previous.write_text(f"<!-- posture-watch:state v1 {payload} -->")
            code, body, summary, err = self.render("report-findings.json", previous)
            self.assertEqual(code, 0, err)
            self.assertIn("establishes the baseline", body)
            self.assertTrue(summary["changed"])

    def test_a_marker_whose_payload_is_not_findings_is_no_state(self) -> None:
        import base64

        for payload in (b"3", b'{"a": 1}', b'[{"account": "x"}]'):
            encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
            previous = self.tmp / "previous.md"
            previous.write_text(f"<!-- posture-watch:state v1 {encoded} -->")
            _, body, _, err = self.render("report-findings.json", previous)
            self.assertIn("establishes the baseline", body)
            self.assertEqual(err, "", "a body with no readable state is not a crash")

    def test_a_missing_previous_file_is_not_an_error(self) -> None:
        code, _, summary, err = self.render("report-findings.json", self.tmp / "nope.md")
        self.assertEqual(code, 0, err)
        self.assertTrue(summary["changed"])

    def test_the_marker_round_trips_to_the_current_open_set(self) -> None:
        _, body, _, _ = self.render("report-findings.json")
        encoded = MARKER_RE.search(body)
        if encoded is None:
            self.fail("the rendered body carries no state marker")
        import base64

        padding = "=" * (-len(encoded.group(1)) % 4)
        entries = json.loads(base64.urlsafe_b64decode(encoded.group(1) + padding))
        self.assertEqual(
            [e["fingerprint"] for e in entries],
            ["b03faa6106f2405560196e0cad9e0bb74cab9c08d798877c0d795019bddd43d6"],
        )
        self.assertEqual(entries[0]["rule"], "acct-missing")

    def test_the_marker_can_never_carry_the_sequence_that_closes_its_comment(self) -> None:
        _, body, _, _ = self.render("report-findings.json")
        found = MARKER_RE.search(body)
        if found is None:
            self.fail("the rendered body carries no state marker")
        payload = found.group(1)
        self.assertNotIn("-->", payload)
        for char in ("<", ">", "!", "="):
            self.assertNotIn(char, payload)


class TestAcceptedFindings(Renderer):
    def test_an_accepted_finding_is_counted_separately_and_stays_out_of_the_marker(self) -> None:
        code, body, summary, err = self.render("report-accepted.json")
        self.assertEqual(code, 0, err)
        self.assertEqual((summary["open"], summary["accepted"]), (0, 1))
        self.assertIn("## Accepted in the policy", body)
        self.assertIn("do not reappear in the lists above", body)
        current = body.split("## Current findings")[1].split("## Accepted")[0]
        self.assertIn("None.", current)

    def test_accepting_a_known_finding_reads_as_resolved(self) -> None:
        previous = self.tmp / "previous.md"
        previous.write_text(self.fixture_body("report-findings.json"))
        _, body, summary, _ = self.render("report-accepted.json", previous)
        self.assertEqual(summary["resolved"], 1)
        self.assertIn("Accepted in the policy", body)


class TestHostileStrings(Renderer):
    def test_a_home_domain_of_markup_is_escaped(self) -> None:
        code, body, _, err = self.render("report-hostile-strings.json")
        self.assertEqual(code, 0, err)
        self.assertIn(r"\[click here\](javascript:alert(1))", body)
        self.assertNotIn("[click here](javascript:alert(1))", body)

    def test_mentions_in_chain_fields_cannot_notify_anyone(self) -> None:
        _, body, _, _ = self.render("report-hostile-strings.json")
        self.assertNotIn("@all", body)
        self.assertNotIn("@somebody", body)
        self.assertIn("@&#8203;all", body)

    def test_a_hash_in_a_chain_field_does_not_open_a_heading(self) -> None:
        _, body, _, _ = self.render("report-hostile-strings.json")
        self.assertNotIn(" #hidden", body)
        self.assertIn(r"\#hidden", body)

    def test_a_backtick_in_a_chain_field_cannot_break_out_of_its_cell(self) -> None:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        report["exit_code"] = 1
        report["accounts"][0]["findings"] = [
            {
                "rule_id": "flag-drift",
                "severity": "high",
                "account": ACCOUNT,
                "message": "a `` fenced ` rule",
                "evidence": "x",
                "fingerprint": "a" * 64,
                "accepted": False,
            }
        ]
        path = self.tmp / "backticks.json"
        path.write_text(json.dumps(report))
        code, body, _, err = self.render(path)
        self.assertEqual(code, 0, err)
        self.assertNotIn("``", body)
        self.assertIn(r"a \`\` fenced \` rule", body)

    def test_the_report_body_is_never_printed_to_stdout(self) -> None:
        _, _, _, err = self.render("report-findings.json")
        self.assertEqual(err, "")


class TestRefusals(Renderer):
    def assert_refused(self, report: Path, expect: str, exit_code: int = 1) -> None:
        code, body, _, err = self.render(report, exit_code=exit_code)
        self.assertEqual(code, 2, err)
        self.assertIn(expect, err)
        self.assertEqual(body, "", "a refusal must not leave a body behind")

    def test_an_exit_code_that_disagrees_with_the_report(self) -> None:
        code, _, _, err = self.render("report-clean.json", exit_code=0)
        self.assertEqual(code, 0, err)
        self.assert_refused(
            FIXTURES / "report-clean.json", "carries exit code 0 and the run reported 1", 1
        )

    def test_invalid_json(self) -> None:
        path = self.tmp / "bad.json"
        path.write_text('{"tool_version": "x", ')
        self.assert_refused(path, "is not valid JSON at line")

    def test_an_empty_file(self) -> None:
        path = self.tmp / "zero.json"
        path.write_text("")
        self.assert_refused(path, "is empty")

    def test_a_missing_field(self) -> None:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        del report["ledger"]
        path = self.tmp / "noledger.json"
        path.write_text(json.dumps(report))
        self.assert_refused(path, "is missing the 'ledger' field")

    def test_an_unknown_severity(self) -> None:
        report = json.loads((FIXTURES / "report-findings.json").read_text())
        report["accounts"][1]["findings"][0]["severity"] = "critical"
        path = self.tmp / "crit.json"
        path.write_text(json.dumps(report))
        self.assert_refused(path, "unknown severity 'critical'")

    def test_a_finding_without_a_useful_fingerprint(self) -> None:
        report = json.loads((FIXTURES / "report-findings.json").read_text())
        report["accounts"][1]["findings"][0]["fingerprint"] = "b03faa"
        path = self.tmp / "shortfp.json"
        path.write_text(json.dumps(report))
        self.assert_refused(path, "without a 64-character fingerprint")

    def test_an_account_with_no_snapshot(self) -> None:
        report = json.loads((FIXTURES / "report-findings.json").read_text())
        del report["accounts"][0]["snapshot"]
        path = self.tmp / "nosnap.json"
        path.write_text(json.dumps(report))
        self.assert_refused(path, "has no snapshot.id")

    def test_a_report_that_is_a_list(self) -> None:
        path = self.tmp / "list.json"
        path.write_text("[1, 2]")
        self.assert_refused(path, "the top level is not an object")

    def test_an_oversized_report(self) -> None:
        path = self.tmp / "huge.json"
        path.write_text(json.dumps({"pad": "x" * (9 * 1024 * 1024)}))
        self.assert_refused(path, "is over the 8 MiB limit")

    def test_an_unreadable_report_path(self) -> None:
        code, _, _, err = self.render(self.tmp / "ghost.json", exit_code=0)
        self.assertEqual(code, 2)
        self.assertIn("cannot read it", err)

    def test_a_non_iso_as_of_date(self) -> None:
        for value in ("2026-11-3", "yesterday", "2026-13-01", "2026-11-03T00:00"):
            code, _, _, err = self.render("report-clean.json", extra={"as-of": value})
            self.assertEqual(code, 2, value)
            self.assertIn("is not a", err, value)

    def test_a_non_sha_gauge_ref(self) -> None:
        code, _, _, err = self.render("report-clean.json", extra={"gauge-ref": "main"})
        self.assertEqual(code, 2)
        self.assertIn("full 40-character commit sha", err)


class TestStateBudget(Renderer):
    def build(self, count: int) -> Path:
        report = json.loads((FIXTURES / "report-clean.json").read_text())
        report["exit_code"] = 1
        report["accounts"][0]["findings"] = [
            {
                "rule_id": "flag-drift",
                "severity": "high",
                "account": ACCOUNT,
                "message": f"finding number {index}",
                "evidence": "x",
                "fingerprint": f"{index:064x}",
                "accepted": False,
            }
            for index in range(count)
        ]
        path = self.tmp / f"many{count}.json"
        path.write_text(json.dumps(report))
        return path

    def test_more_findings_than_the_budget_leaves_a_loud_note(self) -> None:
        path = self.tmp / "seven.json"
        report = json.loads(self.build(7).read_text())
        report["accounts"] = report["accounts"][:1]
        path.write_text(json.dumps(report))
        code, body, _, err = self.render(path, extra={"max-state-entries": 3})
        self.assertEqual(code, 0, err)
        self.assertIn("Change detection is partial", body)
        self.assertIn("carries 3 of 7", body)

    def test_the_action_does_not_pass_the_flag_so_the_default_budget_applies(self) -> None:
        argv = "\n".join(
            line.strip()
            for line in (ROOT / "action.yml").read_text().splitlines()
            if "render_report.py" in line or "--max-state" in line
        )
        self.assertNotIn("--max-state", argv)


class TestFixtureProvenance(unittest.TestCase):
    def test_every_fixture_is_listed_in_the_provenance_table(self) -> None:
        readme = (FIXTURES / "README.md").read_text()
        listed = set(re.findall(r"^\| `(report-[^`]+\.json)`", readme, re.MULTILINE))
        present = {path.name for path in FIXTURES.glob("report-*.json")}
        self.assertEqual(present, listed, "a fixture with no recorded origin")

    def test_the_hand_built_ones_say_so(self) -> None:
        readme = (FIXTURES / "README.md").read_text()
        for name in ("report-accepted.json", "report-hostile-strings.json"):
            row = next(line for line in readme.splitlines() if line.startswith(f"| `{name}`"))
            self.assertIn("derived from", row)

    def test_no_fixture_contains_a_seed_shaped_string(self) -> None:
        pattern = re.compile(r"(?<![A-Z2-7])S[A-Z2-7]{55}(?![A-Z2-7])")
        for path in FIXTURES.glob("*.json"):
            self.assertIsNone(pattern.search(path.read_text()), path.name)


if __name__ == "__main__":
    unittest.main()
