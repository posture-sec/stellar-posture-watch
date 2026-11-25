#!/usr/bin/env python3
"""Turn one Gauge JSON report into the body of the tracking issue.

The report is hostile input: every string in it was written by a chain read or by a
policy file, and Gauge's renderer controls characters but does not escape markdown
markup. A GitHub issue body is markdown, so this script escapes again and refuses to
let a chain-written value mention a user, a team or ``@all``.

Nothing here is printed to stdout except a one-line summary. The report body never
reaches the log.

Outputs are staged as temporaries in the destination directory and committed with
os.replace, with the body replaced first and the summary second so the summary is
the commit point.

Exit codes: 0 wrote the body, 2 refused the input.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

MARKER_PREFIX = "<!-- posture-watch:state v1 "
MARKER_SUFFIX = " -->"
MAX_STATE_ENTRIES = 200
MAX_MARKER_CHARS = 20_000
#: The issue body ceiling, matching the API limit `sync_issue.py` trims against.
BODY_LIMIT = 65_536
DROP_NOTICE = (
    "\n_{dropped} finding row(s) were left out of this body to stay under the "
    "{limit}-character issue limit; the state marker still carries the full open set._\n"
)
SEVERITIES = ("high", "warn")
SEVERITY_RANK = {"high": 0, "warn": 1}
SARIF_LEVEL = {"high": "error", "warn": "warning"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MARKDOWN_SPECIAL = re.compile(r"([\\*_\[\]<>#|~`&])")
MENTION = re.compile(r"(?<![\w/])@(\w{1,39})")
# Unicode format characters that must not reach the GitHub renderer unchanged.
# U+202A-U+202E: LRE, RLE, PDF, LRO, RLO (bidirectional formatting)
# U+2066-U+2069: LRI, RLI, FSI, PDI (bidirectional isolates)
# U+200B-U+200D: ZWSP, ZWNJ, ZWJ (zero-width joiners / separators)
# U+2060: WJ (word joiner); U+FEFF: BOM / ZWNBSP
_BIDI_STRIP = re.compile("[‪-‮⁦-⁩​-‍⁠﻿]")
LINE_BREAK = re.compile(r"[ \t]*\r?\n[ \t]*")
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

    Strips bidi and zero-width Unicode format characters that cause visual spoofing.
    Backslash escapes the characters that can open markup, and any mention is broken
    with a zero-width space entity so a hostile home domain cannot notify a user or
    ``@all``.  The mention rewrite emits ``&#8203;`` as an HTML entity; because that
    is ASCII it is unaffected by stripping the corresponding code point U+200B.
    """
    text = _BIDI_STRIP.sub("", str(value))
    text = MARKDOWN_SPECIAL.sub(r"\\\1", text)
    return MENTION.sub(lambda m: "@&#8203;" + m.group(1), text)


def fenced(value: object) -> str:
    """A value in backticks, with any run of backticks inside it neutralised."""
    text = MENTION.sub(lambda m: "@&#8203;" + m.group(1), str(value).replace("`", "&#96;"))
    return f"`{text}`"


def cell(value: object) -> str:
    """An escaped value for a table cell.

    ``escape`` covers markup but not line endings, and a newline inside a cell ends
    the row: the rest of the value renders as a row the report never contained, which
    a reader cannot tell from a real one. A break becomes the space it stood for.
    """
    return escape(LINE_BREAK.sub(" ", str(value)))


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
    accepted_keys: set[str] = set()
    for account in report["accounts"]:
        for entry in account.get("findings") or []:
            if isinstance(entry, dict) and entry.get("accepted") is True:
                accepted_keys.add(str(entry.get("fingerprint")))
    open_only: list[Finding] = []
    accepted: list[Finding] = []
    for finding in open_findings:
        (accepted if finding["fingerprint"] in accepted_keys else open_only).append(finding)
    return open_only, accepted


