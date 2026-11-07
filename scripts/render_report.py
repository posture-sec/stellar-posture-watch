#!/usr/bin/env python3
"""Turn one Gauge JSON report into the body of the tracking issue.

The report is hostile input: every string in it was written by a chain read or by a
policy file, and Gauge's renderer controls characters but does not escape markdown
markup. A GitHub issue body is markdown, so this script escapes again and refuses to
let a chain-written value mention a user, a team or ``@all``.

Nothing here is printed to stdout except a one-line summary. The report body never
reaches the log.

Exit codes: 0 wrote the body, 2 refused the input.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import TypedDict

MARKER_PREFIX = "<!-- posture-watch:state v1 "
MARKER_SUFFIX = " -->"
MAX_STATE_ENTRIES = 200
MAX_MARKER_CHARS = 20_000
SEVERITIES = ("high", "warn")
SEVERITY_RANK = {"high": 0, "warn": 1}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MARKDOWN_SPECIAL = re.compile(r"([\\*_\[\]<>#|~`&])")
MENTION = re.compile(r"(?<![\w/])@(\w{1,39})")
NO_CHANGE_SUMMARY = "no change since the previous run"


class Finding(TypedDict):
    """One entry of the state marker, with the fields a change list needs."""

    account: str
    fingerprint: str
    message: str
    rule: str
    severity: str


class Refused(Exception):
    """Input this script will not render. Exit 2, never a partial body."""


def escape(value: object) -> str:
    """Make a report-derived string safe to drop into issue markdown.

    Backslash escapes the characters that can open markup, and any mention is broken
    with a zero-width space so a hostile home domain cannot notify a user or ``@all``.
    """
    text = MARKDOWN_SPECIAL.sub(r"\\\1", str(value))
    return MENTION.sub(lambda m: "@&#8203;" + m.group(1), text)


def fenced(value: object) -> str:
    """A value in backticks, with any run of backticks inside it neutralised."""
    text = str(value).replace("`", "&#96;")
    return f"`{text}`"


def read_report(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Refused(f"report {path}: cannot read it ({exc.strerror})") from None
    if not raw:
        raise Refused(f"report {path}: is empty")
    if len(raw) > 8 * 1024 * 1024:
        raise Refused(f"report {path}: {len(raw)} bytes is over the 8 MiB limit")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Refused(f"report {path}: is not valid JSON at line {exc.lineno}") from None
    if not isinstance(data, dict):
        raise Refused(f"report {path}: the top level is not an object")
    for key in ("tool_version", "network", "ledger", "accounts", "exit_code", "limits"):
        if key not in data:
            raise Refused(f"report {path}: is missing the {key!r} field")
    if not isinstance(data["accounts"], list):
        raise Refused(f"report {path}: accounts is not an array")
    return data


def collect_findings(report: dict, path: Path) -> list[Finding]:
    """Every finding in the report, open and accepted, with hostile fields checked."""
    collected: list[Finding] = []
    for index, account in enumerate(report["accounts"]):
        where = f"{path}: accounts[{index}]"
        if not isinstance(account, dict):
            raise Refused(f"{where} is not an object")
        snapshot = account.get("snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("id"), str):
            raise Refused(f"{where} has no snapshot.id")
        for entry in account.get("findings") or []:
            if not isinstance(entry, dict):
                raise Refused(f"{where} has a finding that is not an object")
            severity = entry.get("severity")
            if severity not in SEVERITIES:
                raise Refused(f"{where} has a finding with unknown severity {severity!r}")
            fingerprint = entry.get("fingerprint")
            if not isinstance(fingerprint, str) or not HEX64.match(fingerprint):
                raise Refused(
                    f"{where} has a finding without a 64-character fingerprint, "
                    "so it cannot be tracked between runs"
                )
            rule = entry.get("rule_id")
            if not isinstance(rule, str) or not rule:
                raise Refused(f"{where} has a finding with no rule_id")
            collected.append(
                {
                    "account": str(snapshot["id"]),
                    "fingerprint": fingerprint,
                    "message": str(entry.get("message") or ""),
                    "rule": rule,
                    "severity": severity,
                }
            )
    return collected


def split_accepted(
    report: dict, open_findings: list[Finding]
) -> tuple[list[Finding], list[Finding]]:
    """Findings the policy accepted, kept out of the change list on purpose."""
    accepted_keys: set[tuple[str, str]] = set()
    for account in report["accounts"]:
        for entry in account.get("findings") or []:
            if isinstance(entry, dict) and entry.get("accepted") is True:
                accepted_keys.add((str(entry.get("rule_id")), str(entry.get("fingerprint"))))
    open_only: list[Finding] = []
    accepted: list[Finding] = []
    for finding in open_findings:
        key = (finding["rule"], finding["fingerprint"])
        (accepted if key in accepted_keys else open_only).append(finding)
    return open_only, accepted


def marker_open(key: str) -> str:
    """The marker's opener, carrying the policy file's key when there is one.

    A body can describe more than one policy file, so the marker has to say which file
    its entries belong to. The key is separated with ``#``, which base64url never
    produces, so a keyed marker cannot be mistaken for an unkeyed payload.
    """
    return MARKER_PREFIX if not key else f"{MARKER_PREFIX}{key}#"


def encode_state(
    findings: list[Finding], budget: int = MAX_STATE_ENTRIES, key: str = ""
) -> tuple[str, int]:
    """The marker payload and the number of findings left out of it.

    The payload is base64url of a compact JSON array: an HTML comment cannot hold a
    ``--`` and a report can produce one inside a message. Entries are packed in
    fingerprint order until either the count or the character budget runs out, and
    whatever falls out is counted and said out loud in the body.
    """
    ordered = sorted(findings, key=lambda f: f["fingerprint"])
    limit = min(len(ordered), budget)
    while True:
        payload = json.dumps(ordered[:limit], separators=(",", ":"), sort_keys=True)
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        marker = f"{marker_open(key)}{encoded}{MARKER_SUFFIX}"
        if len(marker) <= MAX_MARKER_CHARS or limit == 0:
            return encoded, len(ordered) - limit
        limit = max(limit - max(1, len(ordered) // 8), 0)


def decode_state(text: str, key: str = "") -> list[Finding] | None:
    """The findings recorded by a previous run, or None if the body carries no state.

    With a key, only that file's marker is read; without one, only an unkeyed marker is.
    """
    match = re.search(
        re.escape(marker_open(key)) + r"([A-Za-z0-9_-]*)" + re.escape(MARKER_SUFFIX), text
    )
    if not match:
        return None
    padding = "=" * (-len(match.group(1)) % 4)
    try:
        payload = base64.urlsafe_b64decode(match.group(1) + padding)
        entries = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(entries, list):
        return None
    findings: list[Finding] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        if not all(
            isinstance(entry.get(key), str)
            for key in ("account", "fingerprint", "rule", "severity")
        ):
            return None
        findings.append(
            {
                "account": entry["account"],
                "fingerprint": entry["fingerprint"],
                "message": entry.get("message", ""),
                "rule": entry["rule"],
                "severity": entry["severity"],
            }
        )
    return findings


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (SEVERITY_RANK[f["severity"]], f["rule"], f["account"], f["fingerprint"]),
    )


def finding_rows(findings: list[Finding]) -> str:
    if not findings:
        return "None.\n"
    lines = [
        "| Severity | Rule | Account | Fingerprint | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for finding in sort_findings(findings):
        lines.append(
            f"| {escape(finding['severity'])} | {fenced(finding['rule'])} "
            f"| {fenced(finding['account'])} | {fenced(finding['fingerprint'][:12])} "
            f"| {escape(finding['message'])} |"
        )
    return "\n".join(lines) + "\n"


def account_rows(report: dict) -> str:
    if not report["accounts"]:
        return "The report lists no accounts.\n"
    lines = [
        "| Account | Ledger | Low/med/high | Signers | Balances | Flags set | Home domain | Read |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for account in sorted(report["accounts"], key=lambda a: str(_snapshot(a).get("id"))):
        snapshot = _snapshot(account)
        status = account_status(account)
        if status != "read":
            # A zero ledger and zero thresholds are what Gauge emits for an account it
            # never read. Printing them as numbers would present an absent account as a
            # configured one, so the row says "(not read)" and leaves the cells out.
            lines.append(
                f"| {fenced(snapshot.get('id'))} | (not read) | - | - | - "
                f"| - | - | {escape(status)} |"
            )
            continue
        thresholds = snapshot.get("thresholds") or {}
        flags = snapshot.get("flags") or {}
        set_flags = (
            ", ".join(fenced(name) for name, on in sorted(flags.items()) if on is True) or "none"
        )
        signers = snapshot.get("signers") or []
        balances = snapshot.get("balances") or []
        domain = snapshot.get("home_domain")
        lines.append(
            f"| {fenced(snapshot.get('id'))} | {snapshot.get('ledger')} "
            f"| {thresholds.get('low', 0)}/{thresholds.get('medium', 0)}"
            f"/{thresholds.get('high', 0)} "
            f"| {len(signers)} | {len(balances)} | {set_flags} "
            f"| {escape(domain) if domain else '(none)'} | {escape(status)} |"
        )
    return "\n".join(lines) + "\n"


def _snapshot(account: dict) -> dict:
    snapshot = account.get("snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def account_status(account: dict) -> str:
    if account.get("missing") is True:
        return "not found on this endpoint"
    skipped = account.get("skipped")
    if isinstance(skipped, str) and skipped:
        return f"not read: {skipped}"
    return "read"


def status_line(
    counts: dict[str, int], read: int, asked: int, baseline: bool, changed: bool
) -> str:
    noun = "finding" if counts["open"] == 1 else "findings"
    if counts["open"] == 0:
        posture = (
            f"No findings open among {counts['accepted']} accepted in the policy"
            if counts["accepted"]
            else "No findings open"
        )
    else:
        posture = f"{counts['open']} {noun} open ({counts['high']} high, {counts['warn']} warn)"
        if counts["accepted"]:
            posture += f", {counts['accepted']} accepted in the policy"
    # 3.6: an account the endpoint did not have is not an account that was read. The table
    # below already marks the row "(not read)"; the sentence has to agree with it.
    tail = f" across {read} account{'s' if read != 1 else ''} read"
    if asked != read:
        tail += f" of {asked} asked about"
    if baseline:
        return f"This run establishes the baseline: {posture}{tail}.\n"
    if changed:
        return f"Posture changed since the previous run: {posture}{tail}.\n"
    return f"{posture}{tail}, unchanged since the previous run.\n"


def render(args: argparse.Namespace) -> tuple[str, dict[str, object]]:
    """The issue body, whether anything changed, and the counts behind the summary."""
    report = read_report(Path(args.report))
    reported_exit = report.get("exit_code")
    if reported_exit != args.exit_code:
        raise Refused(
            f"the report carries exit code {reported_exit!r} and the run reported {args.exit_code}"
        )
    tool_version = report.get("tool_version")
    if not isinstance(tool_version, str) or not tool_version:
        raise Refused("the report carries no tool_version")

    all_findings = collect_findings(report, Path(args.report))
    open_findings, accepted = split_accepted(report, all_findings)
    current = {f["fingerprint"]: f for f in open_findings}

    previous: list[Finding] | None = None
    if args.previous_body and Path(args.previous_body).exists():
        previous = decode_state(
            Path(args.previous_body).read_text(encoding="utf-8", errors="replace"),
            args.state_key,
        )

    if previous is None:
        new, resolved, changed, baseline = list(current.values()), [], True, True
    else:
        before = {f["fingerprint"]: f for f in previous}
        new = [current[fp] for fp in sorted(set(current) - set(before))]
        resolved = [before[fp] for fp in sorted(set(before) - set(current))]
        changed = bool(new or resolved)
        baseline = False

    payload, omitted = encode_state(list(current.values()), args.max_state_entries, args.state_key)

    counts = {
        "open": len(current),
        "high": sum(1 for f in current.values() if f["severity"] == "high"),
        "warn": sum(1 for f in current.values() if f["severity"] == "warn"),
        "accepted": len(accepted),
    }

    parts: list[str] = []
    asked = len(report["accounts"])
    read = sum(1 for account in report["accounts"] if account_status(account) == "read")
    parts.append(
        status_line(counts, read, asked, baseline, changed)
        + f"\nAs of {args.as_of}, read at ledger {report['ledger']} on {escape(report['network'])} "
        f"with `{escape(tool_version)}`, built from {fenced(args.gauge_repo)} at "
        f"{fenced(args.gauge_ref[:7])}, auditing {fenced(args.config)} "
        f"with --fail-on {args.fail_on}.\n"
    )
    if omitted:
        parts.append(
            f"\n**Change detection is partial.** The state marker carries {len(current) - omitted} "
            f"of {len(current)} open findings; {omitted} were left out of it, so a run that only "
            "moves those findings will report none change.\n"
        )
    parts.append(f"\n## New since the previous run\n\n{finding_rows(new)}")
    parts.append(f"\n## Resolved since the previous run\n\n{finding_rows(resolved)}")
    parts.append(f"\n## Current findings\n\n{finding_rows(list(current.values()))}")
    if accepted:
        parts.append(
            "\n## Accepted in the policy\n\nThese are recorded as accepted with a reason in "
            "the policy file, so they do not count as open and do not reappear in the lists "
            f"above.\n\n{finding_rows(accepted)}"
        )
    # 3.7: the heading takes the summary's word for the whole set. "## Accounts read" titled a
    # table whose own Read column says "(not read)", the same claim 3.6 removed from the sentence.
    parts.append(f"\n## Accounts asked about\n\n{account_rows(report)}")
    parts.append(f"\n## What this cannot see\n\n> {escape(report['limits'])}\n")
    parts.append(
        "\n---\n\n"
        "Maintained by `posture-sec/stellar-posture-watch`. The header date is the run that last "
        "changed this list; a run that finds the same posture leaves the body alone, so check the "
        "workflow run history for the most recent read. Findings are posture, not safety: a clean "
        "list here means the rules this version of Gauge runs agreed with the policy at one "
        "ledger, nothing more.\n"
    )
    parts.append(f"\n{marker_open(args.state_key)}{payload}{MARKER_SUFFIX}\n")
    summary: dict[str, object] = {
        "changed": changed,
        "new": len(new),
        "resolved": len(resolved),
        "open": counts["open"],
        "high": counts["high"],
        "warn": counts["warn"],
        "accepted": counts["accepted"],
        "omitted": omitted,
        "as_of": args.as_of,
    }
    return "".join(parts), summary


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--previous-body", dest="previous_body", default="")
    parser.add_argument("--as-of", dest="as_of", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--state-key", dest="state_key", default="")
    parser.add_argument("--gauge-repo", dest="gauge_repo", default="posture-sec/guage")
    parser.add_argument("--gauge-ref", dest="gauge_ref", required=True)
    parser.add_argument("--fail-on", dest="fail_on", default="high", choices=("high", "warn"))
    parser.add_argument("--exit-code", dest="exit_code", type=int, required=True)
    parser.add_argument(
        "--max-state-entries",
        dest="max_state_entries",
        type=int,
        default=MAX_STATE_ENTRIES,
        help="how many findings the state marker may carry; the body says so when it drops any",
    )
    parser.add_argument(
        "--summary-out",
        dest="summary_out",
        default="",
        help="write the counts as JSON for sync_issue.py",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        date = dt.date.fromisoformat(args.as_of)
    except ValueError:
        print(f"render_report: --as-of {args.as_of!r} is not a YYYY-MM-DD date", file=sys.stderr)
        return 2
    if date.isoformat() != args.as_of:
        print(f"render_report: --as-of {args.as_of!r} is not a canonical ISO date", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[0-9a-f]{40}", args.gauge_ref):
        print("render_report: --gauge-ref must be a full 40-character commit sha", file=sys.stderr)
        return 2
    try:
        body, summary = render(args)
    except Refused as exc:
        print(f"render_report: refused: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    counts_text = (
        f"{summary['open']} open, {summary['high']} high, {summary['warn']} warn, "
        f"{summary['accepted']} accepted"
    )
    if not summary["changed"]:
        counts_text = f"{NO_CHANGE_SUMMARY} ({counts_text})"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        if args.summary_out:
            Path(args.summary_out).write_text(
                json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
            )
    except OSError as exc:
        print(f"render_report: cannot write {out}: {exc.strerror}", file=sys.stderr)
        return 2
    print(f"render_report: wrote {out} ({len(body)} characters); {counts_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
