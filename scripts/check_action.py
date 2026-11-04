#!/usr/bin/env python3
"""Check the invariants that make this composite action safe to consume.

`action.yml` is the product, and the two rules that matter most about it are about text, not
semantics: no expression may be interpolated into a shell command, and every third-party step
must be pinned by commit sha. A reviewer can miss either one in a diff, and a runner will not
complain until the workflow has already run with the caller's token. This script checks both
without a YAML parser, so it runs on the runner's own python3 like the rest of `scripts/`.

Exit codes: 0 the file holds, 2 it does not. Every problem is reported in one pass.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SHA_PIN = re.compile(r"^[A-Za-z0-9._/-]+@[0-9a-f]{40}( # v\S+)?$")
INPUT_REF = re.compile(r"\$\{\{\s*inputs\.([a-z0-9-]+)\s*\}\}")
STEP_ID = re.compile(r"^\s{6}id:\s*([a-z0-9-]+)\s*$")


def input_names(lines: list[str]) -> dict[str, list[str]]:
    """Each input name in the `inputs:` block with the lines that describe it."""
    found: dict[str, list[str]] = {}
    in_inputs = False
    current: str | None = None
    for line in lines:
        if line.startswith("inputs:"):
            in_inputs = True
            continue
        if in_inputs and line and not line.startswith("  "):
            break
        if not in_inputs:
            continue
        name = re.fullmatch(r"  ([a-z0-9-]+):", line)
        if name:
            current = name.group(1)
            found.setdefault(current, [])
        elif current and line.startswith("    "):
            found[current].append(line.strip())
    return found


def run_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """(starting line number, body) for every `run: |` block."""
    blocks: list[tuple[int, list[str]]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s+run:\s*\|", lines[index]):
            start = index + 1
            body: list[str] = []
            index += 1
            while index < len(lines):
                line = lines[index]
                if line.strip() and not line.startswith(" " * 8):
                    break
                body.append(line)
                index += 1
            blocks.append((start, body))
            continue
        index += 1
    return blocks


def step_env_names(lines: list[str]) -> set[str]:
    """The input names bound through `env:` mappings anywhere in the file."""
    bound: set[str] = set()
    in_env = False
    for line in lines:
        if re.match(r"^\s+env:\s*$", line):
            in_env = True
            continue
        if in_env:
            match = re.match(r"^\s+[A-Z_][A-Z0-9_]*:\s*(.*)$", line)
            if not match:
                in_env = False
                continue
            bound.update(INPUT_REF.findall(match.group(1)))
    return bound


def check(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: cannot read it ({exc})"]
    lines = text.splitlines()
    if not lines:
        return [f"{path}: is empty"]

    declared = input_names(lines)
    if not declared:
        problems.append("the inputs: block names no input, so the file is not an action")

    gauge_ref = declared.get("gauge-ref")
    if gauge_ref is None:
        problems.append("gauge-ref is not declared, so nothing pins the code that gets built")
    else:
        if not any(line.startswith("required: true") for line in gauge_ref):
            problems.append("gauge-ref must be required: true")
        if any(line.startswith("default:") for line in gauge_ref):
            problems.append("gauge-ref must have no default: a stale pin is a silent downgrade")

    used: set[str] = set()
    for number, body in run_blocks(lines):
        for offset, line in enumerate(body):
            used.update(INPUT_REF.findall(line))
            if "${{" in line:
                problems.append(
                    f"line {number + offset}: an expression inside a run: block reaches the "
                    "shell; bind it through env: instead"
                )
    for name in sorted(used):
        if name not in declared:
            problems.append(f"{name} is used in a run: block but is not declared in inputs:")

    bound = step_env_names(lines)
    for name in sorted(declared):
        if name == "github-token":
            continue
        if name not in bound and name not in used:
            problems.append(
                f"input {name} is declared but never bound in an env: mapping, so no step "
                "receives it"
            )

    for number, line in enumerate(lines, start=1):
        uses = re.match(r"^\s+uses:\s*(\S+)\s*(?:#.*)?$", line)
        if not uses:
            continue
        target = uses.group(1)
        if target.startswith("./") or target.startswith("docker://"):
            continue
        tail = target.split("@", 1)[1] if "@" in target else ""
        if not re.fullmatch(r"[0-9a-f]{40}", tail):
            problems.append(
                f"line {number}: {target} is not pinned by a full 40-character commit sha"
            )
        elif "#" not in line:
            problems.append(
                f"line {number}: {target} has no comment naming the release the sha resolved "
                "from, so nobody can tell which commit was read"
            )

    ids = {m.group(1) for m in (STEP_ID.match(line) for line in lines) if m}
    for number, line in enumerate(lines, start=1):
        output = re.match(r"^\s+value:\s*\$\{\{\s*steps\.([a-z0-9-]+)\.", line)
        if output and output.group(1) not in ids:
            problems.append(
                f"line {number}: output refers to step id {output.group(1)!r}, "
                "and no step in the file carries that id"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    target = Path(args[0]) if args else Path("action.yml")
    problems = check(target)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"check_action: {target} breaks {len(problems)} rule(s)", file=sys.stderr)
        return 2
    print(f"check_action: {target} holds its rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
