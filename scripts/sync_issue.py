#!/usr/bin/env python3
"""Create or update the one tracking issue this Action maintains.

Talks to the GitHub REST API with nothing but the standard library: HTTPS only, no
redirects, a timeout on every call, bounded retries that honour ``Retry-After``, and a
token read from the environment because a token in an argument would show up in the
runner's process list and in the step log.

Exit codes: 0 done, 2 bad input, 3 the API could not be reached or answered wrongly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BODY_LIMIT = 65_536
MARKER_PREFIX = "<!-- posture-watch:state v1 "
DEFAULT_API = "https://api.github.com"
PATH_SEGMENT = re.compile(r"[A-Za-z0-9._-]{1,100}")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 60.0
ACCEPT = "application/vnd.github+json"
CURRENT_HEADER = "## Current findings"
TRUNCATION_ROW = "| ... | ... | ... | ... | {remaining} more finding(s) truncated here |"


class BadInput(Exception):
    """An argument this script will not act on."""


class ApiError(Exception):
    """A response this script will not act on."""


class RedirectRefused(urllib.request.HTTPRedirectHandler):
    """Stop at any redirect instead of following the token to an unlisted host.

    Subclassing the default handler is what does it: `build_opener` drops its own
    `HTTPRedirectHandler` when a passed handler already covers that role, and raising
    from `redirect_request` means no 30x is ever followed.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def build_opener() -> urllib.request.OpenerDirector:
    opener = urllib.request.build_opener(RedirectRefused())
    opener.addheaders = []
    return opener


OPENER = build_opener()


def transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    """One HTTPS exchange, with no retry logic in it.

    This is the seam the tests drive: `tests/test_sync_issue.py` swaps it for a stub so
    the retry policy and the write decisions can be asserted without a socket, and calls
    the real one against a loopback server when it wants to check what goes on the wire.
    The https-only rule in `api_base` applies to both paths alike.
    """
    request_object = urllib.request.Request(url, data=body, headers=headers, method=method)
    with OPENER.open(request_object, timeout=30) as response:
        return response.status, response.read()


TRANSPORT = transport


def api_base() -> str:
    base = os.environ.get("GITHUB_API_URL") or DEFAULT_API
    base = base.rstrip("/")
    if not base.startswith("https://"):
        raise ApiError(f"GITHUB_API_URL {base!r} is not https")
    if "://" not in base or not re.match(
        r"^[a-zA-Z0-9.-]+(?::\d+)?(/api/v3)?$", base.split("://", 1)[1]
    ):
        raise ApiError(f"GITHUB_API_URL {base!r} is not a bare scheme and host")
    return base


def retryable(exc: urllib.error.HTTPError) -> bool:
    """True unless the response says to wait longer than this script is allowed to."""
    header = exc.headers.get("Retry-After") if exc.headers else None
    if not header:
        return True
    match = re.fullmatch(r"\s*(\d+)\s*", header)
    if match is None:
        # A Retry-After this script cannot read as a number of seconds, which an HTTP date
        # is, is not a reason to keep sending a token at the same host.
        return False
    return float(match.group(1)) <= MAX_RETRY_WAIT


def request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, bytes]:
    """One call, with bounded retries. Returns the status and the response body."""
    body = json.dumps(payload).encode() if payload is not None else None
    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": ACCEPT,
            "User-Agent": "posture-sec-stellar-posture-watch",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            return TRANSPORT(method, url, headers, body)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:200].decode("utf-8", "replace")
            if (
                (exc.code == 429 and retryable(exc))
                or (
                    exc.code == 403
                    and exc.headers
                    and "Retry-After" in exc.headers
                    and retryable(exc)
                )
                or exc.code >= 500
            ):
                last = exc
            else:
                raise ApiError(f"{method} {url} -> {exc.code}: {redact(detail)}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        if attempt < MAX_ATTEMPTS:
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_WAIT)
    reason = redact(str(last)) if last is not None else "no attempt succeeded"
    raise ApiError(f"{method} {url} failed after {MAX_ATTEMPTS} attempts: {reason}")


def redact(text: str) -> str:
    return re.sub(
        r"(Bearer |token=|[a-z0-9_]+=)[A-Za-z0-9._-]+|"
        r"(gh[pousr]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{82,}|[A-Za-z0-9._-]{40,})",
        r"\1[redacted]",
        text,
    )[:200]


