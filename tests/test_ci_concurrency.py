from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"
GROUP = "group: ${{ github.workflow }}-${{ github.ref }}"
CANCEL = "cancel-in-progress: ${{ github.event_name == 'pull_request' }}"
BLOCK = f"concurrency:\n  {GROUP}\n  {CANCEL}\n"


def concurrency_problems(text: str) -> list[str]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line == "concurrency:"]
    if len(starts) != 1:
        return ["ci.yml must have exactly one workflow-level concurrency block"]
    start = starts[0]
    jobs = next((index for index, line in enumerate(lines) if line == "jobs:"), len(lines))
    if start >= jobs:
        return ["ci.yml concurrency must precede jobs"]
    block = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(" "):
            break
        if line.strip() and not line.lstrip().startswith("#"):
            block.append(line)
    problems = []
    for expected in (GROUP, CANCEL):
        key = expected.split(":", 1)[0] + ":"
        if [line for line in block if line.strip().startswith(key)] != [f"  {expected}"]:
            problems.append(f"ci.yml concurrency must contain exactly {expected}")
    return problems


class TestCiConcurrency(unittest.TestCase):
    def test_shipped_ci_cancels_only_superseded_pull_requests(self) -> None:
        self.assertEqual(concurrency_problems(CI.read_text(encoding="utf-8")), [])

    def test_missing_or_changed_block_is_rejected(self) -> None:
        valid = f"name: ci\n{BLOCK}jobs:\n  checks:\n"
        self.assertEqual(concurrency_problems(valid), [])
        mutations = (
            valid.replace(BLOCK, ""),
            valid.replace("github.ref", "github.sha"),
            valid.replace(f"  {GROUP}", f"    {GROUP}"),
            valid.replace("github.event_name == 'pull_request'", "true"),
            valid.replace(BLOCK, "  " + BLOCK.replace("\n", "\n  ")),
            valid.replace(BLOCK, BLOCK + BLOCK),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                self.assertTrue(concurrency_problems(mutated))


if __name__ == "__main__":
    unittest.main()
