#!/usr/bin/env python3
"""A 403 that carries only the primary rate-limit headers (task 9.22)."""

from __future__ import annotations

import io
import re
import sys
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402


def forbidden(headers: dict[str, str]) -> urllib.error.HTTPError:
    message = Message()
    message["Content-Type"] = "application/json"
    for key, value in headers.items():
        message[key] = value
    return urllib.error.HTTPError(
        "https://api.example.test/x", 403, "status 403", message, io.BytesIO(b"{}")
    )


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


class Stubbed(unittest.TestCase):
    def setUp(self) -> None:
        self.sleeps: list[float] = []
        self._real_sleep = sync_issue.time.sleep
        self._real = sync_issue.TRANSPORT
        self._real_time = sync_issue.time.time

        def no_wait(seconds: Any) -> None:
            self.sleeps.append(float(seconds))

        sync_issue.time.sleep = no_wait  # type: ignore[method-assign]

    def tearDown(self) -> None:
        sync_issue.time.sleep = self._real_sleep  # type: ignore[method-assign]
        sync_issue.time.time = self._real_time  # type: ignore[method-assign]
        sync_issue.TRANSPORT = self._real  # type: ignore[assignment]

    def use(self, script: list[Any]) -> Stub:
        stub = Stub(script)
        sync_issue.TRANSPORT = stub  # type: ignore[assignment]
        return stub

    def now(self, epoch: int) -> None:
        sync_issue.time.time = lambda: float(epoch)  # type: ignore[method-assign]


class TestRateLimitReset(Stubbed):
    def test_a_reset_inside_the_ceiling_is_waited_for_and_retried(self) -> None:
        stub = self.use(
            [
                forbidden({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1030"}),
                (200, b"[]"),
            ]
        )
        self.now(1000)
        status, _ = sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(status, 200)
        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(self.sleeps, [30.0])

    def test_a_reset_outside_the_ceiling_fails_on_the_first_response(self) -> None:
        stub = self.use([forbidden({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "4600"})])
        self.now(1000)
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)
        message = str(caught.exception)
        self.assertIn("rate limit resets at", message)
        self.assertRegex(message, r"resets at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        self.assertEqual(self.sleeps, [])

    def test_a_403_without_either_header_still_fails(self) -> None:
        stub = self.use([forbidden({"Content-Type": "application/json"})])
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)

    def test_a_403_with_remaining_above_zero_is_not_a_rate_limit(self) -> None:
        stub = self.use([forbidden({"X-RateLimit-Remaining": "5", "X-RateLimit-Reset": "1030"})])
        self.now(1000)
        with self.assertRaises(sync_issue.ApiError):
            sync_issue.request("GET", "https://api.example.test/x", "tok")
        self.assertEqual(len(stub.calls), 1)

    def test_the_helper_reads_both_headers(self) -> None:
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Reset"] = "1030"
        self.now(1000)
        self.assertEqual(sync_issue.rate_limit_wait(headers), 30.0)
        headers.replace_header("X-RateLimit-Remaining", "1")
        self.assertIsNone(sync_issue.rate_limit_wait(headers))

    def test_a_token_never_appears_in_the_reset_message(self) -> None:
        self.use([forbidden({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "4600"})])
        self.now(1000)
        with self.assertRaises(sync_issue.ApiError) as caught:
            sync_issue.request("GET", "https://api.example.test/x", "supersecrettoken")
        self.assertNotIn("supersecrettoken", str(caught.exception))
        self.assertIsNotNone(re.search(r"resets at", str(caught.exception)))


if __name__ == "__main__":
    unittest.main()