def get_json(method_target: str, token: str, url: str, payload: dict | None = None) -> object:
    status, body = request(method_target, url, token, payload)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise ApiError(
            f"{method_target} {url} -> {status} returned a body that is not JSON"
        ) from None


def emit(name: str, value: str) -> None:
    """Publish a step output, or print it when running outside Actions."""
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"posture-watch: {name}={value}")


def find_issue(
    owner: str, repo: str, label: str, title: str, token: str, previous_out: Path
) -> int | None:
    """The open issue carrying our state marker, or one with our title to adopt."""
    base = api_base()
    adopt: int | None = None
    for page in range(1, 6):
        url = (
            f"{base}/repos/{owner}/{repo}/issues?state=open"
            f"&labels={urllib.parse.quote(label)}&per_page=100&page={page}"
        )
        batch = get_json("GET", token, url)
        if not isinstance(batch, list):
            raise ApiError(f"the issue list on page {page} is not an array")
        if not batch:
            break
        for entry in batch:
            if not isinstance(entry, dict) or "pull_request" in entry:
                continue
            number = entry.get("number")
            body = entry.get("body")
            if not isinstance(number, int):
                continue
            text = body if isinstance(body, str) else ""
            if MARKER_PREFIX in text:
                previous_out.write_text(text, encoding="utf-8")
                return number
            if entry.get("title") == title and adopt is None:
                adopt = number
    return adopt


