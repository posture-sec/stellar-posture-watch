#!/usr/bin/env python3
"""Test the audit/write split of watch.yml and the token boundary between them.

Only the second job may carry issues: write, and that job must not check out code or build
Gauge: the first half is the one that compiles another repository's Go. The handoff is an
artifact holding the rendered body, its summary and the stdlib syncer. The assertions read
the workflow as text so they run on the runner's own python3 with no YAML dependency.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / ".github" / "workflows" / "watch.yml"
PATH = "watch.yml"
UPLOAD = "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2"
DOWNLOAD = "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131 # v7.0.0"


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def job_blocks(text: str) -> dict[str, list[str]]:
    """Map each job key to the lines under its two-space header."""
    jobs: dict[str, list[str]] = {}
    current: str | None = None
    in_jobs = False
    for line in text.splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs or not line.strip() or line.lstrip().startswith("#"):
            continue
        if indent_of(line) == 2 and re.fullmatch(r"  [A-Za-z0-9_-]+:", line):
            current = line.strip()[:-1]
            jobs[current] = []
        elif indent_of(line) <= 2:
            current = None
        elif current is not None:
            jobs[current].append(line)
    return jobs


def block_of(jobs: dict[str, list[str]], name: str) -> list[str]:
    if name not in jobs:
        raise AssertionError(f"{PATH}: jobs: has no '{name}' job; the audit/write split is missing")
    return jobs[name]


def permissions(block: list[str], job: str) -> dict[str, str]:
    result: dict[str, str] = {}
    start = next(
        (i for i, line in enumerate(block) if line == "    permissions:"),
        None,
    )
    if start is None:
        raise AssertionError(f"{PATH}: job '{job}' declares no permissions map")
    for line in block[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if indent_of(line) < 6:
            break
        match = re.match(r"^      ([A-Za-z0-9_-]+):\s*(\S+)", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def steps(block: list[str]) -> list[list[str]]:
    result: list[list[str]] = []
    start = next((i for i, line in enumerate(block) if line == "    steps:"), None)
    if start is None:
        return result
    for line in block[start + 1 :]:
        if re.match(r"^      - (name|uses):", line):
            result.append([line])
        elif result and indent_of(line) >= 8 and line.strip():
            result[-1].append(line)
    return result


class TestWatchJobSplit(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATCH.read_text(encoding="utf-8")
        self.jobs = job_blocks(self.text)

    def test_audit_has_only_read_permissions(self) -> None:
        self.assertEqual(
            permissions(block_of(self.jobs, "audit"), "audit"),
            {"contents": "read", "issues": "read"},
            f"{PATH}: job 'audit' must read issues but must not hold the write token",
        )

    def test_write_has_only_the_issue_write_permission(self) -> None:
        self.assertEqual(
            permissions(block_of(self.jobs, "write"), "write"),
            {"issues": "write"},
            f"{PATH}: job 'write' may carry only issues: write, never checkout or contents",
        )

    def test_no_workflow_level_write_permission(self) -> None:
        match = re.search(r"^permissions:\n((?:  .*\n)+)", self.text, re.MULTILINE)
        if match:
            self.assertNotIn(
                "issues: write",
                match.group(1),
                f"{PATH}: issues: write belongs on the write job, not on every job",
            )

    def test_write_needs_audit(self) -> None:
        block = block_of(self.jobs, "write")
        self.assertIn("    needs: audit", block, f"{PATH}: job 'write' must run after 'audit'")

    def test_audit_runs_a_dry_run_and_uploads_both_files(self) -> None:
        block = block_of(self.jobs, "audit")
        joined = "\n".join(block)
        self.assertIn('dry-run: "true"', joined, f"{PATH}: job 'audit' must not write an issue")
        upload = [step for step in steps(block) if any(UPLOAD in line for line in step)]
        self.assertEqual(len(upload), 1, f"{PATH}: job 'audit' needs exactly one pinned upload")
        paths = "\n".join(upload[0])
        self.assertIn("issue-body.md", paths)
        self.assertIn("summary.json", paths)

    def test_write_downloads_the_artifact_and_calls_sync_issue(self) -> None:
        block = block_of(self.jobs, "write")
        write_steps = steps(block)
        download = [step for step in write_steps if any(DOWNLOAD in line for line in step)]
        self.assertEqual(
            len(download), 1, f"{PATH}: job 'write' needs one pinned artifact download"
        )
        writers = [step for step in write_steps if any("sync_issue.py" in line for line in step)]
        self.assertEqual(len(writers), 1, f"{PATH}: job 'write' must call sync_issue.py write")
        self.assertIn('sync_issue.py" write', " ".join("\n".join(writers[0]).split()))
        self.assertIn(
            "POSTURE_WATCH_TOKEN: ${{ github.token }}",
            "\n".join(writers[0]),
            f"{PATH}: job 'write' must bind the token in env, never in an argument",
        )

    def test_write_has_no_checkout_and_no_go_build(self) -> None:
        block = block_of(self.jobs, "write")
        joined = "\n".join(block)
        for forbidden in ("actions/checkout@", "uses: ./", "setup-go@", "go build"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(
                    forbidden,
                    joined,
                    f"{PATH}: job 'write' must never compile or check out code ({forbidden})",
                )


if __name__ == "__main__":
    unittest.main()
