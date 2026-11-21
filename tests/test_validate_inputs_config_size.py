#!/usr/bin/env python3
"""The 1 MiB ceiling has to be read off the directory entry, not off the bytes in memory.

`check_policy()` opened the policy, held it, and only then compared its length to
`MAX_CONFIG_BYTES`. The message was right and the order was not: a caller who points `config`
at a large file makes the pre-flight read that file in full before it says no, and `ARCHITECTURE.md`
section 3 lists "at most 1 MiB" as a property of the path check rather than of the parse.

`stat()` answers the question for the price of one syscall, so it comes first. The check after
the read stays, because a file is allowed to grow between the two calls and the limit is a
promise about what reaches the parser either way.

The `Path` stand-ins below exist for one reason: the only way to show that a read did not
happen is to be the thing that would have been asked to do it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_inputs  # noqa: E402
from test_validate_inputs import MINIMAL, Harness  # noqa: E402

LIMIT = validate_inputs.MAX_CONFIG_BYTES


class RecordingPath:
    """A `Path` stand-in that reports a size, counts reads, and can fail either call.

    It is deliberately minimal: `check_policy()` only ever asks for `stat()`, `read_bytes()`
    and the text a refusal prints, so a fake with more surface than that would be a second
    filesystem to keep honest.
    """

    def __init__(
        self,
        *,
        size: int | None = None,
        body: bytes = b"",
        stat_error: OSError | None = None,
        read_error: OSError | None = None,
        name: str = "policy.toml",
    ) -> None:
        self.size = size
        self.body = body
        self.stat_error = stat_error
        self.read_error = read_error
        self.name = name
        self.reads = 0

    def __str__(self) -> str:
        return self.name

    def stat(self) -> Any:
        if self.stat_error is not None:
            raise self.stat_error
        assert self.size is not None
        return _Stat(self.size)

    def read_bytes(self) -> bytes:
        self.reads += 1
        if self.read_error is not None:
            raise self.read_error
        return self.body


class _Stat:
    """Only `st_size` is read, so only `st_size` exists."""

    def __init__(self, size: int) -> None:
        self.st_size = size


def padded_to(limit: int) -> str:
    """`MINIMAL` plus one comment line, so the file is exactly `limit` bytes on disk."""
    base = len(MINIMAL.encode("utf-8"))
    filler = limit - base - 3  # "# " + "x" * n + "\n"
    assert filler > 0, "the limit has to leave room for a comment"
    return f"{MINIMAL}# {'x' * filler}\n"


class TestStatBeforeRead(unittest.TestCase):
    def problems(self, path: RecordingPath) -> list[str]:
        found: list[str] = []
        validate_inputs.check_policy(path, found)  # type: ignore[arg-type]
        return found

    def test_a_file_over_the_limit_is_refused_without_being_read(self) -> None:
        path = RecordingPath(size=LIMIT + 1)
        self.assertEqual(
            self.problems(path),
            [f"config {path}: {LIMIT + 1} bytes is over the {LIMIT} limit"],
        )
        self.assertEqual(path.reads, 0)

    def test_a_much_larger_file_is_still_only_a_stat(self) -> None:
        # The number in the message is the size on disk, so a gigabyte has to be refused the
        # same one syscall way or the guard does not bound what the process holds.
        path = RecordingPath(size=1024 * LIMIT)
        self.assertEqual(
            self.problems(path),
            [f"config {path}: {1024 * LIMIT} bytes is over the {LIMIT} limit"],
        )
        self.assertEqual(path.reads, 0)

    def test_a_file_at_the_limit_is_read(self) -> None:
        body = padded_to(LIMIT).encode("utf-8")
        path = RecordingPath(size=len(body), body=body)
        self.assertEqual(self.problems(path), [])
        self.assertEqual(path.reads, 1)

    def test_a_file_that_grows_between_the_stat_and_the_read_is_still_refused(self) -> None:
        # The second guard is a second check and not a replacement: this is the case where the
        # stat said yes and the read says otherwise.
        body = b"# " + b"x" * LIMIT
        path = RecordingPath(size=10, body=body)
        self.assertEqual(
            self.problems(path),
            [f"config {path}: {len(body)} bytes is over the {LIMIT} limit"],
        )
        self.assertEqual(path.reads, 1)

    def test_a_stat_failure_keeps_the_read_failure_message(self) -> None:
        path = RecordingPath(stat_error=OSError(2, "No such file or directory"))
        self.assertEqual(
            self.problems(path),
            [f"config {path}: cannot read it (No such file or directory)"],
        )
        self.assertEqual(path.reads, 0)

    def test_a_file_that_vanishes_after_the_stat_is_still_reported(self) -> None:
        path = RecordingPath(size=40, read_error=OSError(2, "No such file or directory"))
        self.assertEqual(
            self.problems(path),
            [f"config {path}: cannot read it (No such file or directory)"],
        )
        self.assertEqual(path.reads, 1)


class TestRealFilesAtTheLimit(Harness):
    """The same boundary through the CLI, on bytes that are really on disk."""

    def test_a_policy_of_exactly_one_mebibyte_passes(self) -> None:
        text = padded_to(LIMIT)
        self.assertEqual(len(text.encode("utf-8")), LIMIT)
        code, out, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 0, err)
        self.assertIn("gauge-ref is pinned at da65673", out)

    def test_one_byte_more_is_refused_with_its_own_count(self) -> None:
        text = padded_to(LIMIT + 1)
        self.assertEqual(len(text.encode("utf-8")), LIMIT + 1)
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2, err)
        self.assertEqual(
            [line for line in err.splitlines() if line.startswith("  - ")],
            [f"  - config gauge.toml: {LIMIT + 1} bytes is over the {LIMIT} limit"],
        )


if __name__ == "__main__":
    unittest.main()
