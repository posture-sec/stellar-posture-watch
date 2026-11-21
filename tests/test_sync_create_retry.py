#!/usr/bin/env python3
"""The create call is single-attempt (task 9.21)."""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402


def httperror(url: str, code: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    from email.message import Message

    headers = Message()
    headers["Content-Type"] = "application/json"
    return urllib.error.HTTPError(url, code, f"status {code}", headers, io.BytesIO(body))


class Stub:
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
        return outcome

    @property
    def methods(self) -> list[str]:
        return [call["method"] for call in self.calls]


class Stubbed(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self.sleeps: list[float] = []
        self._real_sleep = sync_issue.time.sleep
        self._real = sync_issue.TRANSPORT

        def no_wait(seconds: Any) -> None:
            self.sleeps.append(float(seconds))

        sync_issue.time.sleep = no_wait  # type: ignore[method-assign]

    def tearDown(self) -> None:
        sync_issue.time.sleep = self._real_sleep  # type: ignore[method-assign]
        sync_issue.TRANSPORT = self._real  # type: ignore[assignment]
        self._directory.cleanup()

    def use(self, script: list[Any]) -> Stub:
        stub = Stub(script)
        sync_issue.TRANSPORT = stub  # type: ignore[assignment]
        return stub

    def env(self) -> None:
        for key, value in {
            "GITHUB_API_URL": "https://api.example.test",
            "GITHUB_REPOSITORY": "acme/widgets",
            "POSTURE_WATCH_TOKEN": "tok",
        }.items():
            os.environ[key] = value
            self.addCleanup(os.environ.pop, key, None)

    def file(self, name: str, text: str) -> str:
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def write(self, *flags: str) -> tuple[int, str]:
        summary = self.file(
            "summary.json",
            json.dumps(
                {"changed": True, "new": 1, "resolved": 0, "open": 1, "as_of": "2026-11-03"}
            ),
        )
        argv = [
            "write",
            "--label",
            "account-posture",
            "--title",
            "Account posture watch",
            "--body",
            self.file("body.md", "the rendered body"),
            "--summary",
            summary,
        ]
        argv += list(flags)
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = sync_issue.main(argv)
        return code, out.getvalue() + err.getvalue()


class TestCreateIsSingleAttempt(Stubbed):
    def test_a_dropped_create_response_makes_one_post_and_exits_3(self) -> None:
        self.env()
        stub = self.use([urllib.error.URLError("connection reset by peer")])
        code, log = self.write()
        self.assertEqual(code, 3, log)
        self.assertEqual(stub.methods, ["POST"], "a create must never be resent")
        self.assertIn("failed after 1 attempt", log)
        self.assertEqual(self.sleeps, [])

    def test_the_default_retry_policy_is_still_three(self) -> None:
        self.env()
        stub = self.use([httperror("u", 500), httperror("u", 500), (200, b'{"ok": true}')])
        status, _ = sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(status, 200)
        self.assertEqual(len(stub.calls), 3)

    def test_a_get_that_keeps_failing_uses_three_attempts(self) -> None:
        self.env()
        stub = self.use([httperror("u", 500) for _ in range(3)])
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 3)
        self.assertIn("failed after 3 attempts", str(caught.exception))

    def test_the_caller_can_ask_for_one_attempt(self) -> None:
        self.env()
        stub = self.use([urllib.error.URLError("boom")])
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("POST", "https://api.example.test/x", "tok", {"a": 1}, attempts=1)
        self.assertEqual(len(stub.calls), 1)


if __name__ == "__main__":
    unittest.main()
