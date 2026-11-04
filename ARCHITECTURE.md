# Architecture

How the four pieces fit, which strings are load bearing, and what happens when a run goes
wrong. `README.md` says what this action does for its operator; this file says how it is put
together so a contributor can change one part without guessing what the other three assume.

## 1. Shape

```
caller's workflow (schedule)
  |
  v
action.yml ......................... composite: ten inputs, ten steps, no CLI of its own
  |-- validate_inputs.py           exit 0 | 2      refuses before the network is touched
  |-- actions/checkout + setup-go  pinned           fetches and builds Gauge at gauge-ref
  |-- stellar-gauge audit --format json             the only producer of findings
  |-- sync_issue.py find            exit 0 | 2 | 3  hands over the current issue body
  |-- render_report.py              exit 0 | 2      report + previous body -> new body
  |-- sync_issue.py write           exit 0 | 2 | 3  creates, updates, or touches nothing
  '-- propagate exit                              0/1 green (1 unless break-build), 2/3 red
```

One pass, one artifact each, everything handed over through files under `$RUNNER_TEMP`. No
step reads another step's stdout. There is no long-lived state, no daemon, no cache, and no
code path that runs more than once per workflow run.

There is no CLI in this repository on purpose. The deliverable is `action.yml`, and the thing
that makes it a control rather than a tool is that it runs from a schedule inside the
consumer's own repository, where installing a binary is somebody's recurring chore.

## 2. The version contract

Gauge's JSON report is the interface between the two repositories, and it is not versioned:
there is no schema field and no compatibility promise. So the renderer treats the contract
as a set of names it refuses to run without, and a rename or a retype fails the run rather
than silently dropping findings.

Load bearing, checked in `read_report` and `collect_findings` (`scripts/render_report.py`):

| Path | Kind | What breaks if it changes |
|---|---|---|
| `tool_version` | non-empty string | No tool version in the header, so a report stops being traceable. Refused. |
| `network` | string, escaped | The header would not say which network was read. Refused. |
| `ledger` | rendered as given | The "at one ledger" claim becomes unverifiable. Refused if absent. |
| `exit_code` | must equal `--exit-code` | A report that disagrees with the process it came from is not rendered. Refused. |
| `limits` | string | The footer that tells a reader what the report cannot see. Refused if absent. |
| `accounts` | array of objects | Everything. Refused if missing or not an array. |
| `accounts[].snapshot.id` | string | Findings are keyed by account; without an id the row cannot be named. Refused. |
| `accounts[].findings[].rule_id` | non-empty string | Sorted, grouped and accepted-key matching all use it. Refused if missing. |
| `accounts[].findings[].severity` | `high` or `warn` | An unknown value makes the counts and the sort meaningless. Refused. |
| `accounts[].findings[].fingerprint` | exactly `[0-9a-f]{64}` | It is the identity of a finding across runs. Refused: no fingerprint means no change detection. |
| `accounts[].findings[].message` | string, escaped | Only display; an absent message renders empty rather than failing. |
| `accounts[].findings[].accepted` | `true` splits it out | Anything that is not exactly `true` counts as open, which is the unsafe direction. |
| `accounts[].missing`, `accounts[].skipped` | optional | A missing account with no findings is not a clean account; see `account_status`. |
| `accounts[].snapshot.{thresholds,signers,balances,flags,home_domain}` | display only | Absent or partial renders as zeros, `none` or `(none)` in the Accounts table. |

Deliberately not load bearing: `accounts[].snapshot.sequence`, `sponsor`, `endpoint`,
`balances[].*` beyond their count, and `evidence`. Gauge's report carries them and the
renderer ignores them, so adding a balance or changing a sequence never changes an issue.

The consequence to keep: **a Gauge change that renames one of the load bearing keys must make
this action exit 2 loudly**, which is what the refusals above are for. That is roadmap 1.10,
and it is the reason `tests/fixtures/` holds captured reports instead of hand-written ones:
a fixture typed from a spec tests the renderer against the spec, not against what Gauge
actually emits. Gauge's own JSON writer (`internal/report/json.go`) sanitizes characters but
does not escape markdown markup, which is why escaping lives here and not there.

