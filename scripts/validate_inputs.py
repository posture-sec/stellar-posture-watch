#!/usr/bin/env python3
"""Refuse an unusable or unsafe Action configuration before anything is built.

The watch checks out a repository at a commit and compiles Go code from it, so the
inputs are part of the trust path. This script is the only gate in front of that, and
it is deliberately narrow: it checks the things Gauge cannot see, because they are
Action inputs rather than policy fields. Gauge stays the authority on policy meaning.
If the two ever disagree about a policy file, Gauge's exit 2 is the one that ships.

Exit codes: 0 the run is safe to start, 2 refused.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

MAX_CONFIG_BYTES = 1024 * 1024
MAX_CONFIG_FILES = 10
KEY_UNSAFE = re.compile(r"[^a-z0-9]+")
MAX_TEXT_INPUT = 256
NETWORK_KEYWORDS = ("mainnet", "testnet")

# A secret seed is the same length and alphabet as an account id with a different
# version byte, so shape alone is not enough to tell them apart. The lookbehind and
# lookahead stop a longer base32 run matching in the middle of itself.
SEED_SHAPE = re.compile(r"(?<![A-Z2-7])S[A-Z2-7]{55}(?![A-Z2-7])")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPO_SHAPE = re.compile(r"^[A-Za-z0-9_.-]{1,39}/[A-Za-z0-9_.-]{1,100}$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

STRKEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
VERSION_ACCOUNT = 6 << 3
VERSION_SEED = 18 << 3


class Strkey:
    """A decoded Stellar strkey: its version byte, and whether the checksum verifies."""

    def __init__(self, version: int | None, checksum_ok: bool) -> None:
        self.version = version
        self.checksum_ok = checksum_ok


def crc16_xmodem(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            step = crc << 1
            crc = (step ^ 0x1021) & 0xFFFF if crc & 0x8000 else step & 0xFFFF
    return crc


def decode_strkey(text: str) -> Strkey:
    """Decode a 56-character strkey far enough to read its version byte.

    The 56 characters hold a version byte, 32 bytes of key material and a CRC16-CCITT
    of the first 33 bytes, stored little-endian. A fabricated address fails the
    checksum, which is the difference between a typo and a real account.
    """
    if len(text) != 56:
        return Strkey(None, False)
    accumulator = 0
    width = 0
    raw = bytearray()
    for char in text:
        index = STRKEY_ALPHABET.find(char)
        if index < 0:
            return Strkey(None, False)
        accumulator = (accumulator << 5) | index
        width += 5
        while width >= 8:
            width -= 8
            raw.append((accumulator >> width) & 0xFF)
    if len(raw) != 35:
        return Strkey(None, False)
    body = bytes(raw[:33])
    checksum = bytes(raw[33:35])
    ok = crc16_xmodem(body) == int.from_bytes(checksum, "little")
    return Strkey(body[0], ok)


def seed_findings(text: str) -> list[str]:
    """One message per seed-shaped token, whether or not its checksum verifies.

    Both outcomes are a refusal. The difference is only what the operator is told to
    do next: a verifying checksum means a real seed is in the file and needs rotating,
    anything else means a lookalike worth a look.
    """
    found = []
    for match in SEED_SHAPE.finditer(text):
        token = match.group(0)
        head = f"{token[:4]}...{token[-4:]}"
        decoded = decode_strkey(token)
        if decoded.version == VERSION_SEED and decoded.checksum_ok:
            detail = "its checksum verifies, so treat it as a live seed and rotate it"
        else:
            detail = "its checksum does not verify, so it is likely a lookalike"
        found.append(
            f"{head} is seed-shaped; {detail}. This repository never reads, writes or "
            "prints a secret seed, so the run stops here"
        )
    return found


def check_endpoint(url: str, problems: list[str]) -> None:
    if not isinstance(url, str) or not url:
        problems.append("an endpoint entry is not a string")
        return
    scheme, _, rest = url.partition("://")
    if scheme != "https":
        problems.append(f"endpoint {url!r} is not https")
        return
    if not rest or "?" in url:
        problems.append(f"endpoint {url!r} has no host or carries a query string")


def check_policy(path: Path, problems: list[str]) -> None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        problems.append(f"config {path}: cannot read it ({exc.strerror})")
        return
    if len(raw) > MAX_CONFIG_BYTES:
        problems.append(f"config {path}: {len(raw)} bytes is over the {MAX_CONFIG_BYTES} limit")
        return
    text = raw.decode("utf-8", "replace")
    problems.extend(seed_findings(text))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        problems.append(f"config {path}: is not valid TOML ({exc})")
        return
    if not isinstance(data, dict):
        problems.append(f"config {path}: the top level is not a table")
        return

    if data.get("version") != 1:
        problems.append(f"config {path}: version must be 1, found {data.get('version')!r}")
    network = data.get("network")
    if not isinstance(network, str) or not network:
        problems.append(f"config {path}: network is required and has no default")
    elif network not in NETWORK_KEYWORDS and " ; " not in network:
        problems.append(
            f"config {path}: network {network!r} is neither mainnet, testnet nor a "
            "full network passphrase"
        )

    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        problems.append(f"config {path}: endpoints must be a non-empty array")
    else:
        for entry in endpoints:
            check_endpoint(entry, problems)

    accounts = data.get("account")
    if not isinstance(accounts, list) or not accounts:
        problems.append(f"config {path}: at least one [[account]] table is required")
        return
    for index, account in enumerate(accounts):
        if not isinstance(account, dict):
            problems.append(f"config {path}: account[{index}] is not a table")
            continue
        check_account(str(account.get("id") or ""), index, path, problems)


def check_account(account_id: str, index: int, path: Path, problems: list[str]) -> None:
    where = f"config {path}: account[{index}]"
    if not account_id:
        problems.append(f"{where} has no id")
        return
    if account_id[0] == "S":
        problems.append(f"{where} is a secret seed, which this project refuses on sight")
        return
    if account_id[0] == "M":
        problems.append(f"{where} {account_id} is a muxed M... address; Gauge reads G... accounts")
        return
    if account_id[0] == "C":
        problems.append(f"{where} {account_id} is a contract C... address, not an account")
        return
    decoded = decode_strkey(account_id)
    if decoded.version is None:
        problems.append(f"{where} {account_id} is not a 56-character base32 strkey")
    elif not decoded.checksum_ok:
        problems.append(
            f"{where} {account_id} is shaped like a strkey but its checksum does not verify"
        )
    elif decoded.version != VERSION_ACCOUNT:
        problems.append(
            f"{where} {account_id} decodes as strkey version {decoded.version >> 3}, not an account"
        )


def check_config_path(value: str, problems: list[str]) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute():
        problems.append(f"config {value!r} must be a path inside the repository, not absolute")
        return None
    if ".." in candidate.parts:
        problems.append(f"config {value!r} must not climb out of the repository with ..")
        return None
    if not candidate.exists():
        problems.append(f"config {value!r} does not exist in the workspace")
        return None
    if not candidate.is_file():
        problems.append(f"config {value!r} is not a regular file")
        return None
    return candidate


def split_config(value: str) -> list[str]:
    """The policy files the config input names, in the order given.

    One path is the common case and stays a plain string in a consumer's yaml. A list
    is separated by commas or newlines; both are accepted so the same input works
    inline and as a multi-line block scalar.
    """
    entries: list[str] = []
    for chunk in value.replace(",", "\n").splitlines():
        chunk = chunk.strip()
        if chunk:
            entries.append(chunk)
    return entries


def state_key(path: str) -> str:
    """A stable, marker-safe key for one policy file.

    The whole path without its suffix is used, so ``a/gauge.toml`` and ``b/gauge.toml``
    do not collide on ``gauge``. The key names the marker inside the issue body and the
    label suffix of that file's issue, so it may not contain anything outside
    ``[a-z0-9-]``.
    """
    stem = path.rsplit(".", 1)[0] if "." in path.rsplit("/", 1)[-1] else path
    key = KEY_UNSAFE.sub("-", stem.lower()).strip("-")
    return key or "config"


def check_text_input(name: str, value: str, problems: list[str]) -> None:
    if not value:
        problems.append(f"{name} must not be empty")
        return
    if len(value) > MAX_TEXT_INPUT:
        problems.append(f"{name} is {len(value)} characters, over the {MAX_TEXT_INPUT} limit")
    if CONTROL_CHARS.search(value) or "\n" in value:
        problems.append(f"{name} carries a control character or a line break")


def validate(args: argparse.Namespace) -> list[str]:
    problems: list[str] = []
    if not SHA40.match(args.gauge_ref):
        problems.append(
            f"gauge-ref {args.gauge_ref!r} is not a full 40-character lowercase commit sha; "
            "a branch or tag would let the commit built change without this file changing"
        )
    if not REPO_SHAPE.match(args.gauge_repo):
        problems.append(f"gauge-repo {args.gauge_repo!r} is not an owner/name pair")
    if args.fail_on not in ("high", "warn"):
        problems.append(f"fail-on {args.fail_on!r} must be high or warn")
    check_text_input("issue-label", args.issue_label, problems)
    check_text_input("title", args.title, problems)
    entries = split_config(args.config)
    if not entries:
        problems.append("config must name at least one policy file")
    if len(entries) > MAX_CONFIG_FILES:
        problems.append(f"config names {len(entries)} files, over the {MAX_CONFIG_FILES} limit")
    seen: set[str] = set()
    keys: dict[str, str] = {}
    for value in entries:
        if value in seen:
            problems.append(f"config {value!r} is listed more than once")
            continue
        seen.add(value)
        key = state_key(value)
        if key in keys:
            problems.append(f"config {value!r} shares the state key {key!r} with {keys[key]!r}")
        keys[key] = value
        config = check_config_path(value, problems)
        if config is not None:
            check_policy(config, problems)
    return problems


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="gauge.toml")
    parser.add_argument("--files-out", dest="files_out", default="")
    parser.add_argument("--gauge-repo", dest="gauge_repo", default="posture-sec/guage")
    parser.add_argument("--gauge-ref", dest="gauge_ref", default="")
    parser.add_argument("--fail-on", dest="fail_on", default="high")
    parser.add_argument("--issue-label", dest="issue_label", default="account-posture")
    parser.add_argument("--title", default="Account posture watch")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems = validate(args)
    if problems:
        print("validate_inputs: refused", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    entries = split_config(args.config)
    if args.files_out:
        payload = json.dumps(
            [{"path": value, "key": state_key(value)} for value in entries], separators=(",", ":")
        )
        with open(args.files_out, "a", encoding="utf-8") as handle:
            handle.write(f"files={payload}\n")
    print(
        f"validate_inputs: gauge-ref is pinned at {args.gauge_ref[:7]}, "
        f"{len(entries)} config file(s) parsed, fail-on {args.fail_on}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
