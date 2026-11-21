#!/usr/bin/env python3
"""Test that the build half of watch has a bounded job-level timeout-minutes.

After the audit/write split, `audit` is the job that checks out and compiles Gauge at the
pinned sha, so it is the one that can hold the no-cancel concurrency group forever. A key on
the workflow or on the write job is not that bound and is rejected here. As with the ci
timeout, the assertions read the text with the standard library only (D-02).

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / ".github" / "workflows" / "watch.yml"
PATH = "watch.yml"
JOB = "audit"
MIN_MINUTES = 20
MAX_MINUTES = 60

GOOD = """jobs:
  audit:
    name: watch / audit
    runs-on: ubuntu-latest
    # 30 minutes: a cold Gauge build is about 2 minutes and three sync retries at a
    # 60-second ceiling add at most 3 minutes, so this leaves 6x headroom.
    timeout-minutes: 30
    steps:
      - name: Audit
        uses: ./
"""


def job_block(text: str, job: str = JOB) -> tuple[list[str], int]:
    """Return the lines of one job and the 1-based line of its header."""
    lines = text.splitlines()
    header = f"  {job}:"
    for index, line in enumerate(lines):
        if line == header:
            start = index
            break
    else:
        raise AssertionError(f"{PATH}: no '  {job}:' job header; cannot time a job that is absent")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip(" ")) <= 2:
            end = index
            break
    return lines[start:end], start + 1


def timeout(text: str) -> tuple[int, int]:
    """Return (minutes, line number) or raise an AssertionError naming job and line."""
    block, header_line = job_block(text)
    for offset, line in enumerate(block[1:], start=1):
        match = re.match(r"^    timeout-minutes:\s*(\S.*)$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        line_no = header_line + offset
        if not re.fullmatch(r"\d+", raw):
            raise AssertionError(
                f"{PATH}: job '{JOB}' line {line_no}: timeout-minutes must be a whole number "
                f"of minutes, got {raw!r}"
            )
        minutes = int(raw)
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            raise AssertionError(
                f"{PATH}: job '{JOB}' line {line_no}: timeout-minutes={minutes} is outside "
                f"{MIN_MINUTES}-{MAX_MINUTES}; a cold build plus the retry ceiling needs a bound"
            )
        return minutes, line_no
    raise AssertionError(
        f"{PATH}: job '{JOB}' (header line {header_line}) has no job-level timeout-minutes; "
        "a stalled build holds the no-cancel group until GitHub's six-hour default"
    )


class TestWatchTimeout(unittest.TestCase):
    def test_valid_job_has_a_bounded_integer_timeout(self) -> None:
        self.assertEqual(timeout(GOOD), (30, 7))

    def test_shipped_build_job_is_bounded(self) -> None:
        minutes, line_no = timeout(WATCH.read_text(encoding="utf-8"))
        self.assertTrue(MIN_MINUTES <= minutes <= MAX_MINUTES)
        self.assertGreater(line_no, 0)

    def test_zero_minutes_is_rejected(self) -> None:
        text = GOOD.replace("timeout-minutes: 30", "timeout-minutes: 0")
        with self.assertRaisesRegex(AssertionError, "job 'audit' line 7.*outside 20-60"):
            timeout(text)

    def test_non_integer_minutes_are_rejected(self) -> None:
        for raw in ("30m", "half an hour", "30.0", "false", '"30"'):
            with self.subTest(raw=raw):
                text = GOOD.replace("timeout-minutes: 30", f"timeout-minutes: {raw}")
                with self.assertRaisesRegex(AssertionError, "job 'audit' line 7.*whole number"):
                    timeout(text)

    def test_missing_key_names_the_job_and_its_line(self) -> None:
        text = GOOD.replace("    timeout-minutes: 30\n", "")
        with self.assertRaisesRegex(AssertionError, "job 'audit'.*header line 2.*no-cancel"):
            timeout(text)

    def test_workflow_level_key_is_not_the_job_key(self) -> None:
        text = "timeout-minutes: 30\n" + GOOD.replace("    timeout-minutes: 30\n", "")
        with self.assertRaisesRegex(AssertionError, "job 'audit'.*no job-level timeout-minutes"):
            timeout(text)

    def test_key_on_the_write_job_is_not_the_build_bound(self) -> None:
        text = GOOD.replace("    timeout-minutes: 30\n", "", 1)
        text = f"{text}  write:\n    timeout-minutes: 30\n"
        with self.assertRaisesRegex(AssertionError, "job 'audit'.*no job-level timeout-minutes"):
            timeout(text)

    def test_comment_names_the_build_and_the_retry_ceiling(self) -> None:
        block, header_line = job_block(WATCH.read_text(encoding="utf-8"))
        key_offset = next(
            (
                offset
                for offset, line in enumerate(block)
                if line.strip().startswith("timeout-minutes:")
            ),
            None,
        )
        if key_offset is None:
            raise AssertionError(
                f"{PATH}: job '{JOB}' (header line {header_line}) has no timeout-minutes key "
                "whose comment can name the build and the retry ceiling"
            )
        above = "\n".join(block[max(0, key_offset - 8) : key_offset]).lower()
        line_no = header_line + key_offset
        self.assertIn(
            "build",
            above,
            f"{PATH}: job '{JOB}' line {line_no}: the comment must name the Gauge build",
        )
        self.assertTrue(
            "retr" in above and "60" in above,
            f"{PATH}: job '{JOB}' line {line_no}: the comment must name the 60 s retry ceiling",
        )


if __name__ == "__main__":
    unittest.main()
