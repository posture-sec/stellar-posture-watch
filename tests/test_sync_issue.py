#!/usr/bin/env python3
"""Tests for scripts/sync_issue.py.

Two kinds of test live here. Most of them replace `sync_issue.TRANSPORT` with a stub so
the retry policy and the create/update/skip decisions can be asserted without a socket.
A few run a real loopback HTTP server and call the real transport, because the wire
details (headers, method, JSON body, and refusing to follow a redirect) are the part a
stub would happily agree with any wrong implementation of.

No test points the script at api.github.com. The https-only rule in `api_base` is a rule
about where the token may be sent, so the loopback tests exercise the transport directly
rather than loosening it.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402

ACCOUNT = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"
STATE_ISSUE = 7
MARKER_BODY = f"an issue body\n\n{sync_issue.MARKER_PREFIX}W30= -->\n"


def httperror(
    url: str, code: int, body: bytes = b"{}", retry_after: str | None = None
) -> urllib.error.HTTPError:
    from email.message import Message

    headers = Message()
    headers["Content-Type"] = "application/json"
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(url, code, f"status {code}", headers, io.BytesIO(body))


class Stub:
    """A transport that replays a script of responses and records the requests."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if not self.script:
            raise AssertionError(f"the stub ran out of scripted responses at {method} {url}")
        outcome = self.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            outcome = outcome()
        return outcome

    @property
    def methods(self) -> list[str]:
        return [call["method"] for call in self.calls]


