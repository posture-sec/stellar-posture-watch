# stellar-posture-watch

<p align="center">
  <a href="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/ci.yml"><img src="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/roadmap-check.yml"><img src="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/roadmap-check.yml/badge.svg" alt="Roadmap check" /></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/posture-sec/stellar-posture-watch"><img src="https://api.scorecard.dev/projects/github.com/posture-sec/stellar-posture-watch/badge" alt="OpenSSF Scorecard" /></a>
  <a href="https://github.com/posture-sec/stellar-posture-watch/actions"><img src="https://img.shields.io/endpoint?url=https://posture-sec.github.io/stellar-posture-watch/data/badge-tests.json" alt="Tests" /></a>
  <a href="#what-it-catches-today-stated-plainly"><img src="https://img.shields.io/endpoint?url=https://posture-sec.github.io/stellar-posture-watch/data/badge-rules.json" alt="Rules" /></a>
  <a href="https://posture-sec.github.io/stellar-posture-watch/"><img src="https://img.shields.io/badge/docs-live-8b5cf6" alt="Documentation Site" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0" />
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/status-unaudited-orange" alt="Unaudited" /></a>
  <a href="ROADMAP.md"><img src="https://img.shields.io/badge/status-functional%20alpha-orange" alt="Functional alpha" /></a>
</p>

A composite GitHub Action that runs `stellar-gauge` on a schedule and keeps one tracking
issue current.