## 3. `validate_inputs.py`: the pre-flight

Exit 0 or 2. It checks the Action's own surface, not Gauge's:

- `gauge-ref` is exactly 40 hex characters; `gauge-repo` is `owner/name` of safe segments.
- `fail-on` is `high` or `warn`; label and title are non-empty, at most 256 characters, and
  carry no control character or newline.
- `config` is a path inside the workspace: not absolute, no `..` segment, existing, a regular
  file, at most 1 MiB.
- The policy file itself parses as TOML with `version = 1`, names a network, lists https
  endpoints, and has at least one `[[account]]` whose `id` decodes as a canonical `G...`
  strkey. An `M...`, `C...` or seed-shaped address gets its own message.
- A seed-shaped string anywhere in the raw policy text is refused, with the head and tail of
  the token printed but never the whole thing, and with a line saying whether its checksum
  verifies, because one that does must be treated as live and rotated.

Why it re-implements the strkey and CRC16 checks rather than trusting Gauge: the pre-flight
runs before a Go toolchain is fetched, so a bad address costs seconds instead of a build.
Gauge validates the same fields again in `internal/policy`, and that check is the authority;
this one exists to refuse early and to refuse in one pass. All problems are collected and
printed together, because a workflow author should not discover the second one on the next
run. Exit 2 stops the action before the checkout step.

## 4. `render_report.py`: report in, body out

Exit 0 or 2, and never a partial body: every refusal raises `Refused` before anything is
written. Section 2 lists what it insists on. Three jobs beyond layout:

**Escaping.** `escape()` backslash-escapes the characters that can open markup in an issue
body and rewrites every `@mention` as `@&#8203;name`, so a chain-chosen `home_domain` or
finding message cannot open a link, embed an image or notify `@all`. `fenced()` puts a value
in backticks with any inner backtick turned into `&#96;`, so a value cannot break out of the
code span that contains it. Both are applied at the point of writing, which means a new
table row that forgets them is visible in a test rather than in an issue.

**Change detection.** The identity of a finding is its fingerprint. The previous body's
marker is decoded, the two sets are compared, and `new` / `resolved` are what differ. An
accepted finding is out of both sets on purpose: it is recorded, listed under its own
heading, and never reappears as a change.

**The marker.** `MARKER_PREFIX` plus base64url of a compact sorted JSON array plus
`MARKER_SUFFIX`, one HTML comment at the foot of the body. base64url because an HTML comment
cannot contain `--` and a finding message can; the encoding is what lets the payload survive
a round trip through the issue API. Up to `MAX_STATE_ENTRIES` (200) findings or
`MAX_MARKER_CHARS` (20 000) characters, whichever comes first. Anything left out is counted
and the body opens with a bold **Change detection is partial.** line naming both numbers,
because a silently truncated marker would report "unchanged" for findings nobody compared.

If a human edits the body and destroys the marker, `decode_state` returns `None` and the
next run declares a baseline rather than inventing a diff. That is the known cost of D-07,
and it is the failure mode most likely to be hit by accident.

## 5. `sync_issue.py`: one issue, no redirects

Exit 0, 2 or 3, with 2 for an input it will not send and 3 for an API it could not reach or
understand. Two actions, `find` and `write`, sharing one argument surface.

- Token from `POSTURE_WATCH_TOKEN` in the environment only. It is never an argument, because
  arguments show up in step logs and in `ps`.
- `api_base()` is https-only and takes no path, so a host or a scheme cannot be smuggled in
  through an input. `GITHUB_API_URL` is honored only when it is https without a path.
- Owner, repo and label each match `[A-Za-z0-9._-]{1,100}` before they are interpolated into
  a URL path, and title is length- and control-checked. `find` requires
  `--previous-body-out`, so the handover to the renderer cannot be skipped.
- Redirects are refused, not followed: `RedirectRefused` subclasses the default handler and
  raises from `redirect_request`, so a 3xx cannot send the token to another host. There is
  a loopback test that a `302` is refused and that only the original path is requested.
- One `urllib` call site, 30 second timeout, three bounded attempts with exponential backoff
  capped at 60 seconds, honoring `Retry-After` when the response gives it.
