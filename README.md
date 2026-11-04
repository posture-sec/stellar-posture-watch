# stellar-posture-watch

<p align="center">
  <a href="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/ci.yml"><img src="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/roadmap-check.yml"><img src="https://github.com/posture-sec/stellar-posture-watch/actions/workflows/roadmap-check.yml/badge.svg" alt="Roadmap check" /></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/posture-sec/stellar-posture-watch"><img src="https://api.scorecard.dev/projects/github.com/posture-sec/stellar-posture-watch/badge" alt="OpenSSF Scorecard" /></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/status-unaudited-orange" alt="Unaudited" /></a>
  <a href="ROADMAP.md"><img src="https://img.shields.io/badge/status-functional%20alpha-orange" alt="Functional alpha" /></a>
</p>

A composite GitHub Action that runs `stellar-gauge` on a schedule and keeps one tracking
issue current.

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
tests/                  167 cases, loopback only, run against captured reports
```

## Status

Functional alpha, and hosted. The three scripts and `action.yml` exist and pass 167 tests
against real testnet reports captured from Gauge, and a GitHub runner has now run them: on
2026-11-04 `ci / python`, `roadmap-check / gate` and `self-check / action` were all green on
pull request #1, and that last job executed this action itself against live testnet. The pull
request then merged, and its push to `main` passed `ci / python` there, which closes gate G1.
What has not happened is the write: every run was a dry run, so **no issue has ever been opened
or edited by this action**. `ROADMAP.md` section 6 lists the gates that turn those sentences into
something else, and section 4 says which one is next. Nothing here is a tag, and there is no
released version to depend on.

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
changes the code it points to. That is the dogfood. Until a run of it files an issue, the write
is still the unproven part, and `ROADMAP.md` gate G3 is the row that says so.

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

Exit 2 and exit 3 always fail the run whatever that input says.

## What the issue looks like

One issue per policy file, titled `Account posture watch` unless you change `title`, labeled
`account-posture` unless you change `issue-label`. Its body carries:

```
Posture changed since the previous run: 1 finding open (1 high, 0 warn) across 2 accounts read.

As of 2026-11-03, read at ledger 5535642 on Test SDF Network ; September 2015 with
`0.1.0-dev`, built from `posture-sec/guage` at `da65673`, auditing `.posture/gauge.toml`
with --fail-on warn.

## New since the previous run
## Resolved since the previous run
## Current findings
## Accepted in the policy          (only when the policy has [[accept]] entries)
## Accounts read                   (ledger, thresholds, signer and balance counts, flags, home domain)
## What this cannot see            (Gauge's own limits footer, verbatim)
```

A run that finds the same posture leaves the body alone, so the header date means "the run
that changed something" and the workflow run history means "the newest read". When the list
does move, the change gets one comment as well as the rewritten body. Which findings moved
is decided by the fingerprint Gauge puts on each one, not by the message text.

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
and it is the file that was written to make the write stop being the unproven part.

Those three have since run on GitHub rather than here: on 2026-11-04, at `b107b0f` on pull
request #1, `ci / python` (job 126439899511) passed on CPython 3.11.17 with the same 167 cases
and the same clean lint, format and type output, `roadmap-check / gate` (126439899465) passed
after its own first run failed on a fetch it did not need, and `self-check / action`
(126439899851) ran this action end to end: it fetched Gauge at the pinned sha, built it, read
`example/gauge.toml` against live testnet, and the syncer stopped at the dry run it was told
to stop at. G1 is closed, because the push that merge produced ran `ci / python` on `main`
itself: job 126445751941 on `db8a5ed`, CPython 3.11.18, the same 167 cases green on the trunk
rather than on a branch. One thing is still not proven: G3 waits on an issue, because every run
so far has opened or edited nothing. A green hosted run and a hosted write are different claims,
and the sentences above are evidence for the first only.

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
consumer would most want, and G3 is still the row that says it has not happened.
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