def encode_state(findings: list[Finding], budget: int = MAX_STATE_ENTRIES) -> tuple[str, int]:
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
        marker = f"{MARKER_PREFIX}{encoded}{MARKER_SUFFIX}"
        if len(marker) <= MAX_MARKER_CHARS or limit == 0:
            return encoded, len(ordered) - limit
        limit = max(limit - max(1, len(ordered) // 8), 0)


def _strip_fences(text: str) -> str:
    """Remove fenced code blocks from *text* before state decoding (issue #53).

    Both backtick (```) and tilde (~~~) fences of three or more characters are
    stripped.  An unterminated fence consumes from its opening marker to the end
    of the text, so a marker embedded in a code example cannot survive as state.
    """
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"^(`{3,}|~{3,})[^\n]*\n?", text, re.MULTILINE):
        if m.start() < pos:
            continue
        out.append(text[pos : m.start()])
        fence_char = m.group(1)[0]
        fence_len = len(m.group(1))
        # Match the closing fence: same character, same or greater length, at line start.
        close_re = r"^" + re.escape(fence_char * fence_len) + r"+[^\n]*$"
        close = re.search(close_re, text[m.end() :], re.MULTILINE)
        if close:
            pos = m.end() + close.end()
        else:
            # Unterminated fence: consume to end of text.
            return "".join(out)
    out.append(text[pos:])
    return "".join(out)


def decode_state(text: str) -> list[Finding] | None:
    """The findings recorded by a previous run, or None if the body carries no state."""
    all_matches = re.findall(
        re.escape(MARKER_PREFIX) + r"([A-Za-z0-9_-]*)" + re.escape(MARKER_SUFFIX), text
    )
    if not all_matches:
        return None
    last = all_matches[-1]
    padding = "=" * (-len(last) % 4)
    try:
        payload = base64.urlsafe_b64decode(last + padding)
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


def fit_body(body: str) -> tuple[str, int]:
    """Trim finding rows until the assembled body fits the issue ceiling.

    Rows are dropped in blocks from the end of the document, which is the Current
    findings table, and the notice names how many went. The counts line, the mode and
    exit line, the account table and the state marker are never touched: the marker is
    the last line and stays decodable, and it still carries the open set.
    """
    if len(body) <= BODY_LIMIT:
        return body, 0

    def row_indexes(lines: list[str]) -> list[int]:
        return [
            i
            for i, line in enumerate(lines)
            if line.startswith("| high |") or line.startswith("| warn |")
        ]

    lines = body.splitlines(keepends=True)
    rows = row_indexes(lines)
    dropped = 0
    while rows and len("".join(lines)) > BODY_LIMIT:
        block = max(1, len(rows) // 8)
        remove = set(rows[-block:])
        lines = [line for i, line in enumerate(lines) if i not in remove]
        dropped += len(remove)
        rows = row_indexes(lines)
    if dropped:
        for i, line in enumerate(lines):
            if line.startswith(MARKER_PREFIX):
                lines.insert(i, DROP_NOTICE.format(dropped=dropped, limit=BODY_LIMIT))
                break
    return "".join(lines), dropped


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
            f"| {cell(finding['message'])} |"
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
                f"| - | - | {cell(status)} |"
            )
            continue
        check_snapshot_scalars(snapshot, f"accounts[{account.get('id', '?')}]")
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
            f"| {cell(domain) if domain else '(none)'} | {cell(status)} |"
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


def check_snapshot_scalars(snapshot: dict, where: str) -> None:
    """Refuse a snapshot whose ledger or thresholds are not plain integers.

    A string ledger or threshold would add extra table cells and shift columns.
    ``isinstance(x, bool)`` is needed because ``bool`` is a subclass of ``int``.
    """
    ledger = snapshot.get("ledger")
    if not isinstance(ledger, int) or isinstance(ledger, bool):
        raise Refused(f"{where}: snapshot.ledger must be an integer, got {type(ledger).__name__!r}")
    thresholds = snapshot.get("thresholds") or {}
    for name in ("low", "medium", "high"):
        val = thresholds.get(name, 0)
        if not isinstance(val, int) or isinstance(val, bool):
            raise Refused(
                f"{where}: snapshot.thresholds.{name} must be an integer, "
                f"got {type(val).__name__!r}"
            )


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
    limits = report.get("limits")
    if not isinstance(limits, str):
        raise Refused("the report carries a non-string limits field")

    all_findings = collect_findings(report, Path(args.report))
    open_findings, accepted = split_accepted(report, all_findings)
    _seen_fps: dict[str, str] = {}
    _acc_index = {str(_snapshot(a).get("id")): i for i, a in enumerate(report["accounts"])}
    for _f in open_findings:
        _fp = _f["fingerprint"]
        if _fp in _seen_fps:
            _i0 = _acc_index.get(_seen_fps[_fp], "?")
            _i1 = _acc_index.get(_f["account"], "?")
            raise Refused(f"fingerprint {_fp} appears in both accounts[{_i0}] and accounts[{_i1}]")
        _seen_fps[_fp] = _f["account"]
    current = {f["fingerprint"]: f for f in open_findings}

    previous: list[Finding] | None = None
    if args.previous_body:
        prev_path = Path(args.previous_body)
        if prev_path.exists():
            try:
                raw_body = prev_path.read_text(encoding="utf-8", errors="replace")
                previous = decode_state(_strip_fences(raw_body))
            except OSError as exc:
                raise Refused(
                    f"previous body {prev_path}: cannot read it ({exc.strerror})"
                ) from None

    if previous is None:
        new, resolved, changed, baseline = list(current.values()), [], True, True
    else:
        before = {f["fingerprint"]: f for f in previous}
        new = [current[fp] for fp in sorted(set(current) - set(before))]
        resolved = [before[fp] for fp in sorted(set(before) - set(current))]
        changed = bool(new or resolved)
        baseline = False

    payload, omitted = encode_state(list(current.values()), args.max_state_entries)

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
    parts.append(f"\n{MARKER_PREFIX}{payload}{MARKER_SUFFIX}\n")
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
    body, dropped = fit_body("".join(parts))
    if dropped:
        summary["dropped"] = dropped
    return body, summary


def render_sarif(
    report: dict,
    gauge_ref: str,
    gauge_repo: str,
    config: str,
) -> dict[str, object]:
    """SARIF 2.1.0 representation of the open findings in a Gauge report.

    Severity mapping: high → error, warn → warning, per docs/SARIF_MAPPING.md.
    Skipped/missing accounts produce no results; the state is in the Accounts table.
    """
    path = Path(config)
    all_findings = collect_findings(report, path)
    open_findings, _ = split_accepted(report, all_findings)

    rules: dict[str, dict[str, object]] = {}
    for finding in open_findings:
        rule_id = finding["rule"]
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": rule_id},
            }

    results: list[dict[str, object]] = []
    for finding in open_findings:
        results.append(
            {
                "ruleId": finding["rule"],
                "level": SARIF_LEVEL.get(finding["severity"], "note"),
                "message": {"text": finding["message"] or finding["rule"]},
                "locations": [
                    {"logicalLocations": [{"name": finding["account"], "kind": "account"}]}
                ],
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "stellar-gauge",
                        "version": str(report.get("tool_version", "")),
                        "informationUri": f"https://github.com/{gauge_repo}",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--previous-body", dest="previous_body", default="")
    parser.add_argument("--as-of", dest="as_of", required=True)
    parser.add_argument("--config", required=True)
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
    parser.add_argument(
        "--sarif-out",
        dest="sarif_out",
        default="",
        help="write a SARIF 2.1.0 file to this path (skipped when empty)",
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
    if args.max_state_entries < 0:
        print("render_report: --max-state-entries must be 0 or above", file=sys.stderr)
        return 2
    try:
        body, summary = render(args)
    except Refused as exc:
        print(f"render_report: refused: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    summary_path = Path(args.summary_out) if args.summary_out else None
    counts_text = (
        f"{summary['open']} open, {summary['high']} high, {summary['warn']} warn, "
        f"{summary['accepted']} accepted"
    )
    if not summary["changed"]:
        counts_text = f"{NO_CHANGE_SUMMARY} ({counts_text})"
    tmp_out: Path | None = None
    tmp_summary: Path | None = None
    created: list[Path] = []
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        if str(out).startswith("/dev/") or (
            out.exists() and (out.is_char_device() or out.is_fifo())
        ):
            out.write_text(body, encoding="utf-8")
        else:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=out.parent, encoding="utf-8", delete=False
            ) as f_body:
                tmp_out = Path(f_body.name)
                f_body.write(body)
                f_body.flush()
                os.fsync(f_body.fileno())

        if summary_path:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            if str(summary_path).startswith("/dev/") or (
                summary_path.exists() and (summary_path.is_char_device() or summary_path.is_fifo())
            ):
                summary_path.write_text(
                    json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
                )
            else:
                with tempfile.NamedTemporaryFile(
                    mode="w", dir=summary_path.parent, encoding="utf-8", delete=False
                ) as f_sum:
                    tmp_summary = Path(f_sum.name)
                    f_sum.write(json.dumps(summary, sort_keys=True) + "\n")
                    f_sum.flush()
                    os.fsync(f_sum.fileno())

        if tmp_out:
            out_was_new = not out.exists()
            os.replace(tmp_out, out)
            tmp_out = None
            if out_was_new:
                created.append(out)
        if summary_path and tmp_summary:
            summary_was_new = not summary_path.exists()
            os.replace(tmp_summary, summary_path)
            tmp_summary = None
            if summary_was_new:
                created.append(summary_path)
    except OSError as exc:
        if tmp_out and tmp_out.exists():
            with contextlib.suppress(OSError):
                tmp_out.unlink()
        if tmp_summary and tmp_summary.exists():
            with contextlib.suppress(OSError):
                tmp_summary.unlink()
        for p in created:
            with contextlib.suppress(OSError):
                p.unlink(missing_ok=True)
        print(f"render_report: cannot write {out}: {exc.strerror}", file=sys.stderr)
        return 2
    if args.sarif_out:
        sarif_path = Path(args.sarif_out)
        try:
            report_data = read_report(Path(args.report))
            sarif = render_sarif(report_data, args.gauge_ref, args.gauge_repo, args.config)
            sarif_path.parent.mkdir(parents=True, exist_ok=True)
            sarif_path.write_text(json.dumps(sarif, indent=2) + "\n", encoding="utf-8")
            result_count = len(sarif["runs"][0]["results"])  # type: ignore[index]
            print(f"render_report: wrote SARIF {sarif_path} ({result_count} results)")
        except (Refused, OSError) as exc:
            print(f"render_report: cannot write SARIF: {exc}", file=sys.stderr)
            return 2

    dropped = summary.get("dropped", 0)
    if dropped:
        print(f"render_report: dropped {dropped} finding row(s) to fit the body limit")
    print(f"render_report: wrote {out} ({len(body)} characters); {counts_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