class Stubbed(unittest.TestCase):
    """Replaces the transport and silences the backoff so retries cost nothing."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self.sleeps: list[float] = []
        self._real_sleep = sync_issue.time.sleep

        def no_wait(seconds: Any) -> None:
            self.sleeps.append(float(seconds))

        sync_issue.time.sleep = no_wait  # type: ignore[method-assign]

    def tearDown(self) -> None:
        sync_issue.time.sleep = self._real_sleep  # type: ignore[method-assign]
        self._directory.cleanup()

    def use(self, script: list[Any]) -> Stub:
        stub = Stub(script)
        sync_issue.TRANSPORT = stub  # type: ignore[assignment]
        self.addCleanup(lambda: setattr(sync_issue, "TRANSPORT", sync_issue.transport))
        return stub

    def env(self, **overrides: str) -> None:
        base = {
            "GITHUB_API_URL": "https://api.example.test",
            "GITHUB_REPOSITORY": "acme/widgets",
            "POSTURE_WATCH_TOKEN": "tok",
        }
        base.update(overrides)
        for key, value in base.items():
            os.environ[key] = value
            self.addCleanup(os.environ.pop, key, None)

    def file(self, name: str, text: str) -> str:
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def summary(self, **overrides: Any) -> str:
        data: dict[str, Any] = {
            "changed": True,
            "new": 1,
            "resolved": 0,
            "open": 1,
            "as_of": "2026-11-03",
        }
        data.update(overrides)
        return self.file("summary.json", json.dumps(data))

    def write(self, stub: Stub, number: int | None = None, *flags: str) -> tuple[int, str]:
        argv = [
            "write",
            "--label",
            "account-posture",
            "--title",
            "Account posture watch",
            "--body",
            self.file("body.md", "the rendered body"),
            "--summary",
            self.summary(),
        ]
        if number is not None:
            argv += ["--number", str(number)]
        argv += list(flags)
        out = io.StringIO()
        err = io.StringIO()
        from contextlib import redirect_stderr, redirect_stdout

        with redirect_stdout(out), redirect_stderr(err):
            code = sync_issue.main(argv)
        return code, out.getvalue() + err.getvalue()


class TestApiBaseUrl(Stubbed):
    def test_the_default_is_the_github_api(self) -> None:
        os.environ.pop("GITHUB_API_URL", None)
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        self.assertEqual(sync_issue.api_base(), "https://api.github.com")

    def test_a_trailing_slash_is_stripped(self) -> None:
        os.environ["GITHUB_API_URL"] = "https://ghe.internal/"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        self.assertEqual(sync_issue.api_base(), "https://ghe.internal")

    def test_plain_http_is_refused_because_a_token_rides_on_it(self) -> None:
        os.environ["GITHUB_API_URL"] = "http://api.example.test"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.api_base()
        self.assertIn("not https", str(caught.exception))

    def test_a_base_with_a_path_is_refused(self) -> None:
        os.environ["GITHUB_API_URL"] = "https://api.example.test/redirect"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.api_base()

    def test_ghes_api_v3_path_is_allowed(self) -> None:
        os.environ["GITHUB_API_URL"] = "https://ghe.internal/api/v3"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        self.assertEqual(sync_issue.api_base(), "https://ghe.internal/api/v3")

    def test_ghes_api_v3_with_trailing_slash_is_stripped(self) -> None:
        os.environ["GITHUB_API_URL"] = "https://ghe.internal/api/v3/"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)
        self.assertEqual(sync_issue.api_base(), "https://ghe.internal/api/v3")


class TestRetryPolicy(Stubbed):
    def test_a_servererror_is_retried_and_then_succeeds(self) -> None:
        stub = self.use([httperror("u", 500), httperror("u", 502), (200, b'{"ok": true}')])
        status, body = sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual((status, body), (200, b'{"ok": true}'))
        self.assertEqual(len(stub.calls), 3)
        self.assertEqual(self.sleeps, [2.0, 4.0])

    def test_a_rate_limit_with_a_short_wait_is_honoured(self) -> None:
        stub = self.use([httperror("u", 429, retry_after="1"), (200, b"[]")])
        sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 2)

    def test_a_rate_limit_with_an_absurd_wait_fails_instead_of_hanging(self) -> None:
        stub = self.use([httperror("u", 403, retry_after="99999")])
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertIn("403", str(caught.exception))
        self.assertEqual(len(stub.calls), 1, "a wait longer than the budget is not a retry")

    def test_a_missing_permission_is_reported_without_retry(self) -> None:
        stub = self.use(
            [httperror("u", 403, b'{"message": "Resource not accessible by token"}'), (200, b"[]")]
        )
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)

    def test_a_401_unauthorized_fails_immediately_without_retry(self) -> None:
        stub = self.use([httperror("u", 401, b'{"message": "Bad credentials"}'), (200, b"[]")])
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)

    def test_a_403_with_retry_after_is_retried(self) -> None:
        stub = self.use([httperror("u", 403, retry_after="1"), (200, b"[]")])
        sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 2)

    def test_a_404_is_not_retried(self) -> None:
        stub = self.use([httperror("u", 404, b'{"message": "Not Found"}'), (200, b"[]")])
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)
        self.assertIn("Not Found", str(caught.exception))

    def test_a_dropped_connection_is_retried_then_reported(self) -> None:
        stub = self.use([urllib.error.URLError("connection refused")] * 3)
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 3)
        self.assertIn("connection refused", str(caught.exception))

    def test_the_backoff_is_bounded(self) -> None:
        self.use([httperror("u", 500)] * 3)
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertTrue(all(wait <= sync_issue.MAX_RETRY_WAIT for wait in self.sleeps))

    def test_a_token_never_appears_in_a_failure_message(self) -> None:
        self.use([httperror("u", 500, b"Bearer supersecrettoken") for _ in range(3)])
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "supersecrettoken")
        self.assertNotIn("supersecrettoken", str(caught.exception))
        self.assertIn("[redacted]", sync_issue.redact("Authorization: Bearer supersecrettoken"))

    def test_redact_masks_modern_pats_and_bare_tokens(self) -> None:
        ghp = "ghp_" + "A" * 36
        ghs = "ghs_" + "B" * 36
        pat = "github_pat_" + "C" * 82
        sha = "D" * 40
        self.assertEqual(sync_issue.redact(f"failed {ghp}"), "failed [redacted]")
        self.assertEqual(sync_issue.redact(f"failed {ghs}"), "failed [redacted]")
        self.assertEqual(sync_issue.redact(f"failed {pat}"), "failed [redacted]")
        self.assertEqual(sync_issue.redact(f"failed {sha}"), "failed [redacted]")
        self.assertEqual(sync_issue.redact("var_token=mysecret"), "var_token=[redacted]")


class TestFind(Stubbed):
    def test_the_issue_carrying_the_marker_is_the_one_returned(self) -> None:
        self.env()
        issues = [
            {"number": 3, "title": "other", "body": "no marker here"},
            {"number": STATE_ISSUE, "title": "Account posture watch", "body": MARKER_BODY},
        ]
        stub = self.use([(200, json.dumps(issues).encode()), (200, b"[]")])
        out = self.tmp / "previous.md"
        found = sync_issue.find_issue(
            "acme", "widgets", "account-posture", "Account posture watch", "tok", out
        )
        self.assertEqual(found, STATE_ISSUE)
        self.assertEqual(out.read_text(), MARKER_BODY)
        self.assertIn("labels=account-posture", stub.calls[0]["url"])
        self.assertIn("state=open", stub.calls[0]["url"])

    def test_pull_requests_in_issues_response_are_ignored(self) -> None:
        self.env()
        issues = [
            {
                "number": 99,
                "title": "Account posture watch",
                "body": MARKER_BODY,
                "pull_request": {"url": "https://api.github.com/repos/acme/widgets/pulls/99"},
            },
            {"number": STATE_ISSUE, "title": "Account posture watch", "body": MARKER_BODY},
        ]
        self.use([(200, json.dumps(issues).encode()), (200, b"[]")])
        out = self.tmp / "previous.md"
        found = sync_issue.find_issue(
            "acme", "widgets", "account-posture", "Account posture watch", "tok", out
        )
        self.assertEqual(found, STATE_ISSUE)
        self.assertEqual(out.read_text(), MARKER_BODY)

    def test_pull_request_with_matching_title_is_not_adopted(self) -> None:
        self.env()
        issues = [
            {
                "number": 99,
                "title": "Account posture watch",
                "body": "a human wrote this in a PR",
                "pull_request": {"url": "https://api.github.com/repos/acme/widgets/pulls/99"},
            }
        ]
        self.use([(200, json.dumps(issues).encode()), (200, b"[]")])
        out = self.tmp / "previous.md"
        found = sync_issue.find_issue(
            "acme", "widgets", "account-posture", "Account posture watch", "tok", out
        )
        self.assertIsNone(found)

    def test_an_open_issue_with_the_right_title_is_adopted(self) -> None:
        self.env()
        issues = [{"number": 11, "title": "Account posture watch", "body": "a human wrote this"}]
        self.use([(200, json.dumps(issues).encode()), (200, b"[]")])
        out = self.tmp / "previous.md"
        found = sync_issue.find_issue(
            "acme", "widgets", "account-posture", "Account posture watch", "tok", out
        )
        self.assertEqual(found, 11)
        self.assertFalse(out.exists(), "an adopted issue has no previous state to hand over")

    def test_no_issue_at_all_is_not_an_error(self) -> None:
        self.env()
        self.use([(200, b"[]")])
        self.assertIsNone(
            sync_issue.find_issue(
                "acme",
                "widgets",
                "account-posture",
                "Account posture watch",
                "tok",
                self.tmp / "p.md",
            )
        )

    def test_a_label_is_url_encoded(self) -> None:
        self.env()
        stub = self.use([(200, b"[]")])
        sync_issue.find_issue("acme", "widgets", "account posture", "t", "tok", self.tmp / "p.md")
        self.assertIn("labels=account%20posture", stub.calls[0]["url"])

    def test_a_response_that_is_not_an_array_fails_loudly(self) -> None:
        self.env()
        self.use([(200, b'{"message": "Moved"}')])
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.find_issue("acme", "widgets", "l", "t", "tok", self.tmp / "p.md")

    def test_a_body_that_is_null_counts_as_no_marker(self) -> None:
        self.env()
        self.use(
            [
                (
                    200,
                    json.dumps([{"number": 5, "title": "something else", "body": None}]).encode(),
                ),
                (200, b"[]"),
            ]
        )
        self.assertIsNone(
            sync_issue.find_issue("acme", "widgets", "l", "t", "tok", self.tmp / "p.md")
        )

    def test_find_cli_writes_the_outputs(self) -> None:
        self.env(GITHUB_OUTPUT=str(self.tmp / "outputs.txt"))
        self.use(
            [
                (
                    200,
                    json.dumps(
                        [{"number": STATE_ISSUE, "title": "t", "body": MARKER_BODY}]
                    ).encode(),
                ),
                (200, b"[]"),
            ]
        )
        argv = [
            "find",
            "--label",
            "account-posture",
            "--title",
            "Account posture watch",
            "--previous-body-out",
            str(self.tmp / "prev.md"),
        ]
        out = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(out):
            code = sync_issue.main(argv)
        self.assertEqual(code, 0)
        recorded = (self.tmp / "outputs.txt").read_text()
        self.assertIn("found=true", recorded)
        self.assertIn(f"issue-number={STATE_ISSUE}", recorded)

    def test_emit_without_github_output_prints_safe_log(self) -> None:
        os.environ.pop("GITHUB_OUTPUT", None)
        self.addCleanup(os.environ.pop, "GITHUB_OUTPUT", None)
        out = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(out):
            sync_issue.emit("my-out", "my-val")
        self.assertEqual(out.getvalue(), "posture-watch: my-out=my-val\n")


class TestWriteDecisions(Stubbed):
    def test_a_baseline_creates_the_issue(self) -> None:
        self.env()
        stub = self.use([(201, json.dumps({"number": 42}).encode())])
        code, log = self.write(stub)
        self.assertEqual(code, 0, log)
        self.assertEqual(stub.methods, ["POST"])
        sent = json.loads(stub.calls[0]["body"])
        self.assertEqual(sent["labels"], ["account-posture"])
        self.assertEqual(sent["title"], "Account posture watch")
        self.assertEqual(sent["body"], "the rendered body")

    def test_a_change_updates_the_body_and_leaves_a_comment(self) -> None:
        self.env()
        stub = self.use([(200, b"{}"), (201, b"{}")])
        code, log = self.write(stub, STATE_ISSUE)
        self.assertEqual(code, 0, log)
        self.assertEqual(stub.methods, ["PATCH", "POST"])
        self.assertTrue(stub.calls[1]["url"].endswith("/comments"))
        comment = json.loads(stub.calls[1]["body"])["body"]
        self.assertIn("1 new finding", comment)
        self.assertIn("2026-11-03", comment)

    def test_an_unchanged_run_touches_nothing(self) -> None:
        self.env()
        stub = self.use([])
        argv = [
            "write",
            "--label",
            "l",
            "--title",
            "t",
            "--body",
            self.file("body.md", "the rendered body"),
            "--summary",
            self.summary(changed=False),
            "--number",
            "7",
        ]
        out = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(out):
            code = sync_issue.main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(stub.calls, [])
        self.assertIn("needs no change", out.getvalue())

    def test_update_on_no_change_refreshes_the_body_without_a_comment(self) -> None:
        self.env()
        stub = self.use([(200, b"{}")])
        argv = [
            "write",
            "--label",
            "l",
            "--title",
            "t",
            "--body",
            self.file("body.md", "the rendered body"),
            "--summary",
            self.summary(changed=False),
            "--number",
            "7",
            "--update-on-no-change",
        ]
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            code = sync_issue.main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(stub.methods, ["PATCH"])

    def test_a_dry_run_makes_no_request_at_all(self) -> None:
        self.env()
        stub = self.use([])
        code, log = self.write(stub, STATE_ISSUE, "--dry-run")
        self.assertEqual(code, 0, log)
        self.assertEqual(stub.calls, [])
        self.assertIn("dry run", log)

    def test_a_dry_run_with_no_issue_says_it_would_open_one(self) -> None:
        self.env()
        stub = self.use([])
        code, log = self.write(stub, None, "--dry-run")
        self.assertEqual(code, 0, log)
        self.assertEqual(stub.calls, [])
        self.assertIn("would open an issue", log)

    def test_a_create_response_without_a_number_is_a_failure(self) -> None:
        self.env()
        stub = self.use([(201, b"{}")])
        code, log = self.write(stub)
        self.assertEqual(code, 3)
        self.assertIn("carries no number", log)

    def test_an_api_failure_exits_3_not_0(self) -> None:
        self.env()
        stub = self.use([httperror("u", 401, b'{"message": "Bad credentials"}')])
        code, log = self.write(stub, STATE_ISSUE)
        self.assertEqual(code, 3)
        self.assertIn("401", log)
        self.assertEqual(len(stub.calls), 1)

    def test_the_summary_file_has_to_carry_the_decision_fields(self) -> None:
        self.env()
        path = self.file("summary.json", json.dumps({"open": 1}))
        argv = [
            "write",
            "--label",
            "l",
            "--title",
            "t",
            "--body",
            self.file("b.md", "x"),
            "--summary",
            path,
            "--number",
            "7",
        ]
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(argv)
        self.assertEqual(code, 3)
        self.assertIn("missing 'changed'", err.getvalue())


class TestBodyLimit(Stubbed):
    def body(self, rows: int) -> str:
        table = "\n".join(
            [
                "| Severity | Rule | Account | Fingerprint | Message |",
                "| --- | --- | --- | --- | --- |",
            ]
            + [
                f"| high | `acct-missing` | `{ACCOUNT}` | `{'0' * 12}` | message {index} |"
                for index in range(rows)
            ]
        )
        head = "intro\n\n## Current findings\n\n"
        tail = "\n\n## Accounts asked about\n\n| a |\n| - |\n" + ("pad " * 200 + "\n") * 8
        return head + table + tail

    def test_a_short_body_is_returned_unchanged(self) -> None:
        text = self.body(3)
        trimmed, removed = sync_issue.fit_body(text)
        self.assertEqual((removed, trimmed), (0, text))

    def test_an_oversized_body_loses_rows_not_the_header(self) -> None:
        text = self.body(1200)
        self.assertGreater(len(text), sync_issue.BODY_LIMIT)
        self.assertGreater(len(text), sync_issue.BODY_LIMIT)
        trimmed, removed = sync_issue.fit_body(text)
        self.assertLessEqual(len(trimmed), sync_issue.BODY_LIMIT)
        self.assertGreater(removed, 0)
        self.assertIn("more finding(s) truncated here", trimmed)
        self.assertIn("## Current findings", trimmed)
        self.assertIn("## Accounts asked about", trimmed)

    def test_a_body_that_loses_rows_says_how_many_in_the_log(self) -> None:
        self.env()
        path = self.file("big.md", self.body(1200))
        stub = self.use([(200, b"{}"), (201, b"{}")])
        argv = [
            "write",
            "--label",
            "l",
            "--title",
            "t",
            "--body",
            path,
            "--summary",
            self.summary(),
            "--number",
            "7",
        ]
        out = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(out):
            code = sync_issue.main(argv)
        self.assertEqual(code, 0)
        self.assertIn("truncated", out.getvalue())
        sent = json.loads(stub.calls[0]["body"])["body"]
        self.assertLessEqual(len(sent), sync_issue.BODY_LIMIT)

    def test_a_body_with_no_current_findings_section_cannot_be_trimmed(self) -> None:
        text = "x" * (sync_issue.BODY_LIMIT + 1)
        trimmed, removed = sync_issue.fit_body(text)
        self.assertEqual(removed, -1)
        self.assertEqual(trimmed, text)


class TestArgumentGuards(Stubbed):
    def test_an_empty_token_refuses_before_any_request(self) -> None:
        os.environ["POSTURE_WATCH_TOKEN"] = ""
        self.addCleanup(os.environ.pop, "POSTURE_WATCH_TOKEN", None)
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(
                ["find", "--label", "l", "--title", "t", "--previous-body-out", "x"]
            )
        self.assertEqual(code, 2)
        self.assertIn("POSTURE_WATCH_TOKEN is empty", err.getvalue())

    def test_a_label_that_could_reshape_the_url_is_refused(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok")
        for label in ("a/b", "a?labels=x", "a#b", "a b", "x" * 101):
            err = io.StringIO()
            from contextlib import redirect_stderr

            with redirect_stderr(err):
                code = sync_issue.main(
                    ["find", "--label", label, "--title", "t", "--previous-body-out", "x"]
                )
            self.assertEqual(code, 2, label)
            self.assertIn("refused", err.getvalue())

    def test_owner_and_repo_default_to_the_repository_the_workflow_runs_in(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok", GITHUB_REPOSITORY="posture-sec/watched")
        stub = self.use([(200, b"[]")])
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            code = sync_issue.main(
                [
                    "find",
                    "--label",
                    "l",
                    "--title",
                    "t",
                    "--previous-body-out",
                    str(self.tmp / "p.md"),
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("/repos/posture-sec/watched/issues", stub.calls[0]["url"])

    def test_a_repository_value_that_is_not_owner_slash_name_is_refused(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok", GITHUB_REPOSITORY="nothing-here")
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(
                ["find", "--label", "l", "--title", "t", "--previous-body-out", "x"]
            )
        self.assertEqual(code, 2)

    def test_find_without_an_output_path_is_refused(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok")
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(["find", "--label", "l", "--title", "t"])
        self.assertEqual(code, 2)

    def test_an_explicit_owner_that_is_not_a_path_segment_is_refused(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok")
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(
                [
                    "find",
                    "--owner",
                    "../evil",
                    "--repo",
                    "x",
                    "--label",
                    "l",
                    "--title",
                    "t",
                    "--previous-body-out",
                    "x",
                ]
            )
        self.assertEqual(code, 2)

    def test_a_negative_issue_number_is_refused(self) -> None:
        self.env(POSTURE_WATCH_TOKEN="tok")
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = sync_issue.main(
                [
                    "write",
                    "--label",
                    "l",
                    "--title",
                    "t",
                    "--body",
                    "x",
                    "--summary",
                    "y",
                    "--number",
                    "-3",
                ]
            )
        self.assertEqual(code, 2)


class LoopbackHandler(BaseHTTPRequestHandler):
    """Records what the real transport actually put on the wire."""

    replies: ClassVar[list[tuple[int, bytes]]] = []
    seen: ClassVar[list[dict[str, Any]]] = []
    redirect_to: ClassVar[str] = ""

    def do_GET(self) -> None:
        type(self).seen.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
        if type(self).redirect_to and self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", type(self).redirect_to)
            self.end_headers()
            return
        status, body = type(self).replies.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length)
        type(self).seen.append(
            {"method": "POST", "path": self.path, "body": payload, "headers": dict(self.headers)}
        )
        status, body = type(self).replies.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return


class TestRealTransport(unittest.TestCase):
    def setUp(self) -> None:
        LoopbackHandler.replies = []
        LoopbackHandler.seen = []
        LoopbackHandler.redirect_to = ""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LoopbackHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def call(self, method: str, path: str, body: bytes | None = None) -> tuple[int, bytes]:
        headers = {"Authorization": "Bearer tok", "Accept": sync_issue.ACCEPT}
        if body is not None:
            headers["Content-Type"] = "application/json"
        return sync_issue.transport(method, f"{self.base}{path}", headers, body)

    def test_a_get_returns_the_status_and_the_body(self) -> None:
        LoopbackHandler.replies = [(200, b'[{"number": 1}]')]
        status, body = self.call("GET", "/issues")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [{"number": 1}])

    def test_the_headers_the_api_needs_are_on_the_wire(self) -> None:
        LoopbackHandler.replies = [(200, b"[]")]
        self.call("GET", "/issues?state=open")
        record = LoopbackHandler.seen[0]
        self.assertEqual(record["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(record["headers"]["Accept"], sync_issue.ACCEPT)
        self.assertEqual(record["path"], "/issues?state=open")

    def test_a_post_sends_exactly_the_json_it_was_given(self) -> None:
        LoopbackHandler.replies = [(201, b'{"number": 9}')]
        payload = json.dumps({"title": "t", "body": "b"}).encode()
        status, body = self.call("POST", "/issues", payload)
        self.assertEqual((status, json.loads(body)), (201, {"number": 9}))
        record = LoopbackHandler.seen[0]
        self.assertEqual(json.loads(record["body"]), {"title": "t", "body": "b"})
        self.assertEqual(record["headers"]["Content-Type"], "application/json")

    def test_a_redirect_is_refused_rather_than_followed(self) -> None:
        LoopbackHandler.redirect_to = f"{self.base}/elsewhere"
        LoopbackHandler.replies = [(200, b"should never be asked for")]
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.call("GET", "/redirect")
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(
            [entry["path"] for entry in LoopbackHandler.seen],
            ["/redirect"],
            "the second path was never requested",
        )

    def test_the_opener_carries_the_redirect_handler(self) -> None:
        handlers = {type(h).__name__ for h in sync_issue.OPENER.handlers}  # type: ignore[attr-defined]
        self.assertIn("RedirectRefused", handlers)
        self.assertNotIn("HTTPRedirectHandler", handlers)


class TestMarkerContract(unittest.TestCase):
    """The renderer and the syncer have to agree on the marker or change detection dies."""

    def test_both_scripts_carry_the_identical_prefix(self) -> None:
        import render_report

        self.assertEqual(sync_issue.MARKER_PREFIX, render_report.MARKER_PREFIX)

    def test_a_rendered_body_decodes_back_through_the_prefix(self) -> None:
        import render_report

        body = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "render_report.py"),
                "--report",
                str(ROOT / "tests" / "fixtures" / "report-findings.json"),
                "--out",
                "/dev/stdout",
                "--as-of",
                "2026-11-03",
                "--config",
                "policy.toml",
                "--gauge-ref",
                "da656733fff839d5cf20f795460f4365a7254257",
                "--exit-code",
                "1",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        entries = render_report.decode_state(body)
        if entries is None:
            self.fail("the rendered body carries no state marker")
        self.assertEqual(
            [entry["fingerprint"] for entry in entries],
            ["b03faa6106f2405560196e0cad9e0bb74cab9c08d798877c0d795019bddd43d6"],
        )
        self.assertIn("b03faa6106f2", body, "the short fingerprint is what a reader cites")


if __name__ == "__main__":
    unittest.main()