def fit_body(body: str) -> tuple[str, int]:
    """Keep the body under the API limit by trimming the Current findings table."""
    if len(body) <= BODY_LIMIT:
        return body, 0
    start = body.find(CURRENT_HEADER)
    if start < 0:
        return body, -1
    block_start = body.find("\n|", start)
    end = body.find("\n##", start)
    if block_start < 0 or end < 0:
        return body, -1
    lines = body[block_start + 1 : end].splitlines()
    header = lines[:2]
    rows = lines[2:]
    kept = len(rows)
    while kept > 0:
        trimmed = rows[:kept]
        if kept < len(rows):
            trimmed = [*trimmed, TRUNCATION_ROW.format(remaining=len(rows) - kept)]
        candidate = body[: block_start + 1] + "\n".join(header + trimmed) + body[end:]
        if len(candidate) <= BODY_LIMIT:
            return candidate, len(rows) - kept
        kept -= max(1, kept // 8)
    return body[: block_start + 1] + "\n".join(header) + body[end:], len(rows)


def read_summary(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(f"summary {path}: cannot read it ({exc})") from None
    if not isinstance(data, dict):
        raise ApiError(f"summary {path}: is not an object")
    for key in ("changed", "new", "resolved", "open", "as_of"):
        if key not in data:
            raise ApiError(f"summary {path}: is missing {key!r}")
    return data


def comment_body(summary: dict) -> str:
    noun = "finding" if summary["new"] == 1 else "findings"
    return (
        f"Posture changed as of {summary['as_of']}: {summary['new']} new {noun} and "
        f"{summary['resolved']} resolved. The issue body now shows the current list."
    )


def run_find(args: argparse.Namespace, token: str) -> int:
    number = find_issue(
        args.owner, args.repo, args.label, args.title, token, Path(args.previous_body_out)
    )
    emit("found", "true" if number is not None else "false")
    emit("issue-number", str(number) if number is not None else "")
    print(
        f"sync_issue: {'found' if number is not None else 'no'} issue to update"
        + (f" (#{number})" if number else "")
    )
    return 0


def run_write(args: argparse.Namespace, token: str) -> int:
    summary = read_summary(Path(args.summary))
    body = Path(args.body).read_text(encoding="utf-8")
    body, truncated = fit_body(body)
    if truncated < 0:
        raise ApiError(
            f"the rendered body is {len(body)} characters and cannot be trimmed under "
            f"{BODY_LIMIT}; shrink the policy or raise the limit deliberately"
        )
    if truncated:
        print(f"sync_issue: truncated {truncated} finding row(s) to fit the body limit")
    base = api_base()
    changed = bool(summary["changed"])
    emit("changed", "true" if changed else "false")

    if args.number is None:
        if args.dry_run:
            print(f"sync_issue: dry run, would open an issue titled {args.title!r}")
            emit("issue-number", "")
            return 0
        created = get_json(
            "POST",
            token,
            f"{base}/repos/{args.owner}/{args.repo}/issues",
            {"title": args.title, "body": body, "labels": [args.label]},
        )
        number = created.get("number") if isinstance(created, dict) else None
        if not isinstance(number, int):
            raise ApiError("the created issue carries no number")
        emit("issue-number", str(number))
        print(f"sync_issue: opened issue #{number} as the baseline")
        return 0

    if args.number is not None and not changed and not args.update_on_no_change:
        emit("issue-number", str(args.number))
        print(f"sync_issue: issue #{args.number} needs no change, left alone")
        return 0

    if args.dry_run:
        print(f"sync_issue: dry run, would update issue #{args.number}")
        emit("issue-number", str(args.number))
        return 0

    request(
        "PATCH",
        f"{base}/repos/{args.owner}/{args.repo}/issues/{args.number}",
        token,
        {"body": body},
    )
    emit("issue-number", str(args.number))
    if changed:
        request(
            "POST",
            f"{base}/repos/{args.owner}/{args.repo}/issues/{args.number}/comments",
            token,
            {"body": comment_body(summary)},
        )
        print(f"sync_issue: updated issue #{args.number} and commented the change")
    else:
        print(f"sync_issue: updated issue #{args.number} without a comment")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("find", "write"))
    parser.add_argument("--owner", default="", help="defaults to the owner of GITHUB_REPOSITORY")
    parser.add_argument("--repo", default="", help="defaults to the name in GITHUB_REPOSITORY")
    parser.add_argument("--label", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--previous-body-out", dest="previous_body_out", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--number", type=int, default=None)
    parser.add_argument("--update-on-no-change", dest="update_on_no_change", action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    return parser.parse_args(argv)


def default_repository(args: argparse.Namespace) -> None:
    """Fill owner and repo from GITHUB_REPOSITORY when the caller left them out.

    The runner already exports that variable for every event, including schedule, while
    github.event.repository is missing from a few of them. Reading it here keeps the
    workflow file from interpolating a repository name into a shell command.
    """
    if args.owner and args.repo:
        return
    full = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in full:
        raise BadInput(
            "owner and repo were not given and GITHUB_REPOSITORY is empty or has no slash"
        )
    owner, _, name = full.partition("/")
    args.owner = args.owner or owner
    args.repo = args.repo or name


def check_path_segments(args: argparse.Namespace) -> None:
    """Owner, repo and label go into a URL path, so they get checked before the call.

    A label with a slash or a query marker would move the request somewhere else in
    the API, and a token would be sent there with it.
    """
    for name, value in (("owner", args.owner), ("repo", args.repo), ("label", args.label)):
        if not value or not PATH_SEGMENT.fullmatch(value):
            raise BadInput(
                f"{name} {value!r} must be 1 to 100 characters of letters, digits, dot, "
                "dash or underscore: it goes into a URL path"
            )
    if not args.title or len(args.title) > 256 or CONTROL_CHARS.search(args.title):
        raise BadInput("title must be 1 to 256 characters with no control characters")
    if args.number is not None and args.number < 1:
        raise BadInput(f"--number must be positive, got {args.number}")
    if args.action == "find" and not args.previous_body_out:
        raise BadInput("find needs --previous-body-out, where the current body is handed over")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token = os.environ.get("POSTURE_WATCH_TOKEN", "")
    if not token:
        print(
            "sync_issue: POSTURE_WATCH_TOKEN is empty; pass github.token to the step's env",
            file=sys.stderr,
        )
        return 2
    try:
        default_repository(args)
        check_path_segments(args)
    except BadInput as exc:
        print(f"sync_issue: refused: {exc}", file=sys.stderr)
        return 2
    try:
        if args.action == "find":
            return run_find(args, token)
        if not args.body or not args.summary:
            raise ApiError("write needs --body and --summary")
        Path(args.body).read_text(encoding="utf-8")
        return run_write(args, token)
    except ApiError as exc:
        print(f"sync_issue: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"sync_issue: {exc.strerror or exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
