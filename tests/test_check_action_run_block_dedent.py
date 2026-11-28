#!/usr/bin/env python3
"""Tests for the indentation-relative run-block scanner in `scripts/check_action.py` (#78).

`run_blocks()` decided where a `run: |` body ends by comparing each line against eight literal
spaces, which is the depth of this repository's own `action.yml` and of nothing else. Two shapes
escaped: a step list one level shallower recorded an empty body, so the scan that looks for an
expression reaching the shell had nothing to look at, and a step list one level deeper swallowed
the step's later keys, so an `env:` mapping written after the `run:` block was reported as if it
were shell code. Both cases here fix one shape, and the control case is the shipped depth, which
the change must not move.

Nothing here reaches the network or parses YAML, same as the checker.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import unittest

from action_fixture import GOOD, check_action, line_of, mentions, problems

SHALLOW_HEADER = """name: Shallow
description: A composite action with its step list one level up from the shipped file.

inputs:
  gauge-ref:
    description: Full commit sha.
    required: true
  config:
    description: Policy path.
    required: false
    default: gauge.toml

runs:
  using: composite
  steps:
"""

# `run:` at four spaces, body at six: every body line used to fail the eight-space test.
SHALLOW = (
    SHALLOW_HEADER
    + """  - name: Check the inputs
    shell: bash
    env:
      CONFIG: ${{ inputs.config }}
    run: |
      echo "$CONFIG"
      echo "${{ inputs.gauge-ref }}"
"""
)

DEEP_HEADER = """name: Deep
description: A composite action with its step list one level down from the shipped file.

inputs:
  gauge-ref:
    description: Full commit sha.
    required: true
  config:
    description: Policy path.
    required: false
    default: gauge.toml

runs:
  using: composite
  steps:
"""

# `run:` at eight spaces, body at ten, and the step's own `env:` mapping written after it.
DEEP = (
    DEEP_HEADER
    + """      - name: Check the inputs
        shell: bash
        run: |
          echo "nothing to interpolate"
        env:
          CONFIG: ${{ inputs.config }}
          GAUGE_REF: ${{ inputs.gauge-ref }}
"""
)


def body_of(text: str) -> list[str]:
    """The non-blank lines of the one `run: |` block in `text`."""
    blocks = check_action.run_blocks(text.splitlines())
    assert len(blocks) == 1, blocks
    return [line for line in blocks[0][1] if line.strip()]


class ShippedDepth(unittest.TestCase):
    def test_the_control_block_is_still_read_in_full(self) -> None:
        # `GOOD` is written at the depth `action.yml` uses: `run:` at six, body at eight. The
        # rule that reads it now has to give the answer the literal eight spaces gave then.
        blocks = check_action.run_blocks(GOOD.splitlines())
        self.assertEqual(len(blocks), 2, blocks)
        self.assertEqual(
            [line.strip() for line in blocks[0][1] if line.strip()],
            ['echo "$CONFIG" "$GAUGE_REF"'],
        )
        self.assertEqual(problems(GOOD), [])


class DedentedBody(unittest.TestCase):
    def test_a_six_space_body_is_scanned(self) -> None:
        self.assertEqual(
            [line.strip() for line in body_of(SHALLOW)],
            ['echo "$CONFIG"', 'echo "${{ inputs.gauge-ref }}"'],
        )

    def test_an_expression_in_a_dedented_body_is_refused(self) -> None:
        found = problems(SHALLOW)
        self.assertEqual(len(found), 1, found)
        self.assertIn("reaches the shell", found[0])
        self.assertIn(f"line {line_of(SHALLOW, 'inputs.gauge-ref')}", found[0])


class DeeperBody(unittest.TestCase):
    def test_the_block_stops_at_its_sibling_key(self) -> None:
        self.assertEqual(
            [line.strip() for line in body_of(DEEP)], ['echo "nothing to interpolate"']
        )

    def test_a_sibling_expression_is_not_attributed_to_the_block(self) -> None:
        # The `env:` mapping is where the checker tells you to put an expression, and it sits at
        # the same indent as a `run:` key eight spaces deep. Swallowing it produced this refusal.
        self.assertEqual(mentions(problems(DEEP), "reaches the shell"), [])

    def test_the_deeper_file_holds_its_rules(self) -> None:
        self.assertEqual(problems(DEEP), [])


if __name__ == "__main__":
    unittest.main()
