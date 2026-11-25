#!/usr/bin/env python3
"""Check the invariants that make this composite action safe to consume.

`action.yml` is the product, and the two rules that matter most about it are about text, not
semantics: no expression may be interpolated into a shell command, in a block scalar or on the
line beside `run:`, and every third-party step must be pinned by commit sha. A reviewer can
miss either one in a diff, and a runner will not complain until the workflow has already run
with the caller's token. The file also holds its shape: `using: composite`, a shell named by
every step that runs, and every declared input reaching a step, the token included. This script
checks all of it without a YAML parser, so it runs on the runner's own python3 like the rest of
`scripts/`.

Exit codes: 0 the file holds, 2 it does not. Every problem is reported in one pass.
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

SHA_PIN = re.compile(r"^[A-Za-z0-9._/-]+@[0-9a-f]{40}( # v\S+)?$")
INPUT_REF = re.compile(
    r"""\$\{\{\s*inputs(?:\.([a-z0-9-]+)|\[\s*['"]([a-z0-9-]+)['"]\s*\])\s*\}\}"""
)
STEP_ID = re.compile(r"^\s{6}id:\s*([a-z0-9-]+)\s*$")
STEP_START = re.compile(r"^\s{4}- (?:name|uses):")
RUN_ANY = re.compile(r"^\s+run:")
RUN_BLOCK = re.compile(r"^(\s+)run:\s*\|")
RUN_INLINE = re.compile(r"^\s+run:\s*(\S.*)$")
SHELL_KEY = re.compile(r"^\s+shell:\s*\S")
USING_KEY = re.compile(r"^\s+using:\s*(\S+)")
KEY_START = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_.-]*:")
LIST_START = re.compile(r"^\s*- ")


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


def input_refs(line: str) -> list[str]:
    """Every input name a line references, in dot or in bracket form.

    `inputs.title`, `inputs['title']` and `inputs["title"]` are the same expression to the
    runner, so both rules that read input references — the `env:` binding collection and the
    run-block scan — have to see all three spellings. A bracket reference the pattern misses
    does not simply go uncounted: the input reads as declared and never bound, which is a
    refusal the file cannot answer because it does bind the input.
    """
    return [dotted or bracketed for dotted, bracketed in INPUT_REF.findall(line)]


def ends_body(line: str, key_indent: int) -> bool:
    """True when a non-blank line starts the YAML node that ends a `run:` block.

    A block scalar's body is whatever is indented past its key, and what ends it is the step's
    next key or the next step. Reading the indent off the `run:` key is what makes that work at
    any depth: the eight spaces this scanner used to compare against belong to one file's shape,
    and against any other they either cut the body short before anything was read — so the scan
    examined nothing — or run straight through the step's later keys and blame them for holding
    the expressions they legitimately hold.
    """
    if len(line) - len(line.lstrip()) > key_indent:
        return False
    return bool(KEY_START.match(line) or LIST_START.match(line))


def run_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """(1-based line of the body's first line, body) for every `run:` step in the file.

    Both spellings count: the block scalar introduced by `run: |`, and the one line written
    beside the key as `run: echo`. The second is what #66 found missing — an expression in a
    one-line run is the same shell injection as one in a block, and the block path alone let
    it through. Counting from the body rather than the key is what makes the reported number
    the line a reader needs to land on: for the one-line form the two are the same line, and
    for the block form the key is the line above the offending shell text.
    """
    blocks: list[tuple[int, list[str]]] = []
    index = 0
    while index < len(lines):
        block = RUN_BLOCK.match(lines[index])
        if block:
            key_indent = len(block.group(1))
            start = index + 2
            body: list[str] = []
            index += 1
            while index < len(lines):
                line = lines[index]
                if line.strip() and ends_body(line, key_indent):
                    break
                body.append(line)
                index += 1
            blocks.append((start, body))
            continue
        inline = RUN_INLINE.match(lines[index])
        if inline:
            blocks.append((index + 1, [inline.group(1)]))
        index += 1
    return blocks


def step_spans(lines: list[str]) -> list[tuple[int, list[str]]]:
    """(first line number, body) for every step, from its `- name:` or `- uses:` line.

    A step ends where the next one begins, which is the shape the composite file is written
    in: four spaces of indent for the list item, six for its keys.
    """
    starts = [index for index, line in enumerate(lines) if STEP_START.match(line)]
    starts.append(len(lines))
    return [(start + 1, lines[start:end]) for start, end in itertools.pairwise(starts)]


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
            bound.update(input_refs(match.group(1)))
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
            used.update(input_refs(line))
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

    id_lines: dict[str, list[int]] = {}
    for number, line in enumerate(lines, start=1):
        step_id = STEP_ID.match(line)
        if step_id:
            id_lines.setdefault(step_id.group(1), []).append(number)
    for name, numbers in sorted(id_lines.items()):
        for first, second in itertools.pairwise(numbers):
            problems.append(
                f"step id {name!r} appears on lines {first} and {second}: the runner resolves "
                "`steps.{id}.outputs.*` to one of them, and which one is not visible in the file"
            )

    for number, line in enumerate(lines, start=1):
        output = re.match(r"^\s+value:\s*\$\{\{\s*steps\.([a-z0-9-]+)\.", line)
        if output and output.group(1) not in id_lines:
            problems.append(
                f"line {number}: output refers to step id {output.group(1)!r}, "
                "and no step in the file carries that id"
            )

    declared_using = [
        (number, using.group(1))
        for number, line in enumerate(lines, start=1)
        if (using := USING_KEY.match(line))
    ]
    if not declared_using:
        problems.append(
            "runs: declares no using:, so nothing in the file says what shape the runner is loading"
        )
    for number, value in declared_using:
        if value != "composite":
            problems.append(
                f"line {number}: runs.using is {value!r} and this action is composite; the "
                "shape is a decision in ROADMAP.md, and every run: line means something "
                "different the moment it changes"
            )

    for number, body in step_spans(lines):
        if not any(RUN_ANY.match(line) for line in body):
            continue
        if any(SHELL_KEY.match(line) for line in body):
            continue
        problems.append(
            f"line {number}: step {body[0].strip()!r} has a run: without a shell:, which the "
            "runner only refuses when it loads the file, after a consumer has adopted the tag"
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