- Failure messages pass through `redact()`, which masks anything that looks like a `Bearer`
  credential, so a URL echoed back from an error cannot leak the token.
- `find` searches open issues with the configured label for the marker, then falls back to
  adopting an open issue with the configured title, across at most five pages of 100.
- `write` creates the baseline when there is no issue, updates body plus one comment when the
  list moved, and does nothing when it did not unless `--update-on-no-change`.
- Bodies over `BODY_LIMIT` (65 536 characters) are trimmed by dropping rows from the Current
  findings table, and the table keeps a row saying how many were dropped. If no trim fits,
  it exits 2 rather than sending a body the API will reject with a message nobody reads.

## 6. The seam, and how the tests use it

`TRANSPORT = transport` is the module-level name every API call goes through
(`request()` looks it up at call time, not at definition time). The suite replaces it with a
stub to drive the branches that a fake cannot reach: 404, 429 with `Retry-After`, 5xx, a
body that never parses, a rate-limit loop, redaction. `TestRealTransport` does **not** use
the seam: it runs a `ThreadingHTTPServer` on 127.0.0.1 and calls the real function, which is
how the header set, the POST body and the redirect refusal are actually observed rather than
asserted against a mock of themselves.

The tests are the only thing in this repository that runs on more than one Python: 167 cases
across five files, no network beyond loopback, and none of them starts a runner.

## 7. Failure modes, and what a reader sees

| Failure | Where it lands | Signal |
|---|---|---|
| Input unusable (bad sha, bad path, bad policy) | `validate_inputs.py` | First step fails, exit 2, nothing fetched, no issue touched. |
| Gauge refuses the config (exit 2) | `render_report.py` | Gauge writes no report to stdout on a usage error, so the renderer refuses an empty file and the run is red at that step. No issue is opened or edited. |
| Endpoint unreachable, or one account read fails (exit 3) | `render_report.py` | Same shape: `internal/run` cancels on the first fetch error and returns no report, so the body is never rendered and the run is red. Gauge's stderr goes up as the `gauge-diagnostics` artifact. |
| Network mismatch (exit 1) | Renders | Each account row says `not read: the endpoint is on a different network`, `acct-network-mismatch` carries the finding, and the run is green by D-05. |
| Account not on this endpoint (exit 1) | Renders | The row says `not found on this endpoint` and carries `(not read)` in its data columns, so an absent account never reads as a configured one. |
| Report inconsistent with the run | `render_report.py` | Exit 2, body never written, no API call made. |
| Issue API unreachable or refused | `sync_issue.py` | Exit 3 with the token masked. The audit still ran, so the `exit-code` output is intact. |
| Body over the API limit | `sync_issue.py` | Rows trimmed with a visible count, or exit 3 if trimming cannot fit. |
| Findings present | `Propagate` step | Green by default (D-05), and the issue is the record. Red with `break-build: true`. |

A run that fails before the write step leaves the previous issue body untouched, which is
the intended behavior: a broken read must not look like a fixed account. Exit 2 and exit 3
are therefore both loud and both inert, and the artifact in the run history is where the
reason lives.

## 8. What is deliberately not here

No detection logic, so no rule can be argued with here; take it to Gauge. No SARIF, no
pull request review comments, no second policy file per issue, no HTTP server, no cache of
previous reports, and no dependency beyond the standard library (`ROADMAP.md` D-02, 9.1 to
9.3). No `pip install` step in any workflow: the runner has `python3`, and the two dev tools
are pinned in `requirements-dev.txt` for the people who run them.

## 9. Read order for a change

`ROADMAP.md` section 4 for what is wanted, this file for what it touches, `SECURITY.md` for
what must not break, `CONTRIBUTING.md` for how to prove it. `action.yml` is the shortest
read of the three contracts and is the one a consumer sees.

```
action.yml                    the surface: inputs, outputs, step order, exit mapping
scripts/validate_inputs.py    what is refused, and in one pass
scripts/render_report.py      the report contract (section 2), escaping, the marker
scripts/sync_issue.py         the API, the seam, the limit
tests/                        what all of the above is held to
```
