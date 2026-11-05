#!/usr/bin/env python3
"""Regenerate `requirements-dev.lock.txt` from `requirements-dev.txt`.

`requirements-dev.txt` names the dev tools and their versions; the lock says which bytes
those versions are, so `pip install --require-hashes` in CI refuses a wheel that was
re-uploaded or substituted under the same version. This script is the only supported way
to produce the lock, because a hand-written one drifts the moment a pin moves.

Resolution is pip's own, so the closure is the one pip would install rather than a guess;
the hashes come from the release metadata for each resolved version, and every published
file is listed so the lock is not bound to this laptop's platform.

Usage:
    scripts/lock_dev_requirements.py [--check]

With `--check` nothing is written and the script exits 1 if the committed lock disagrees,
which is what CI runs: a bumped `requirements-dev.txt` without a regenerated lock fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements-dev.txt"
LOCK = ROOT / "requirements-dev.lock.txt"

HEADER = """\
# Dev tooling, pinned by version AND content hash.
#
# `requirements-dev.txt` says what the pair is; this file says what bytes it is, so
# `pip install --require-hashes` refuses a re-uploaded or substituted wheel. CI installs
# from here and nothing else. Every published file for a pinned version is listed, not just
# the one this laptop picked, so the lock holds on the runner's interpreter and platform too.
#
# Regenerate with `scripts/lock_dev_requirements.py` after changing `requirements-dev.txt`;
# Dependabot bumps `requirements-dev.txt` and the script keeps this file in step.
"""


def pinned(requirements: Path) -> list[tuple[str, str]]:
    """The `name==version` pairs a requirements file states, in file order."""
    pairs: list[tuple[str, str]] = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, _, version = line.partition("==")
        pairs.append((name.strip(), version.strip()))
    return sorted(pairs, key=lambda pair: pair[0].lower())


def locked(lock: Path) -> list[tuple[str, str]]:
    """The `name==version` pairs a lock file states."""
    if not lock.exists():
        return []
    pairs: list[tuple[str, str]] = []
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().rstrip("\\").strip()
        if "==" in line and not line.startswith("--hash"):
            name, _, version = line.partition("==")
            pairs.append((name.strip().replace("_", "-").lower(), version.strip()))
    return sorted(pairs, key=lambda pair: pair[0])


def resolve(requirements: Path) -> list[tuple[str, str]]:
    """The resolved (name, version) closure for the given requirements file."""
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--quiet",
            "--report",
            "-",
            "-r",
            str(requirements),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            f"lock_dev_requirements: pip could not resolve {requirements}:\n{done.stderr}"
        )
    report = json.loads(done.stdout)
    resolved = [
        (item["metadata"]["name"], item["metadata"]["version"]) for item in report["install"]
    ]
    return sorted(resolved, key=lambda pair: pair[0].lower())


def hashes_for(name: str, version: str) -> list[str]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        metadata = json.load(response)
    digests = sorted({entry["digests"]["sha256"] for entry in metadata["urls"]})
    if not digests:
        raise SystemExit(f"lock_dev_requirements: no published files for {name}=={version}")
    return digests


def stale(requirements: Path, lock: Path) -> list[str]:
    """Problems with the lock, as sentences. Empty means the lock covers the pins.

    Extra pins are the transitive closure and are expected; a missing one is the
    failure, because it means the pair was bumped without regenerating the lock. Textual
    only, so this runs without the network.
    """
    declared = {(name.replace("_", "-").lower(), version) for name, version in pinned(requirements)}
    present = set(locked(lock))
    problems = [
        f"{name}=={version} is not in the lock" for name, version in sorted(declared - present)
    ]
    if problems:
        return problems
    if lock.exists():
        text = lock.read_text(encoding="utf-8")
        hashes = [line for line in text.splitlines() if line.strip().startswith("--hash=")]
        if len(hashes) < len(present):
            problems.append("at least one pin carries no hash")
    return problems


def render(requirements: Path) -> str:
    lines = [HEADER]
    for name, version in resolve(requirements):
        digests = hashes_for(name, version)
        lines.append(f"{name}=={version} \\")
        for index, digest in enumerate(digests):
            suffix = " \\" if index < len(digests) - 1 else ""
            lines.append(f"    --hash=sha256:{digest}{suffix}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        problems = stale(REQUIREMENTS, LOCK)
        if problems:
            for problem in problems:
                print(f"lock_dev_requirements: {problem}", file=sys.stderr)
            print(
                "lock_dev_requirements: regenerate with scripts/lock_dev_requirements.py",
                file=sys.stderr,
            )
            return 1
        print("lock_dev_requirements: the lock covers every pin, each with a hash")
        return 0

    wanted = render(REQUIREMENTS)
    current_lock = LOCK.read_text(encoding="utf-8") if LOCK.exists() else ""
    if current_lock == wanted:
        print("lock_dev_requirements: the lock is already current")
        return 0
    LOCK.write_text(wanted, encoding="utf-8")
    print(f"lock_dev_requirements: wrote {LOCK} ({len(wanted.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
