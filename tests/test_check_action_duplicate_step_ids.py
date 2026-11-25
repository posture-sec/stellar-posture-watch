#!/usr/bin/env python3
"""Tests for repeated step ids in `scripts/check_action.py` (#80).

`check()` collected step ids into a set, so a second step declaring `id: gauge` made the
collection task for the output check and reported nothing: `steps.gauge.outputs.exit-code` resolves
to one of the two steps, and which one is not visible in the file. On the shipped action that
output drives the artifact condition and the propagate step, so a collision silently changes which
result a run reports. The ids are now a map from name to the lines carrying it, which both names
the collision and keeps feeding the output check.

Each case is one file with one shape and the findings it should produce. The pre-change answer for
every duplicate case here was an empty list.

Nothing here reaches the network or parses YAML, same as the checker.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from action_fixture import GOOD, check_action, problems

ROOT = Path(__file__).resolve().parent.parent

PAIR = re.compile(r"appears on lines (\d+) and (\d+)")


def step(number: int, step_id: str) -> str:
    """One more step for `GOOD`, carrying `step_id`."""
    return f"""
    - name: Extra {number}
      id: {step_id}
      shell: bash
      run: |
        echo "extra {number}"
"""


def lines(text: str, needle: str) -> list[int]:
    """Every 1-based line number of `text` holding `needle`, in order."""
    return [number for number, line in enumerate(text.splitlines(), start=1) if needle in line]


def reported_pairs(found: list[str]) -> list[tuple[int, int]]:
    matches = [PAIR.search(line) for line in found if PAIR.search(line)]
    return [(int(first), int(second)) for first, second in (m.groups() for m in matches)]


class RepeatedId(unittest.TestCase):
    def test_two_steps_sharing_an_id_are_named_with_both_lines(self) -> None:
        text = GOOD + step(1, "audit")
        found = [line for line in problems(text) if "step id" in line]
        self.assertEqual(len(found), 1, found)
        self.assertIn("step id 'audit'", found[0])
        first, second = lines(text, "id: audit")
        self.assertEqual(reported_pairs(found), [(first, second)])

    def test_three_steps_sharing_an_id_produce_two_problems(self) -> None:
        text = GOOD + step(1, "audit") + step(2, "audit")
        found = [line for line in problems(text) if "step id" in line]
        first, second, third = lines(text, "id: audit")
        self.assertEqual(reported_pairs(found), [(first, second), (second, third)])

    def test_a_collision_does_not_also_lose_the_output(self) -> None:
        # The output check reads the same map, so an id declared twice is still a known id and
        # `outputs.exit-code` is not additionally reported as pointing at nothing.
        text = GOOD + step(1, "audit")
        self.assertEqual([line for line in problems(text) if "no step in the file" in line], [])

    def test_the_only_new_problem_is_the_collision(self) -> None:
        # Nothing else in the file changes when an id repeats, so an extra finding here means the
        # rule was widened past what #80 asked for.
        self.assertEqual(len(problems(GOOD + step(1, "audit"))), 1)


class DistinctIds(unittest.TestCase):
    def test_unique_ids_are_clean(self) -> None:
        self.assertEqual(problems(GOOD + step(1, "build") + step(2, "sync")), [])

    def test_a_single_id_is_clean(self) -> None:
        self.assertEqual(problems(GOOD), [])


class ShippedFile(unittest.TestCase):
    def test_action_yml_declares_each_id_once(self) -> None:
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertEqual(
            [line for line in check_action.check(ROOT / "action.yml") if "step id" in line], []
        )
        self.assertEqual(len(lines(text, "id: gauge")), 1)

    def test_gauge_is_the_id_the_outputs_read(self) -> None:
        # The rule only matters because the file depends on it: the outputs resolve through
        # `steps.gauge`, so an added `id: gauge` is the collision this catches.
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("      id: gauge\n", text)
        self.assertTrue(len(lines(text, "steps.gauge.outputs.")) > 1)
        collided = text.replace(
            "    - name: Find the tracking issue\n      id: find\n",
            "    - name: Find the tracking issue\n      id: gauge\n",
        )
        self.assertNotEqual(collided, text)
        found = [line for line in problems(collided) if "step id 'gauge'" in line]
        self.assertEqual(len(found), 1, found)


if __name__ == "__main__":
    unittest.main()
