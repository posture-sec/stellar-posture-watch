#!/usr/bin/env python3
"""Tests for the sync_issue.py `comment` subcommand (issue #21).

Verifies that `comment` posts to the PR's issues endpoint, requires
both `--number` and `--body`, and routes correctly through main().
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sync_issue  # noqa: E402


class FakeTransport:
    """Stubs sync_issue.TRANSPORT and records every call."""

    def __init__(self, status: int = 201, body: bytes = b'{"number":42}') -> None:
        self.calls: list[tuple[str, str, dict, bytes | None]] = []
        self._status = status
        self._body = body

    def __call__(
        self, method: str, url: str, headers: dict, body: bytes | None
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, headers, body))
        return self._status, self._body


class CommentHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self._prior_transport = sync_issue.TRANSPORT
        self._prior_github_output = os.environ.pop("GITHUB_OUTPUT", None)
        self._prior_github_repo = os.environ.pop("GITHUB_REPOSITORY", None)
        self._prior_api_url = os.environ.pop("GITHUB_API_URL", None)
        os.environ["GITHUB_REPOSITORY"] = "owner/repo"
        os.environ["POSTURE_WATCH_TOKEN"] = "fake-token"

    def tearDown(self) -> None:
        sync_issue.TRANSPORT = self._prior_transport
        self._directory.cleanup()
        for key, val in [
            ("GITHUB_OUTPUT", self._prior_github_output),
            ("GITHUB_REPOSITORY", self._prior_github_repo),
            ("GITHUB_API_URL", self._prior_api_url),
        ]:
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        os.environ.pop("POSTURE_WATCH_TOKEN", None)

    def body_file(self, content: str = "posture update") -> str:
        path = self.tmp / "body.md"
        path.write_text(content, encoding="utf-8")
        return str(path)


class TestCommentSubcommand(CommentHarness):
    def test_comment_posts_to_issues_endpoint(self) -> None:
        fake = FakeTransport(status=201, body=b'{"id":1}')
        sync_issue.TRANSPORT = fake
        body_path = self.body_file("hello from posture watch")
        rc = sync_issue.main(["comment", "--number", "42", "--body", body_path])
        self.assertEqual(rc, 0)
        self.assertEqual(len(fake.calls), 1)
        method, url, _headers, payload = fake.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/repos/owner/repo/issues/42/comments", url)
        import json

        data = json.loads(payload)
        self.assertEqual(data["body"], "hello from posture watch")

    def test_comment_requires_number(self) -> None:
        body_path = self.body_file()
        rc = sync_issue.main(["comment", "--body", body_path])
        self.assertEqual(rc, 2)

    def test_comment_requires_body(self) -> None:
        rc = sync_issue.main(["comment", "--number", "42"])
        self.assertEqual(rc, 2)

    def test_comment_refuses_negative_number(self) -> None:
        body_path = self.body_file()
        rc = sync_issue.main(["comment", "--number", "-1", "--body", body_path])
        self.assertEqual(rc, 2)

    def test_comment_uses_pr_number_in_output(self) -> None:
        fake = FakeTransport(status=201, body=b'{"id":1}')
        sync_issue.TRANSPORT = fake
        output_path = self.tmp / "output.txt"
        os.environ["GITHUB_OUTPUT"] = str(output_path)
        body_path = self.body_file()
        rc = sync_issue.main(["comment", "--number", "7", "--body", body_path])
        self.assertEqual(rc, 0)
        output = output_path.read_text(encoding="utf-8")
        self.assertIn("issue-number=7", output)


class TestCommentDoesNotNeedLabelOrTitle(CommentHarness):
    def test_comment_works_without_label_and_title(self) -> None:
        fake = FakeTransport(status=201, body=b'{"id":1}')
        sync_issue.TRANSPORT = fake
        body_path = self.body_file("content")
        rc = sync_issue.main(["comment", "--number", "5", "--body", body_path])
        self.assertEqual(rc, 0)

    def test_find_still_requires_label(self) -> None:
        # Ensuring the comment change did not loosen find validation
        fake = FakeTransport(status=200, body=b"[]")
        sync_issue.TRANSPORT = fake
        rc = sync_issue.main(
            ["find", "--label", "", "--title", "t", "--previous-body-out", str(self.tmp / "out.md")]
        )
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
