# Contributing to stellar-posture-watch

This is plumbing in front of somebody else's detector, so the bar for a change is narrow: it
must not soften a refusal, must not print what it was given, and must not claim a run that
did not happen. Read `ARCHITECTURE.md` section 2 before touching the renderer and
`ROADMAP.md` section 4 before opening a pull request.

## Status

Three scripts, one `action.yml`, 167 tests, and one hosted run of the action itself. The
table below was written from a local checkout: the suite on Python 3.11.16 and 3.12.3, and
`ruff` and `mypy` at their pinned versions from the tool venv, and `ROADMAP.md` says which
gates are waiting on a runner rather than on code. The same three checks, plus the action
itself, have since run green on GitHub on pull request #1 at `b107b0f` (2026-11-04), and that
pull request's push to `main` passed `ci / python` there, which is gate G1. No tag, no release,
nothing to install. `main` is protected as of 2026-11-04: ruleset 26515104 requires a pull
request and both `ci / python` and `roadmap-check / gate`, and a direct push to `main` was
observed refused with `push declined due to repository rule violations`. That is the machine
version of the rules below, and it stops at exactly that: no approving review is required,
because this repository has one maintainer and an approving review from a single maintainer is
a formality, not a check. `.github/workflows/scorecard.yml` runs on every push to `main` and
weekly, and publishes its result: it grades the workflows in this directory, so an edit to a
`uses:` pin or a `permissions:` block moves a number that strangers can read.

## The rules, and what enforces each one

Each rule is a refusal in the code, not advice. Break one and something exits non-zero and
says why in one line.

| Rule | Enforced by |
|---|---|
| `gauge-ref` is a full commit sha, with no default. | `validate_inputs.py` refuses anything that is not `[0-9a-f]{40}`, and `render_report.py` refuses it again on the way to the body. A branch name would change what gets compiled without changing a file in the consumer's repository. |
| No input reaches a shell command. | Every step in `action.yml` passes its inputs through `env:`. There is no `${{ inputs.* }}` inside a `run:` block to inject into, which is the class of bug that makes composite actions dangerous. |
| The report never reaches the log. | D-06. The audit step redirects stdout to `$RUNNER_TEMP/report.json` and stderr to a file, prints one line of byte counts, and the diagnostics artifact is uploaded only `if: failure()`. |
| A seed-shaped string is refused, quietly. | `validate_inputs.py` sweeps the raw policy text and prints only the head and tail of the token, with a line saying whether its checksum verifies, because one that does is live and needs rotating. `tests/fixtures/README.md` and its test refuse a fixture that carries one. |
| Only `G...` addresses. | The validator refuses `M...`, `C...` and seed-shaped values with a message naming each, then checks shape, checksum and version byte. Gauge re-checks this in `internal/policy`; the pre-flight exists so a bad address costs seconds rather than a Go build. |
| Markdown markup from the chain is neutralised. | `escape()` in `render_report.py` backslash-escapes markup characters and rewrites `@mentions` with a zero-width space; `fenced()` turns inner backticks into `&#96;`. `report-hostile-strings.json` is the fixture that proves a `home_domain` cannot open a link or notify `@all`. |
| Nothing is rendered that cannot be accounted for. | `ARCHITECTURE.md` section 2 lists the load-bearing report fields. A missing field, an unknown severity, a fingerprint that is not 64 hex, or an exit code that disagrees with the run raises `Refused`: exit 2 and no partial body. |
| Change detection says so when it is partial. | `encode_state` returns the count it dropped, and the body opens with a bold line naming both numbers instead of reporting "unchanged". |
| HTTPS only, no redirects, bounded retries. | `api_base()` refuses anything that is not a bare https host; `RedirectRefused` raises instead of following; `request()` makes at most three attempts with a 60 second ceiling on the wait. `TestRealTransport` observes all of it against a loopback server. |
| The token is never an argument. | `POSTURE_WATCH_TOKEN` in the step's `env`, and `redact()` masks a bearer value in every failure message. |
| Python standard library only. | D-02. The three scripts import nothing outside it; `tomllib` (3.11+) is the only non-obvious one. `requirements-dev.txt` is dev tooling, not a runtime dependency, and no workflow installs anything. |
| Tests do not touch the network. | The only sockets are loopback servers started inside the test process, plus subprocesses of the three scripts over a temporary directory. |
| A schedule stays green for findings and red for failures. | D-05, mapped in the last step of `action.yml`. Do not "fix" a red run by weakening this: exit 2 and 3 mean nothing was read. |
| Never weaken, skip or delete a check to make something pass. | If a test is wrong, fix the test and say why in the pull request. If a check is wrong, the check is the bug. |

