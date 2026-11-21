from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.check_action import SHA_PIN

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?(?:uses|'uses'|\"uses\")\s*:\s*(.*?)\s*$")
FLOW_STEP = re.compile(r"^\s*(?:-\s*\{|(?:steps|jobs)\s*:\s*[\[{])")
FLOW_USES = re.compile(r"[,\{]\s*(?:uses|'uses'|\"uses\")\s*:\s*([^,}\s]+)")
BLOCK_SCALAR = re.compile(r"^\s*(?:-\s*)?[^:#]+:\s*[|>][-+1-9]*\s*(?:#.*)?$")
VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")


def uses_lines(text: str) -> list[tuple[int, str]]:
    found = []
    scalar_indent: int | None = None
    for line_number, line in enumerate(text.splitlines(), 1):
        indent = len(line) - len(line.lstrip())
        if scalar_indent is not None:
            if not line.strip() or indent > scalar_indent:
                continue
            scalar_indent = None
        match = USES.match(line)
        if match:
            found.append((line_number, match.group(1)))
        elif FLOW_STEP.match(line):
            _, separator, comment = line.partition(" # ")
            for flow_match in FLOW_USES.finditer(line):
                found.append((line_number, flow_match.group(1) + separator + comment))
        if BLOCK_SCALAR.match(line):
            scalar_indent = indent
    return found


def pin_problems(text: str, path: str) -> list[str]:
    problems = []
    for line_number, value in uses_lines(text):
        reference, separator, comment = value.partition(" # ")
        if len(reference) >= 2 and reference[0] in "\"'" and reference[-1] == reference[0]:
            reference = reference[1:-1]
        if reference.startswith("./") and not any(char.isspace() for char in reference):
            continue
        segments = reference.split("@", 1)[0].split("/")
        if (
            not SHA_PIN.fullmatch(reference + separator + comment)
            or not separator
            or not VERSION.fullmatch(comment)
            or len(segments) < 2
            or not all(segments)
        ):
            problems.append(
                f"{path}:{line_number}: action must use a full SHA and # vX.Y.Z: {value}"
            )
    return problems


class TestWorkflowPins(unittest.TestCase):
    def test_all_shipped_workflow_uses_are_pinned_or_local(self) -> None:
        workflows = sorted(WORKFLOWS.rglob("*.yml"))
        self.assertTrue(workflows, "No workflow files found")
        references = []
        problems = []
        for workflow in workflows:
            text = workflow.read_text(encoding="utf-8")
            relative = workflow.relative_to(ROOT).as_posix()
            references.extend(uses_lines(text))
            problems.extend(pin_problems(text, relative))
        self.assertTrue(references, "No workflow action references found")
        self.assertEqual(problems, [])

    def test_local_and_nested_actions_are_allowed(self) -> None:
        text = (
            f"- uses: ./\n- uses: './path/action'\n- uses: \"owner/repo/sub@{'a' * 40}\" # v1.2.3\n"
        )
        self.assertEqual(pin_problems(text, "fixture.yml"), [])

    def test_floating_and_uncommented_mutations_report_file_and_line(self) -> None:
        for value in (
            "actions/checkout@v4 # v4.0.0",
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        ):
            with self.subTest(value=value):
                problems = pin_problems(f"steps:\n  - uses: {value}\n", "fixture.yml")
                self.assertEqual(len(problems), 1)
                self.assertIn("fixture.yml:2:", problems[0])
                self.assertIn(value, problems[0])

    def test_yaml_key_spacing_and_block_scalars_do_not_hide_or_invent_uses(self) -> None:
        text = "steps:\n  - run: |\n      uses: not-an-action\n  - uses : actions/checkout@v4\n"
        problems = pin_problems(text, "fixture.yml")
        self.assertEqual(len(problems), 1)
        self.assertIn("fixture.yml:4:", problems[0])
        self.assertIn("actions/checkout@v4", problems[0])

    def test_inline_steps_are_scanned(self) -> None:
        text = (
            "steps:\n"
            "  - {uses: ./}\n"
            "  - {name: checkout, uses: actions/checkout@v4}\n"
            f"  - {{uses: owner/repo@{'a' * 40}}} # v1.2.3\n"
        )
        self.assertEqual(len(uses_lines(text)), 3)
        problems = pin_problems(text, "fixture.yml")
        self.assertEqual(len(problems), 1)
        self.assertIn("fixture.yml:3:", problems[0])
        for line in (
            "steps: [{uses: actions/checkout@v4}]",
            "jobs: {check: {uses: owner/repo@v4}}",
        ):
            with self.subTest(line=line):
                self.assertEqual(len(pin_problems(line, "fixture.yml")), 1)

    def test_remote_requires_version_comment_and_owner_repo(self) -> None:
        for value in (f"owner/repo@{'a' * 40} # v4", f"repo@{'a' * 40} # v1.2.3"):
            with self.subTest(value=value):
                self.assertEqual(len(pin_problems(f"- uses: {value}\n", "fixture.yml")), 1)


if __name__ == "__main__":
    unittest.main()
