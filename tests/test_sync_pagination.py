#!/usr/bin/env python3
"""Issue-list pagination past the fifth page (task 9.20)."""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402

MARKER_BODY = f"an issue body\n\n{sync_issue.MARKER_PREFIX}W30= -->\n"


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
        return self.script.pop(0)


def page(count: int, *, marker: bool = False, start: int = 1) -> bytes:
    entries = [
        {"number": start + i, "title": f"issue {start + i}", "body": "nothing here"}
        for i in range(count)
    ]
    if marker:
        entries[-1] = {
            "number": start + count - 1,
            "title": "tracked",
            "body": MARKER_BODY,
        }
    return json.dumps(entries).encode()


class Stubbed(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._real = sync_issue.TRANSPORT

    def tearDown(self) -> None:
        sync_issue.TRANSPORT = self._real  # type: ignore[assignment]
        self._directory.cleanup()

    def use(self, script: list[Any]) -> Stub:
        stub = Stub(script)
        sync_issue.TRANSPORT = stub  # type: ignore[assignment]
        return stub

    def env(self) -> None:
        os.environ["GITHUB_API_URL"] = "https://api.example.test"
        self.addCleanup(os.environ.pop, "GITHUB_API_URL", None)


class TestPagination(Stubbed):
    def test_a_marker_on_page_seven_is_found_once(self) -> None:
        self.env()
        pages = [page(100, start=1 + i * 100) for i in range(6)]
        pages.append(page(1, marker=True, start=701))
        stub = self.use([(200, p) for p in pages])
        out = self.tmp / "previous.md"
        found = sync_issue.find_issue(
            "acme", "widgets", "account-posture", "Account posture watch", "tok", out
        )
        self.assertEqual(found, 701)
        self.assertEqual(len(stub.calls), 7)
        self.assertIn("page=6", stub.calls[5]["url"])
        self.assertIn("page=7", stub.calls[6]["url"])
        self.assertEqual(out.read_text(), MARKER_BODY)

    def test_a_short_batch_ends_the_walk(self) -> None:
        self.env()
        stub = self.use([(200, page(100)), (200, page(3, start=101)), (200, page(0))])
        found = sync_issue.find_issue("acme", "widgets", "l", "t", "tok", self.tmp / "p.md")
        self.assertIsNone(found)
        self.assertEqual(len(stub.calls), 2, "a batch shorter than the page size ends it")

    def test_reaching_the_hard_cap_is_printed_once(self) -> None:
        self.env()
        self.addCleanup(setattr, sync_issue, "MAX_ISSUE_PAGES", sync_issue.MAX_ISSUE_PAGES)
        sync_issue.MAX_ISSUE_PAGES = 2
        stub = self.use([(200, page(100)), (200, page(100, start=101))])
        out = io.StringIO()
        with redirect_stdout(out):
            found = sync_issue.find_issue("acme", "widgets", "l", "t", "tok", self.tmp / "p.md")
        self.assertIsNone(found)
        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(out.getvalue().count("state marker may sit beyond"), 1)

    def test_the_page_size_is_the_module_constant(self) -> None:
        self.env()
        stub = self.use([(200, b"[]")])
        sync_issue.find_issue("acme", "widgets", "l", "t", "tok", self.tmp / "p.md")
        self.assertIn(f"per_page={sync_issue.ISSUE_PAGE_SIZE}", stub.calls[0]["url"])


if __name__ == "__main__":
    unittest.main()
