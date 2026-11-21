#!/usr/bin/env python3
"""Tests for issue #73: no token reaches stdout, stderr or a step output on any exit path.

`scripts/sync_issue.py` prints six kinds of refusal: an API answer it will not act on, retries
it ran out of, a body that is not JSON, an input it will not put in a URL, a summary it cannot
read, and an `OSError` from the filesystem. Every one of those messages is built from a string
that can carry a credential, because a bearer value is echoed in API error bodies, sits in the
URL as the `labels=` query value the operator supplied, and names files a caller can point at
anything.

So the rule these tests hold is about the outputs, not the exceptions: `redact()` at
`scripts/sync_issue.py` masks what the pattern recognises, and `tests/test_sync_issue.py` checks
that on one 500. This file drives `main()` instead, with `POSTURE_WATCH_TOKEN` set and
`GITHUB_OUTPUT` pointed at a real file, and reads back everything the process could have said.
That is the only way to catch an edit that prints `str(exc)`, `os.environ`, or the URL it was
about to call.

The last class proves the assertions have teeth: with `redact()` replaced by the identity
function the same cases leak the token, so a regression that drops a call site fails here.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402

TOKEN = "ghp_" + "K" * 36
REDACTED = "[redacted]"
BASE = "https://api.example.test"
TITLE = "Account posture watch"
MARKER_BODY = f"an issue body\n\n{sync_issue.MARKER_PREFIX}W30= -->\n"
EMPTY_JSON = (200, b"{}")


def echo(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    """An API failure whose reason phrase and body both quote the credential.

    GitHub puts a `Retry-After` on the limits it wants respected and nothing on the ones it does
    not, so the two shapes decide whether this becomes one call or three.
    """
    headers = Message()
    headers["Content-Type"] = "application/json"
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    body = json.dumps({"message": f"Bad credentials: Bearer {TOKEN}"}).encode()
    return urllib.error.HTTPError(BASE, code, f"Bearer {TOKEN}", headers, io.BytesIO(body))


def broken_transport(kind: str) -> list[Any]:
    """The scripted responses that make one API case fail, repeated as the policy retries."""
    if kind == "429 then fails":
        return [echo(429, retry_after="1") for _ in range(3)]
    if kind == "three 500s":
        return [echo(500), echo(502), echo(503)]
    if kind == "URLError":
        return [urllib.error.URLError(f"connection reset near {TOKEN}") for _ in range(3)]
    if kind == "OSError":
        return [OSError(f"socket write failed for {TOKEN}") for _ in range(3)]
    return [echo(int(kind))]


API_CASES = [
    "401",
    "403",
    "404",
    "422",
    "429 then fails",
    "three 500s",
    "URLError",
    "OSError",
]


class Stub:
    """A transport that replays a script of responses and raises the exceptions in it."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.urls: list[str] = []

    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        self.urls.append(url)
        if not self.script:
            raise AssertionError(f"ran out of scripted responses at {method} {url}")
        outcome = self.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Driven(unittest.TestCase):
    """Runs the CLI with the token in the environment and a real step-output file."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.tmp = Path(self._directory.name)
        self.sleeps: list[float] = []
        self._real_sleep = sync_issue.time.sleep
        sync_issue.time.sleep = lambda seconds: self.sleeps.append(float(seconds))  # type: ignore
        self.addCleanup(setattr, sync_issue.time, "sleep", self._real_sleep)
        self.step_output = self.tmp / "github_output.txt"
        self.step_output.write_text("", encoding="utf-8")
        self.environ(
            GITHUB_API_URL=BASE,
            GITHUB_REPOSITORY="acme/widgets",
            POSTURE_WATCH_TOKEN=TOKEN,
            GITHUB_OUTPUT=str(self.step_output),
        )

    def environ(self, **values: str) -> None:
        for key, value in values.items():
            prior = os.environ.get(key)
            os.environ[key] = value
            self.addCleanup(self.restore, key, prior)

    def restore(self, key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def use(self, script: list[Any]) -> Stub:
        stub = Stub(script)
        sync_issue.TRANSPORT = stub  # type: ignore[assignment]
        self.addCleanup(lambda: setattr(sync_issue, "TRANSPORT", sync_issue.transport))
        return stub

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
            "as_of": "2026-11-21",
        }
        data.update(overrides)
        return self.file("summary.json", json.dumps(data))

    def find_argv(self, label: str = TOKEN) -> list[str]:
        return [
            "find",
            "--label",
            label,
            "--title",
            TITLE,
            "--previous-body-out",
            str(self.tmp / "previous.md"),
        ]

    def write_argv(self, number: int | None = 7, **overrides: str) -> list[str]:
        argv = [
            "write",
            "--label",
            "account-posture",
            "--title",
            TITLE,
            "--body",
            overrides.get("body", self.file("body.md", MARKER_BODY)),
            "--summary",
            overrides.get("summary", self.summary()),
        ]
        if number is not None:
            argv += ["--number", str(number)]
        return argv

    def invoke(self, argv: list[str]) -> tuple[int, str]:
        """The exit code, and everything said: both streams plus the step-output file."""
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = sync_issue.main(argv)
        said = out.getvalue() + err.getvalue() + self.step_output.read_text(encoding="utf-8")
        return code, said

    def assert_no_token(self, argv: list[str], expect_code: int) -> str:
        code, said = self.invoke(argv)
        self.assertEqual(code, expect_code, said)
        self.assertNotIn(TOKEN, said, f"the token reached an output: {said}")
        return said

    def without_redaction(self) -> None:
        """Replace `redact()` with the identity, for the teeth test only."""
        original = sync_issue.redact
        sync_issue.redact = lambda text: text[:200]
        self.addCleanup(setattr, sync_issue, "redact", original)


class TestEveryApiFailureIsClean(Driven):
    def test_find_and_write_leave_the_token_out_of_every_exit_3_message(self) -> None:
        for case in API_CASES:
            for action in ("find", "write"):
                with self.subTest(case=case, action=action):
                    self.use(broken_transport(case))
                    argv = self.find_argv() if action == "find" else self.write_argv()
                    said = self.assert_no_token(argv, 3)
                    self.assertIn(REDACTED, said, f"{action} on {case} printed nothing redacted")


class TestUnparseableAnswer(Driven):
    def test_a_non_json_list_answer_reports_the_url_without_the_label(self) -> None:
        self.use([(200, b"<html>an error page</html>")])
        said = self.assert_no_token(self.find_argv(), 3)
        self.assertIn("returned a body that is not JSON", said)
        self.assertIn(REDACTED, said)

    def test_a_non_json_create_answer_is_still_exit_3(self) -> None:
        self.use([(200, f"<html>Bearer {TOKEN}</html>".encode())])
        said = self.assert_no_token(self.write_argv(number=None), 3)
        self.assertIn("returned a body that is not JSON", said)

    def test_a_list_answer_that_is_not_an_array_is_refused(self) -> None:
        self.use([(200, json.dumps({"message": TOKEN}).encode())])
        said = self.assert_no_token(self.find_argv(), 3)
        self.assertIn("is not an array", said)


class TestInputRefusals(Driven):
    def test_an_empty_token_names_the_variable_and_nothing_else(self) -> None:
        os.environ["POSTURE_WATCH_TOKEN"] = ""
        code, said = self.invoke(self.find_argv(label="account-posture"))
        self.assertEqual(code, 2, said)
        self.assertIn("POSTURE_WATCH_TOKEN is empty", said)
        self.assertEqual(self.step_output.read_text(encoding="utf-8"), "")

    def test_a_token_shaped_invalid_label_is_refused_without_printing_it(self) -> None:
        self.use([EMPTY_JSON])
        said = self.assert_no_token(self.find_argv(label=f"{TOKEN}/nested"), 2)
        self.assertIn("it goes into a URL path", said)
        self.assertIn(REDACTED, said)

    def test_a_blank_owner_from_the_environment_is_refused(self) -> None:
        self.environ(GITHUB_REPOSITORY="")
        argv = self.find_argv(label="account-posture")
        code, said = self.invoke(argv)
        self.assertEqual(code, 2, said)
        self.assertNotIn(TOKEN, said)


class TestSummaryAndFiles(Driven):
    def without_key(self, key: str) -> str:
        data = {
            "changed": True,
            "new": 1,
            "resolved": 0,
            "open": 1,
            "as_of": "2026-11-21",
        }
        data.pop(key)
        return self.file("partial-summary.json", json.dumps(data))

    def test_a_missing_summary_is_refused_without_the_token(self) -> None:
        self.use([EMPTY_JSON, EMPTY_JSON])
        argv = self.write_argv(summary=str(self.tmp / "absent.json"))
        said = self.assert_no_token(argv, 3)
        self.assertIn("cannot read it", said)

    def test_a_summary_missing_a_key_is_refused_without_the_token(self) -> None:
        self.use([EMPTY_JSON, EMPTY_JSON])
        said = self.assert_no_token(self.write_argv(summary=self.without_key("as_of")), 3)
        self.assertIn("is missing 'as_of'", said)

    def test_a_missing_body_file_is_reported_as_an_oserror(self) -> None:
        self.use([EMPTY_JSON])
        argv = self.write_argv(body=str(self.tmp / "no-such-body.md"))
        said = self.assert_no_token(argv, 3)
        self.assertIn("No such file", said)


class TestSuccessfulRuns(Driven):
    def test_a_found_issue_emits_only_its_number(self) -> None:
        issues = [{"number": 7, "title": TITLE, "body": MARKER_BODY}]
        self.use([(200, json.dumps(issues).encode())])
        said = self.assert_no_token(self.find_argv(), 0)
        self.assertIn("found=true", self.step_output.read_text(encoding="utf-8"))
        self.assertIn("issue-number=7", said)

    def test_an_update_emits_the_number_and_writes_no_token(self) -> None:
        self.use([EMPTY_JSON, EMPTY_JSON])
        said = self.assert_no_token(self.write_argv(), 0)
        outputs = self.step_output.read_text(encoding="utf-8")
        self.assertIn("changed=true", outputs)
        self.assertIn("issue-number=7", outputs)
        self.assertIn("updated issue #7", said)


class TestTheAssertionsHaveTeeth(Driven):
    """A guard that passes because nothing was ever printable is worth nothing.

    Same fixtures, same runs, with `redact()` neutered: the token is provably in the message
    every class above is checking, which is what a dropped `redact()` at a call site would hit.
    """

    def test_an_unredacted_detail_prints_the_bearer_value(self) -> None:
        self.without_redaction()
        self.use([echo(404)])
        code, said = self.invoke(self.write_argv())
        self.assertEqual(code, 3, said)
        self.assertIn(TOKEN, said)

    def test_an_unredacted_reason_phrase_prints_the_bearer_value(self) -> None:
        self.without_redaction()
        self.use(broken_transport("URLError"))
        code, said = self.invoke(self.write_argv())
        self.assertEqual(code, 3, said)
        self.assertIn(TOKEN, said)

    def test_an_unredacted_url_prints_the_label(self) -> None:
        self.without_redaction()
        self.use([echo(404)])
        code, said = self.invoke(self.find_argv())
        self.assertEqual(code, 3, said)
        self.assertIn(TOKEN, said)

    def test_an_unredacted_refusal_prints_an_invalid_label(self) -> None:
        self.without_redaction()
        self.use([EMPTY_JSON])
        code, said = self.invoke(self.find_argv(label=f"{TOKEN}/nested"))
        self.assertEqual(code, 2, said)
        self.assertIn(TOKEN, said)
