from __future__ import annotations

import unittest
from pathlib import Path

from test_workflows_pins import uses_lines

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "example" / "workflow.yml"
ACTION = "posture-sec/stellar-posture-watch"
PLACEHOLDER = "REPLACE-WITH-A-SHA-YOU-READ"


def placeholder_problems(text: str, path: str) -> list[str]:
    lines = text.splitlines()
    references: list[tuple[int, str]] = []
    for line_number, value in uses_lines(text):
        target = value.partition(" # ")[0].strip("\"'")
        if target.split("@", 1)[0].lower() == ACTION:
            references.append((line_number, target))
    if len(references) != 1:
        location = references[0][0] if references else 1
        return [f"{path}:{location}: expected exactly one reference to {ACTION}"]

    line_number, target = references[0]
    problems = []
    if target != f"{ACTION}@{PLACEHOLDER}":
        problems.append(f"{path}:{line_number}: expected {ACTION}@{PLACEHOLDER}, got {target}")
    comment_lines = []
    for line in reversed(lines[: line_number - 1]):
        if not line.lstrip().startswith("#"):
            break
        comment_lines.append(line.strip().lower())
    comment = " ".join(reversed(comment_lines))
    if not all(
        phrase in comment
        for phrase in ("40-character", "sha", "tag", "code that runs change", "without a diff")
    ):
        problems.append(f"{path}:{line_number}: missing SHA and tag-risk explanation")
    return problems


class TestExamplePinPlaceholder(unittest.TestCase):
    def setUp(self) -> None:
        self.text = EXAMPLE.read_text(encoding="utf-8")
        self.path = "example/workflow.yml"

    def test_example_keeps_the_single_explained_placeholder(self) -> None:
        self.assertEqual(placeholder_problems(self.text, self.path), [])

    def test_tag_and_sha_mutations_are_rejected_with_file_and_line(self) -> None:
        for ref in ("v0.1.0", "fbcd9a45fbce1d275fc0ad0dd13626e165b354ef"):
            with self.subTest(ref=ref):
                mutated = self.text.replace(PLACEHOLDER, ref)
                problems = placeholder_problems(mutated, self.path)
                self.assertEqual(len(problems), 1)
                self.assertRegex(problems[0], r"^example/workflow\.yml:\d+:")
                self.assertIn(f"got {ACTION}@{ref}", problems[0])

    def test_missing_comment_or_duplicate_reference_is_rejected(self) -> None:
        without_risk = self.text.replace("without a diff", "without a review")
        self.assertIn("tag-risk explanation", placeholder_problems(without_risk, self.path)[0])
        duplicate = self.text + f"\n      - uses: {ACTION}@{PLACEHOLDER}\n"
        self.assertIn(
            "expected exactly one reference", placeholder_problems(duplicate, self.path)[0]
        )
        inline = self.text + f"\n      - {{uses: {ACTION}@v0.1.0}}\n"
        self.assertIn("expected exactly one reference", placeholder_problems(inline, self.path)[0])


if __name__ == "__main__":
    unittest.main()
