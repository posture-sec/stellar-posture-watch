#!/usr/bin/env python3
"""Test that self-check's action job skips fork pull requests but exit3 still runs.

The point is not the colour of a check: a fork can hand this workflow a pull request whose
code is compiled with a token that lists every open issue. A read-only token still reads
those bodies, so this is a cost-and-token guard, not a write barrier. The guard must sit on
the job, with exit3 left running, and the test reads the workflow as text so it fails on a
moved, inverted or deleted condition.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF_CHECK = ROOT / ".github" / "workflows" / "self-check.yml"
PATH = "self-check.yml"
EXPECTED = (
    "github.event_name != 'pull_request' || "
    "github.event.pull_request.head.repo.full_name == github.repository"
)

GOOD = """jobs:
  action:
    name: self-check / action
    runs-on: ubuntu-latest
    if: %s
    steps:
      - name: Watch the example policy
        uses: ./

  exit3:
    name: self-check / exit-3 probe
    runs-on: ubuntu-latest
    steps:
      - name: Audit an unreadable policy
        uses: ./
        continue-on-error: true
""".replace("%s", EXPECTED)


def job_block(text: str, job: str) -> tuple[list[str], int]:
    """Return the lines of one job and the 1-based line of its header."""
    lines = text.splitlines()
    header = f"  {job}:"
    for index, line in enumerate(lines):
        if line == header:
            start = index
            break
    else:
        raise AssertionError(f"{PATH}: no '  {job}:' job header; cannot check a job that is absent")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip(" ")) <= 2:
            end = index
            break
    return lines[start:end], start + 1


def job_condition(text: str, job: str) -> tuple[str, int]:
    """Return the job-level if: expression, or raise one naming the job and line."""
    block, header_line = job_block(text, job)
    for offset, line in enumerate(block[1:], start=1):
        match = re.match(r"^    if:\s*(\S.*)$", line)
        if match:
            return match.group(1).strip(), header_line + offset
    raise AssertionError(
        f"{PATH}: job '{job}' (header line {header_line}) has no job-level if:; fork pull "
        "requests run its steps with the workflow token"
    )


def validate(text: str) -> str:
    condition, line_no = job_condition(text, "action")
    if condition != EXPECTED:
        raise AssertionError(
            f"{PATH}: job 'action' line {line_no}: if: {condition!r} is not the fork guard "
            f"{EXPECTED!r}"
        )
    try:
        probe_condition, probe_line = job_condition(text, "exit3")
    except AssertionError:
        pass
    else:
        raise AssertionError(
            f"{PATH}: job 'exit3' line {probe_line}: the exit-3 probe must keep running on "
            f"fork pull requests, but it carries if: {probe_condition!r}"
        )
    return condition


class TestSelfCheckForks(unittest.TestCase):
    def test_valid_guard_is_accepted(self) -> None:
        self.assertEqual(validate(GOOD), EXPECTED)

    def test_shipped_action_job_carries_the_exact_guard(self) -> None:
        condition, line_no = job_condition(SELF_CHECK.read_text(encoding="utf-8"), "action")
        self.assertEqual(
            condition,
            EXPECTED,
            f"{PATH}: job 'action' line {line_no} does not guard fork pull requests",
        )

    def test_shipped_exit3_probe_still_runs_for_forks(self) -> None:
        text = SELF_CHECK.read_text(encoding="utf-8")
        block, header_line = job_block(text, "exit3")
        with self.assertRaises(AssertionError):
            job_condition(text, "exit3")
        joined = "\n".join(block)
        self.assertIn("continue-on-error: true", joined)
        self.assertIn("no report, no body, no issue touched", joined)
        self.assertGreater(header_line, 0)

    def test_moved_guard_is_rejected(self) -> None:
        text = GOOD.replace(f"    if: {EXPECTED}\n", "", 1).replace(
            "      - name: Watch the example policy\n",
            f"      - name: Watch the example policy\n        if: {EXPECTED}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "job 'action'.*no job-level if:"):
            validate(text)

    def test_inverted_guard_is_rejected(self) -> None:
        for bad in (
            EXPECTED.replace("!=", "=="),
            EXPECTED.replace("github.repository", "github.event.pull_request.head.repo.full_name"),
            "github.event_name == 'pull_request'",
        ):
            with self.subTest(bad=bad):
                text = GOOD.replace(EXPECTED, bad, 1)
                with self.assertRaisesRegex(AssertionError, "job 'action' line 5.*not the fork"):
                    validate(text)

    def test_guard_on_the_wrong_job_is_rejected(self) -> None:
        text = GOOD.replace(
            "  exit3:\n",
            f"  exit3:\n    if: {EXPECTED}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "job 'exit3' line .*must keep running"):
            validate(text)


if __name__ == "__main__":
    unittest.main()
