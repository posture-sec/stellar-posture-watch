#!/usr/bin/env python3
"""Test that the ci / python job has a bounded timeout-minutes.

The text assertions are deliberately over the workflow text rather than a parsed YAML tree:
the guard must run on the runner's own python3 with no third-party package (D-02), and the
property is about where the key sits as much as about its value. A workflow-level key is a
failure here, because it is not the checks job that stops when a pip index never answers.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"
PATH = "ci.yml"
JOB = "checks"
MIN_MINUTES = 10
MAX_MINUTES = 30

GOOD = """jobs:
  checks:
    name: ci / python
    runs-on: ubuntu-latest
    # Covers the dev-tool install and the whole test, lint and type suite.
    timeout-minutes: 15
    steps:
      - name: Tests
        run: python -m unittest discover -s tests -t tests
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
        value = int(raw)
        if not MIN_MINUTES <= value <= MAX_MINUTES:
            raise AssertionError(
                f"{PATH}: job '{JOB}' line {line_no}: timeout-minutes={value} is outside "
                f"{MIN_MINUTES}-{MAX_MINUTES}; a cold install plus the suite needs a real bound"
            )
        return value, line_no
    raise AssertionError(
        f"{PATH}: job '{JOB}' (header line {header_line}) has no job-level timeout-minutes; "
        "a hung install or test inherits GitHub's six-hour default"
    )


class TestCiTimeout(unittest.TestCase):
    def test_valid_job_has_a_bounded_integer_timeout(self) -> None:
        self.assertEqual(timeout(GOOD), (15, 6))

    def test_shipped_ci_job_is_bounded(self) -> None:
        minutes, line_no = timeout(CI.read_text(encoding="utf-8"))
        self.assertTrue(MIN_MINUTES <= minutes <= MAX_MINUTES)
        self.assertGreater(line_no, 0)

    def test_zero_minutes_is_rejected(self) -> None:
        text = GOOD.replace("timeout-minutes: 15", "timeout-minutes: 0")
        with self.assertRaisesRegex(AssertionError, "job 'checks' line 6.*outside 10-30"):
            timeout(text)

    def test_non_integer_minutes_are_rejected(self) -> None:
        for raw in ("15m", "fifteen", "15.5", "true", "'15'"):
            with self.subTest(raw=raw):
                text = GOOD.replace("timeout-minutes: 15", f"timeout-minutes: {raw}")
                with self.assertRaisesRegex(AssertionError, "job 'checks' line 6.*whole number"):
                    timeout(text)

    def test_missing_key_names_the_job_and_its_line(self) -> None:
        text = GOOD.replace("    timeout-minutes: 15\n", "")
        with self.assertRaisesRegex(AssertionError, "job 'checks'.*header line 2.*six-hour"):
            timeout(text)

    def test_workflow_level_key_is_not_the_job_key(self) -> None:
        text = "timeout-minutes: 15\n" + GOOD.replace("    timeout-minutes: 15\n", "")
        with self.assertRaisesRegex(AssertionError, "job 'checks'.*no job-level timeout-minutes"):
            timeout(text)

    def test_comment_names_what_the_bound_covers(self) -> None:
        text = CI.read_text(encoding="utf-8")
        block, header_line = job_block(text)
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
                "whose comment can name what it covers"
            )
        above = "\n".join(block[max(0, key_offset - 8) : key_offset]).lower()
        line_no = header_line + key_offset
        self.assertIn(
            "install",
            above,
            f"{PATH}: job '{JOB}' line {line_no}: the comment must name the dev-tool install",
        )
        self.assertTrue(
            "test" in above or "suite" in above,
            f"{PATH}: job '{JOB}' line {line_no}: the comment must name the suite it bounds",
        )


if __name__ == "__main__":
    unittest.main()