[Documentation site & Workflow Builder](https://posture-sec.github.io/stellar-posture-watch/) · [Action Specification](action.yml) · [Usage](#usage) · [What it catches](#what-it-catches-today-stated-plainly) · [Contributing](CONTRIBUTING.md)

Gauge reads an account and compares it to a policy. It is a gate you walk through: useful,
and worthless if nobody walks through it. This repository is the clock. Point a weekly
workflow at it, name the Gauge commit to build, and the findings arrive in your own issue
tracker whether or not anybody remembered to run the tool.

It owns no detection logic. Every finding it publishes came from Gauge, and the issue body
names the commit that produced it, so a report can be traced back to the code that made it.

```
action.yml              the whole product: ten inputs, ten steps
scripts/
  validate_inputs.py    refuses an unusable input before anything is fetched
  render_report.py      one Gauge report in, one issue body out
  sync_issue.py         the GitHub issue API, one issue, no redirects
  check_action.py       the action.yml invariants CI enforces instead of asserting in prose
tests/                  185 cases, loopback only, run against captured reports
```

## Status

<!-- METRICS:START -->
| Indicator | Value | Source |
|---|---|---|
| Unit & Action Tests | **194 passing** | `python -m unittest` |
| Supported Findings | **4 active rules** (`acct-*`, `flag-*`) | `action.yml` |
| Runtime Footprint | **0 external dependencies** | Python standard library |
| State Tracking | **Idempotent issue marker** | `<!-- posture-watch:v1:state -->` |
<!-- METRICS:END -->

Functional alpha, and hosted. The three scripts and `action.yml` exist and pass 185 tests
against real testnet reports captured from Gauge, and a GitHub runner has now run them: on
2026-11-04 `ci / python`, `roadmap-check / gate` and `self-check / action` were all green on
pull request #1, and that last job executed this action itself against live testnet. The pull
request then merged, and its push to `main` passed `ci / python` there, which closes gate G1.
And the write has happened. On 2026-11-04 `.github/workflows/watch.yml` ran with `dry-run` off,
built Gauge at the same pinned sha, and **opened issue #6 in this repository** with one high
finding; a second run at 08:39:51Z found that issue by the state marker in its body and
left it untouched.

An interactive Web3 Sentinel documentation site and visual Workflow Builder is live at
**[https://posture-sec.github.io/stellar-posture-watch/](https://posture-sec.github.io/stellar-posture-watch/)**.
It includes an interactive schedule/config generator, live clean vs drift issue simulator, complete action input/output specs, security invariants, and a comprehensive FAQ. `ROADMAP.md` section 6 records which gates those two runs close and what is
still open. Nothing here is a tag, and there is no released version to depend on.

## What it catches today, stated plainly

Four rules ship in Gauge at the commit this repository's fixtures were captured from, and
those are the only findings this action can put in an issue:

| Rule | Severity | What it says |
|---|---|---|
| `acct-missing` | high | The policy names an account the endpoint does not have. |
| `acct-network-mismatch` | high | The endpoint serves a different network than the policy declares. |
| `flag-drift` | high | An account flag disagrees with the value the policy expects. |
| `flag-undeclared-clawback` | warn | `clawback` is set and the policy never mentioned it. |

There is no signer rule and no threshold rule yet. Gauge's own roadmap task 3.1 is blocked
behind its 0.7, which needs a transaction it will not build. So a watch run today tells you
an account vanished, moved network, or grew a flag; it does not tell you a threshold left the
2-of-3 custody scheme alone reachable. That is the honest state, and it is why this
repository's value right now is the plumbing rather than the findings.

Gauge merged three identity rules (`id-no-home-domain`, `id-toml-unreachable`,
`id-toml-account-unlisted`) on 2026-11-03, after every fixture here was captured. They live on
its `main`, not in the `da656733` sha this repository pins, so they cannot appear in an issue
until a pull request bumps `gauge-ref` to a commit that carries them and the state rows are
read again.

## Usage

`.github/workflows/posture-watch.yml` in the repository you want watched. Actions are
pinned by commit sha here as everywhere else in this organization, so replace the one
placeholder with the sha of the commit of *this* repository you read before using it.
This repository runs it too. `.github/workflows/watch.yml` is the file above with `dry-run` off
and `uses: ./` in place of the pin, pointed at `example/gauge.toml`: a local action reference is
resolved from the commit the schedule ran at, so there is no second sha to bump in the diff that
changes the code it points to. That is the dogfood, and it has run: issue #6 is what that
schedule writes, and `ROADMAP.md` 3.1 names the two dispatches and what each printed. One
repository that is not this one runs it as well, in the pinned form above:
`posture-sec/stellar-account-fixtures` consumes this action at `deaf7dcc` from its own
`.github/workflows/posture-watch.yml` and watches the account behind one of its captures, which is
roadmap 3.4 and the worked example to copy if you want the sha rather than the local reference.

```yaml
name: account posture
on:
  schedule:
    - cron: '17 6 * * 1'
  workflow_dispatch:

permissions:
  contents: read
  issues: write

jobs:
  watch:
    name: watch / audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: posture-sec/stellar-posture-watch@REPLACE-WITH-A-SHA-YOU-READ
        with:
          gauge-ref: da656733fff839d5cf20f795460f4365a7254257
          config: .posture/gauge.toml
          fail-on: warn
```

`gauge-ref` has no default and will not accept a branch or a tag. That is the point: this
action compiles Go code from that commit, so the only way to change what runs should be a
one-line diff in your workflow file, reviewed like any other dependency bump.
`example/workflow.yml` is the same file with the schedule commented and the inputs spelled
out, and `example/gauge.toml` is the policy it reads.

## The signal, and why a finding is not a red X

Gauge exits 0 with nothing open, 1 with findings at or above `fail-on`, 2 when it refuses
the configuration, and 3 when it cannot read the account. On a schedule this action keeps
the run **green for findings** and **red for failures**: the tracking issue is the signal
for the first case, and the second means nobody looked at anything. A weekly cron that
mails you a red X for a WARN you already accepted trains everyone to ignore the mail. Set
`break-build: true` when you want findings to fail the run instead, which is the right
answer in a `pull_request` workflow and the wrong one in a cron.

Exit 2 and exit 3 always fail the run whatever that input says. The second of those is not
something you have to take on faith: this repository's own `self-check` workflow has a job
that audits a policy pointing at an endpoint no resolver answers for, and it fails the job
unless that run wrote no report and rendered no body. A broken read never reaches a reader
as a fixed account.

## What the issue looks like

One issue per policy file, titled `Account posture watch` unless you change `title`, labeled
`account-posture` unless you change `issue-label`. Its body carries:

```
Posture changed since the previous run: 1 finding open (1 high, 0 warn) across 1 account read of 2 asked about.

As of 2026-11-03, read at ledger 5535642 on Test SDF Network ; September 2015 with
`0.1.0-dev`, built from `posture-sec/guage` at `da65673`, auditing `.posture/gauge.toml`
with --fail-on warn.

## New since the previous run
## Resolved since the previous run
## Current findings
## Accepted in the policy          (only when the policy has [[accept]] entries)
## Accounts asked about            (ledger, thresholds, signer and balance counts, flags, home domain)
## What this cannot see            (Gauge's own limits footer, verbatim)
```

A run that finds the same posture leaves the body alone, so the header date means "the run
that changed something" and the workflow run history means "the newest read". When the list
does move, the change gets one comment as well as the rewritten body. Which findings moved
is decided by the fingerprint Gauge puts on each one, not by the message text.

The one case where that rule wants an override is a fix to the renderer's wording: a body is
written by the code that read the chain, so a corrected sentence reaches an existing issue at
the next change in posture or not at all. `watch.yml` therefore takes a `refresh_body` box on a
manual dispatch, which is the action's `update-on-no-change` input and nothing else. It rewrites
the body and posts no comment, and it moves the header date without moving the posture. That is
the cost, and it is why the scheduled run never has it on. Issue #6 is the proof it works: its
first line now reads "across 2 accounts read of 3 asked about" and its account section is titled
`## Accounts asked about`, on the same finding and the same state marker the run that opened it
wrote.

The first line counts the accounts the run actually read. "across 1 account read of 2 asked
about" means the policy named two and the endpoint had one of them; an account that is not
there is a finding in its own right, not a read that came up empty, so it is left out of the
numerator. When every account was read the sentence says so plainly and carries no denominator.
The table beneath it is titled `## Accounts asked about` because it carries every account the
policy named, read or not, and its `Read` column is where a run says what happened to each one.
A heading that claimed "read" would contradict the row directly underneath it.

Everything chain-derived goes through escaping before it reaches the body. A `home_domain`
is chosen by the account's owner, and a tool that pastes it into markdown would let a
hostile account open a link or notify your team: the renderer backslash-escapes markup and
breaks mentions with a zero-width space, so `[click here](javascript:alert(1)) @all` in a
home domain renders as text and pings nobody.

## Limits

- **It says posture, never secure.** A clean list means four rules agreed with your policy
  at one ledger. It does not mean the account cannot be used, and the issue body says so in
  Gauge's own footer on every run.
- **The state lives in the issue body.** Change detection reads an HTML comment at the foot
  of it. Edit that comment out and the next run re-baselines rather than pretending it knew;
  that cost is `ROADMAP.md` D-07, chosen over a label system that needs a second authority
  to clean up.
- **It is not a sandbox.** This action fetches and compiles Go code from another repository
  at the sha you name. Pinning makes that code auditable and the bump reviewable; it does
  not confine it. `SECURITY.md` states what is in scope if you think the boundary is wrong.
- **Verification is testnet.** Every captured report in `tests/fixtures/` is a testnet read
  (`ROADMAP.md` D-03). A mainnet audit is your act as the operator, not this repository's
  test.
- **The marker holds 200 findings.** Past that, or past 20 000 characters, the body opens
  with a bold line saying change detection is partial and naming both numbers. It does not
  quietly truncate.
- **One policy file, one issue.** Multiple files need multiple workflows (`ROADMAP.md` 9.3).

## Checks

```
python3 -m unittest discover -s tests -t tests   # 167 cases, no network
ruff check . && ruff format --check .
mypy
python3 scripts/roadmap_progress.py --check ROADMAP.md
```

Those are the commands, re-run locally on 2026-11-04: the suite passes its 167 cases on both
Python 3.12.3 and 3.11.16, and `ruff` 0.17.3 and `mypy` 2.4.0 (clean on the ten typed files)
come from a pinned tool venv whose own interpreter is 3.14.0. That is what `ROADMAP.md`
claims and nothing more. `.github/workflows/ci.yml` runs them on 3.11 on
every pull request and every push to `main`, `.github/workflows/roadmap-check.yml` is the
roadmap gate, and `.github/workflows/self-check.yml` consumes this directory as an action
with `dry-run: true` so the yaml is executed rather than only parsed.
`.github/workflows/watch.yml` is the same call with `dry-run: "false"`, on a Tuesday schedule,
and it is the file that wrote issue #6.

Those three have since run on GitHub rather than here: on 2026-11-04, at `b107b0f` on pull
request #1, `ci / python` (job 126439899511) passed on CPython 3.11.17 with the same 167 cases
and the same clean lint, format and type output, `roadmap-check / gate` (126439899465) passed
after its own first run failed on a fetch it did not need, and `self-check / action`
(126439899851) ran this action end to end: it fetched Gauge at the pinned sha, built it, read
`example/gauge.toml` against live testnet, and the syncer stopped at the dry run it was told
to stop at. G1 is closed, because the push that merge produced ran `ci / python` on `main`
itself: job 126445751941 on `db8a5ed`, CPython 3.11.18, the same 167 cases green on the trunk
rather than on a branch. The write came the same day, from a fourth workflow: `watch / audit`
(job 126475427542, 08:36:02Z) opened issue #6 carrying one high `acct-missing`, on a green job
while Gauge exited 1, and job 126477058944 at 08:39:51Z found that issue by its state marker,
rendered 2291 characters of no change and left the body byte-identical with `updated_at` unmoved.
Gates G3 and G4 close on those two runs and on reading the body against a report reproduced from
the same sha on the desk, which is `ROADMAP.md` 3.1 and G4.

The path into `main` is enforced as of 2026-11-04: ruleset 26515104 refuses a direct push and
requires both `ci / python` and `roadmap-check / gate`, and the refusal was observed rather than
assumed. What it does not require is an approving review, because this repository has one
maintainer; `ROADMAP.md` 2.7 states that limit.

The first OpenSSF Scorecard result is the `scorecard / analysis` job 126460914087 on the push
that pull request #3 merged into `main` at `8a308ac`, published 2026-11-04T08:00:51Z: **5.2**
over 18 checks, which is the number in the badge above. Read it against what this repository
actually is. `Dangerous-Workflow`, `Token-Permissions`, `CI-Tests`, `Binary-Artifacts`,
`Vulnerabilities`, `Security-Policy` and `License` score 10, and the first two are the checks
that matter for an action whose job is fetching and compiling another repository's Go code.
`Branch-Protection` is 4 for the three warnings its siblings carry: the ruleset requires the
pull request and the checks but no approver. `Pinned-Dependencies` is 6 because one `pip install`
line in `ci.yml` installs the dev tools by requirement file rather than by hash, which is the
same reason the corpus scores 6. `Maintained`, `Code-Review`, `Contributors`,
`CII-Best-Practices`, `Dependency-Update-Tool` and `SAST` are 0 for six facts about the setup
rather than the code: one maintainer reviewing only their own pull requests, a repository created
this month, no OpenSSF badge registered, no update bot, and no code-analysis tool running on its
commits. `Fuzzing` is a seventh zero and it is not about the setup: `render_report.py` parses a
report whose contents came off the chain, and nothing hammers it. `Packaging` and `Signed-Releases` are -1 because
nothing is published from this repository at all. None of the eighteen measures the sentence a
consumer would most want. That sentence is now issue #6, and the gate that used to say it had not
happened is closed.
[Full result](https://scorecard.dev/viewer/?uri=github.com/posture-sec/stellar-posture-watch).

## Siblings and licence

[Gauge](https://github.com/posture-sec/guage) produces the findings,
[the fixtures corpus](https://github.com/posture-sec/stellar-account-fixtures) proves the
account shapes the rules are written against, and
[Airlock](https://github.com/posture-sec/airlock) watches repositories instead of accounts.
No code is shared between them by design (`ROADMAP.md` D-04); this repository copies the two
roadmap guard scripts and their self-test rather than importing them.

Apache License 2.0; see `LICENSE`. `CONTRIBUTING.md` has the rules for a pull request,
`SECURITY.md` has the private reporting path, and `AGENTS.md` in the Gauge repository states
the working conventions this one keeps.