## Workflow

1. Find the task in `ROADMAP.md`. If it does not exist, add it with the next free ID in its
   phase and say why.
2. Check its dependencies are done. If they are not, stop and report that on the issue.
3. Branch from `main` as `feat/<task-id>-<slug>`.
4. Write the failing test first and watch it fail for the right reason. The renderer and both
   API paths are driven as subprocesses and through the `TRANSPORT` seam, so a new behaviour
   has an existing harness to join.
5. Implement the smallest change that passes.
6. Run the checks below and paste the real output in the pull request.
7. Update the docs the change touches: `ARCHITECTURE.md` section 2 for anything about the
   report contract, `README.md` for what an operator sees, this file for a rule.
8. Update `ROADMAP.md` in the same pull request: the task box, a changelog row with the UTC
   time from `date -u` at the moment of writing, then `python3 scripts/roadmap_progress.py`,
   then the `Last updated` line. CI enforces this as a required check, so a change that skips
   it cannot merge.
9. One pull request per task, or per one tightly related group.

## Checks

```bash
python3 -m unittest discover -s tests -t tests
ruff check . && ruff format --check .
mypy
scripts/check_roadmap_touched.sh origin/main
python3 scripts/roadmap_progress.py --check ROADMAP.md
```

`ruff` and `mypy` are pinned in `requirements-dev.txt`, the file CI installs from, so a local
run and a hosted run use the same two versions. `mypy` reads its target list from
`pyproject.toml`. The suite runs on 3.11 and 3.12; if you add a syntax feature, check the
floor as well as your own interpreter.

If you change `action.yml`, run the two parsers that catch what a reviewer will not:

```bash
python3 -c 'import yaml,sys; yaml.safe_load(open("action.yml")); print("parses")'
```

and open the pull request, because `.github/workflows/self-check.yml` consumes the local
action with `dry-run: true`. That workflow is not a required check: a testnet outage should
not make this repository unmergeable. Its run is the evidence for 1.8 and G3, so read its
output rather than its colour.

## Changing what the issue looks like

The body is the product. Three constraints hold it together:

- The fingerprint, not the message, is a finding's identity. Do not key change detection on
  text: Gauge rewords messages, and a reword would read as one finding resolved and another
  opened.
- The marker at the foot of the body is the only state. Anything that rewrites the body
  between the read and the write destroys it.
- Every string that came from the chain, the policy file or the report goes through `escape()`
  or `fenced()` at the point it is written. A new table row that forgets it is a way for an
  account owner to format your issue.

Golden-style bodies are written per test into a temporary directory; there is no `-update`
flag, because a body that changes shape should be argued about in a pull request rather than
regenerated silently.

## Issues

One issue per open roadmap task, with the task's `Done when` line as the acceptance criteria.
`ROADMAP.md` section 5 rows that name a gate (G1 to G5) are not issues: they are claims that
need an observed run, and nobody should close one with a code change.

## Naming and writing

Scripts are `snake_case` verbs of what they do, findings-level names come from Gauge, and the
rule ids in a body are Gauge's, never paraphrased. Docs, comments and commit messages use
plain language with no em dashes, comments explain why rather than what, and commits follow
Conventional Commits with the subject under 72 characters. This repository reports posture. It
never calls an account secure or safe, and a clean issue is not a claim that an account
cannot be used.
