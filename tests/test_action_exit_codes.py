#!/usr/bin/env python3
"""Drive the exit-code mapping in `action.yml` as a table, locally.

The last step of the composite action is where D-05 becomes an exit code: a scheduled run stays
green while Gauge reported findings and goes red when a read did not happen. Until this file
nothing on a desk executed it. `scripts/check_action.py` is a text scanner by D-09, so a dropped
`exit` or a moved 0/1 boundary was visible only after a push, on a runner, with the caller's
token in the job. The block needs nothing to run: two environment variables in, at most one line
out, and `bash` on the path.

The script is read out of `action.yml` instead of copied here. A copy keeps passing after the
file it stands for changes, which is the exact failure this test exists to close, so the
extractor fails loudly when the step is renamed or stops being a `case` statement.
"""

from __future__ import annotations

import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTION_FILE = ROOT / "action.yml"
STEP_NAME = "Propagate a hard failure, and findings only when asked"

# A step item's keys sit at six spaces and the item itself at four, so anything back at four
# belongs to a sibling step rather than to the one being read.
STEP_INDENT = 4

FINDINGS_AND_BREAK = "gauge reported findings and break-build is true"
FINDINGS_ON_ISSUE = "gauge reported findings; the tracking issue carries them"
REFUSED = "gauge refused the configuration (exit 2)"
COULD_NOT_READ = "gauge could not read the account (exit 3)"

UNKNOWN = "gauge exited with {}, which this action does not understand"
UNEXPECTED = "gauge exited with 4, which this action does not understand"
# `steps.gauge.outputs.exit-code` is an empty string when the gauge step did not run at all,
# which is the case that reaches the mapping with nothing in it.
UNSET = UNKNOWN.format("")

# GAUGE_EXIT, BREAK_BUILD, exit code, the one line the step prints.
TABLE: list[tuple[str, str, int, str]] = [
    ("0", "true", 0, ""),
    ("0", "false", 0, ""),
    ("1", "true", 1, FINDINGS_AND_BREAK),
    ("1", "false", 0, FINDINGS_ON_ISSUE),
    ("2", "true", 2, REFUSED),
    ("2", "false", 2, REFUSED),
    ("3", "true", 3, COULD_NOT_READ),
    ("3", "false", 3, COULD_NOT_READ),
    ("4", "true", 2, UNEXPECTED),
    ("4", "false", 2, UNEXPECTED),
    ("", "true", 2, UNSET),
    ("", "false", 2, UNSET),
]


def step_run_block(text: str, step_name: str = STEP_NAME) -> list[str]:
    """The `run:` block of the single step named `step_name`, dedented to column zero.

    `AssertionError` rather than an empty list: a renamed step has to say its own name in the
    failure, or the table below would be describing a block nobody wrote.
    """
    lines = text.splitlines()
    header = f"- name: {step_name}"
    starts = [index for index, line in enumerate(lines) if line.strip() == header]
    if len(starts) != 1:
        raise AssertionError(
            f"action.yml holds {len(starts)} steps named {step_name!r}; this test names one"
        )
    run_at: int | None = None
    for index in range(starts[0] + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped:
            continue
        if len(lines[index]) - len(lines[index].lstrip()) <= STEP_INDENT:
            break
        if stripped.startswith("run:"):
            run_at = index
            break
    if run_at is None:
        raise AssertionError(f"the step {step_name!r} has no run: block to execute")

    body: list[str] = []
    for line in lines[run_at + 1 :]:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if indent <= STEP_INDENT:
                break
        body.append(line)
    if not [line for line in body if line.strip()]:
        raise AssertionError(f"the step {step_name!r} has an empty run: block")
    return textwrap.dedent("\n".join(body)).splitlines()


def mapping_script() -> str:
    """The step's bash, straight from the file, and only while it is still a case statement.

    The closing `esac` is what makes the rest of this file meaningful: a block that ends some
    other way is a different shape of step, and running it against a table written for a `case`
    would report a colour that came from the test rather than from the action.
    """
    block = step_run_block(ACTION_FILE.read_text(encoding="utf-8"))
    arms = [line.strip() for line in block if line.strip()]
    if not arms or arms[-1] != "esac":
        raise AssertionError(
            f"the step {STEP_NAME!r} no longer ends in esac, so it is not the exit-code "
            "mapping this table drives; read the step and update this test with it"
        )
    return "\n".join(block) + "\n"


def run(gauge_exit: str, break_build: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", mapping_script()],
        env={"GAUGE_EXIT": gauge_exit, "BREAK_BUILD": break_build},
        capture_output=True,
        text=True,
        check=False,
    )


class TestExitCodeMapping(unittest.TestCase):
    def test_the_table(self) -> None:
        # Every row is one colour of one scheduled run. `break-build` moves row 1 and nothing
        # else, because 2 and 3 mean nothing was read and an unknown exit is refused outright.
        for gauge_exit, break_build, expected_code, expected_out in TABLE:
            proc = run(gauge_exit, break_build)
            where = f"GAUGE_EXIT={gauge_exit!r} BREAK_BUILD={break_build!r}"
            self.assertEqual(proc.returncode, expected_code, f"{where}: {proc.stderr}")
            self.assertEqual(proc.stdout, f"{expected_out}\n" if expected_out else "", where)
            self.assertEqual(proc.stderr, "", where)

    def test_twelve_rows_cover_six_exits_and_both_flags(self) -> None:
        exits = {row[0] for row in TABLE}
        self.assertEqual(exits, {"0", "1", "2", "3", "4", ""})
        self.assertEqual(len(TABLE), 12)
        for gauge_exit in exits:
            flags = sorted(row[1] for row in TABLE if row[0] == gauge_exit)
            self.assertEqual(flags, ["false", "true"], gauge_exit)

    def test_both_finding_messages_are_distinct(self) -> None:
        # D-05 turns on which of these a reader sees, so a table that asserted the same line for
        # both would pass while the step said nothing about the flag.
        on = run("1", "true")
        off = run("1", "false")
        self.assertNotEqual(on.stdout, off.stdout)
        self.assertEqual((on.returncode, off.returncode), (1, 0))

    def test_the_block_holds_no_expression_interpolation(self) -> None:
        # CONTRIBUTING's rule for every step: an input reaches bash through `env:`, never
        # through `${{ }}` inside the script, which is the class of bug that makes a composite
        # action dangerous.
        self.assertNotIn("${{", mapping_script())

    def test_the_block_starts_under_strict_shell_options(self) -> None:
        # `set -u` is why the empty row above is a real case rather than a hypothetical one: an
        # unset variable would kill the step before the mapping ran.
        block = step_run_block(ACTION_FILE.read_text(encoding="utf-8"))
        self.assertEqual(block[0], "set -uo pipefail")

    def test_the_mapping_is_the_last_step_of_the_action(self) -> None:
        lines = ACTION_FILE.read_text(encoding="utf-8").splitlines()
        steps = [line for line in lines if line.strip().startswith("- name: ")]
        self.assertTrue(steps[-1].strip().endswith(STEP_NAME))


if __name__ == "__main__":
    unittest.main()
