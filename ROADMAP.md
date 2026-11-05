# ROADMAP: stellar-posture-watch

Status: **functional alpha, hosted, it has written, and something else uses it.** The action
exists, its three scripts are written and tested against real captured reports, and a GitHub
runner has now executed all four workflows and the action itself: `self-check / action` fetched
Gauge at the pinned sha, built it, read the example policy from live testnet and rendered the
issue body, stopping at the dry run. `watch / audit` does the same with the flag off, and on
2026-11-04 it opened issue #6 in this repository and then left it alone on a second run. Since
2026-11-05 a second repository calls it by sha rather than by `uses: ./`:
`posture-sec/stellar-account-fixtures` audited its own policy through this action, opened its
issue #29 with no findings, and left that issue alone on the run after, which is roadmap 3.4 and
the first `gauge exited 0` and clean body rendered on a runner. Gate G1 is closed, because
`ci / python` has been read green on the merge commit of pull request #1 on `main`. Gates G3 and
G4 are closed below, on the runs and on the reading of the body against the report. G5 is not,
and 3.4 did not close it: one maintainer wrote both callers. Every claim here names the run or
the file it was read from.

Last updated: 2026-11-05T08:27Z (Phase 3 moves to 5 of 8 and the readiness total to 34 of 39 on
3.4, closed by `posture-sec/stellar-account-fixtures`: its `posture-watch.yml` pins this action at
`deaf7dcc`, three dispatches from its `main` at `71dfffc` printed `gauge exited 0`, opened its
issue #29 with `0 open, 0 high, 0 warn, 0 accepted` and left that issue alone on the run after with
`changed=false`. That is the first call of this action written outside this repository, the first
clean body and the first exit 0 rendered on a runner. G5 stays open because both callers are the
same author, and 2.10 keeps its box for the tag alone now that its second done-when half is
satisfied. `docs/WAVE_SUBMISSION.md` loses four sentences that a finished piece of work left
behind, including one that still called this repository unexecuted, and `README.md` names the
pinned consumer as the example to copy. No code, test or workflow moves, so the suite stays 177.)

## 1. What this repository is

A composite GitHub Action that runs `stellar-gauge audit` on a schedule and keeps one
tracking issue current. It is the third shape of the same idea as its siblings: Gauge
reads an account's configuration and compares it to a policy, Airlock reads a repository
that publishes to Stellar, and this reads the *clock*, the thing that turns a tool you
run when you remember into a control that runs whether or not you do.

It owns no detection logic. Every finding in its output came from Gauge, and the reason
that matters is that the version of the answer is pinned: the action builds Gauge from a
full commit sha you name, and writes that sha into the issue body, so a report can always
be traced to the code that produced it.

Read `ARCHITECTURE.md` for how the pieces fit, `SECURITY.md` before reporting anything,
and `CONTRIBUTING.md` before opening a pull request. `AGENTS.md` in the sibling Gauge
repository states the working conventions this repository keeps.

## 2. How to read this file

- Tasks are `- [ ] **0.1** Title`, and once ticked they are never unticked or renumbered.
  A task that turns out to be wrong gets a replacement with a new number and a note.
- `[x]` means every Done-when clause under it was observed and is written into its note.
  `[~]` means part of it landed; it counts as unfinished.
- The `PROGRESS` table is generated. Do not edit it; run
  `scripts/roadmap_progress.py ROADMAP.md`. CI refuses a stale one.
- Gates are the G-numbers in section 6. They are separate from the readiness sum because
  a finished task list and a finished product are different claims.
- The changelog in section 8 records what changed and which tasks moved, dated in UTC.

## 3. Decisions

| ID | Decision | Status | Why |
| --- | --- | --- | --- |
| D-01 | The Gauge commit is pinned by a required full-40-hex `gauge-ref` input with no default. | Decided 2026-11-03 | A branch or tag makes the code that runs change without any file in the consumer's repository changing. A default sha would go stale in every workflow that uses this action. Requiring it makes the bump visible in a diff. |
| D-02 | Python 3.11+ standard library only, no runtime dependency, nothing installed. | Decided 2026-11-03 | The runner already has python3. `tomllib` arrives in 3.11 and is what reads the policy file. Same rule as Airlock and the fixtures corpus. |
| D-03 | Verification runs against testnet only. | Decided 2026-11-03 | Inherited from Gauge's D-16. Every captured report in `tests/fixtures/` is a testnet read, and a mainnet run is the operator's own act, not this repository's test. |
| D-04 | No shared code with the sibling repositories; the roadmap gate scripts and their self-test are copies. | Decided 2026-11-03 | A published corpus must not depend on a tool that depends on it. The two guard scripts are generic and travel with their tests. |
| D-05 | On a schedule the tracking issue is the signal; the run stays green for findings and red for failures. | Decided 2026-11-03 | A weekly cron that emails a red X for a known WARN trains everyone to ignore it. Exit 2 and exit 3 always fail, because those mean the read did not happen. `break-build` opts back in. |
| D-06 | The action never prints the report it was given. | Decided 2026-11-03 | Gauge's own rule is that response bodies do not reach the log. The report is public data, but the habit is the point: the renderer writes a file, the syncer reads a file, and stdout carries counts and one-line summaries. |
| D-07 | The change state lives in an HTML comment in the issue body, not in a label, a file or an artifact. | Decided 2026-11-03 | A label system needs a second authority to be cleaned up and an artifact is deleted, so a run whose state lived in either would lose the comparison. The body is the one thing this action already rewrites, and a reader can see it in the raw source. Cost: a human who edits the body can destroy the state, and the next run then re-baselines rather than guessing. |
| D-08 | `gauge-ref` pinning is a supply-chain control, not a sandbox. | Decided 2026-11-03 | This action compiles and runs Go code from another repository. Pinning makes that code auditable and the bump reviewable; it does not confine it. `SECURITY.md` states the boundary, and the checkout runs with `persist-credentials: false`. |
| D-09 | `action.yml` is guarded by a stdlib text scanner, not a YAML parse. | Decided 2026-11-03 | The two rules worth enforcing (no expression inside a `run:` block, every third-party step pinned by full sha) are properties of the text, and enforcing them must run on the runner's own python3. Adding PyYAML to CI to prove a dependency-free action parses would contradict D-02 to solve a problem `scripts/check_action.py` does not have. |

## 4. Current focus

Phase 1 is done in code and has been executed on a runner. Phase 2 is the public shape of the
repository, and Phase 3 is the part that cannot be written at a desk: pointing this at a
real account, on a real schedule, and reading what the issue says.

1.8 closed on 2026-11-04, so the yaml is no longer an unexecuted claim: the composite action
was run by `self-check / action`, Gauge was fetched and built at the pinned sha, the audit step
reached live testnet with `example/gauge.toml` and exited 1, the renderer wrote a 2 573-character
body, and the syncer stopped at the dry run it was told to stop at. The write came from the other
caller of the same code, also on 2026-11-04: `watch / audit` opened issue #6 and a second dispatch
found it by its state marker and left it byte-identical, so the sentence a consumer would most
want, "it keeps the tracking issue current", has now been exercised twice on a runner, once in
each direction. G3 and G4 are the rows that record it.

G1 closed the same day, on the push that pull request #1's merge produced: `ci / python`
126445751941 on `db8a5ed`, `ubuntu-26.04`, CPython 3.11.18, nine steps in order. It is the first
evidence in this repository about the repository rather than about a laptop. It is also a rule
now: 2.7 closed on 2026-11-04 when ruleset 26515104 went active on `main` with both checks
required and a direct push was observed refused, which is the difference between a green that
means something and a green that means the maintainer felt like running it.

Phase 2 is at 11 of 13 and its two open rows are not work at a desk: 2.9 is a documentation
site deferred on purpose, and 2.10 is a tag whose blocker cleared on 2026-11-04, when a run of
this action opened an issue. G2 closed the same day, so the public shape is done and what is
left is the kind of work that needs a schedule and a reader.

Phase 3 started where Phase 1 stopped. `.github/workflows/watch.yml` is the same call
`self-check.yml` makes, with two edits that are one change: `dry-run` off and `issues: write` in
place of `issues: read`. It audits the two testnet accounts `tests/fixtures/` holds real reports
for, plus one valid address the endpoint does not have, and the expectation written before the run
was one high `acct-missing`. The first dispatch, at `f19f12c` on 2026-11-04, got that and nothing
else: `gauge exited 1 after writing 4646 bytes of report`, `1 open, 1 high, 0 warn, 0 accepted`,
`sync_issue: opened issue #6 as the baseline`, and the job green. A second dispatch three and
a half minutes later (job 126477058944) found the issue by its state marker, rendered 2291
characters of "no change since the previous run" and left the body byte-identical.

What is left in Phase 3 is not plumbing. 3.3 is a mainnet read the owner has to make, and 3.5 is
the wave-shaped backlog, which stays unpublished until the application is approved. 3.4 is
closed: a second repository consumes the action by sha, and its three runs are recorded in that
row. 3.6 and 3.7
are the wording bugs that reading found, and both are
closed: the summary line used to say "across 3 accounts read" for a set in which one account was
never read, and it now says "across 2 accounts read of 3 asked about"; the heading one section
lower was "## Accounts read" above a row reading "(not read)", and it is now
"## Accounts asked about", the same noun the sentence uses for that set. They are separate diffs
because the section name is a body string keyed on by five test split sites and described in
`ARCHITECTURE.md` section 2's field table.

Reading issue #6 after 3.7 closed shows what leaving the body alone costs. Its first line still
says "across 3 accounts read" and its account section is still titled `## Accounts read` over a row
that says `(not read)`, because a run that finds the same posture does not rewrite a body and the
posture on that issue has not moved since the baseline was written. Both fixes are in the renderer
and neither is on the one artifact a reader opens first, so 3.8 records the gap. The switch it needs
has been in the action since `action.yml` was written: `update-on-no-change` rewrites the body with
no comment, `tests/test_sync_issue.py:383` covers it, and nothing in a dispatch could reach it
because `watch.yml` held it at `"false"`. 3.8 adds that caller and the two dispatches ran the same
day, so issue #6 now opens with "1 finding open (1 high, 0 warn) across 2 accounts read of 3 asked
about" above a section titled `## Accounts asked about`, on the state marker the run that opened it
wrote and with no comment posted. The row stays unticked for one clause of its own done-when: only a
`scheduled` run shows what an event with no `inputs` context does with the new fallback, and that is
Tuesday 2026-11-10 at 05:23 UTC.

1.9's gap was not a missing behaviour but a missing failure. `ARCHITECTURE.md` section 7 has
always said an unreadable endpoint leaves no report, no body and no issue update, and
`ci / python` can only test each script on its own side of the `$RUNNER_TEMP` handoff, so the
claim was one a reader had to take on trust. The probe in the task row is now a second job in
`self-check.yml`, which means every pull request pays about a minute of Go build to make that
row checkable, and the assertions are written so a run that dies before the audit step reads
as a failure rather than as a pass. It has been read once, in the pull request that added it:
job 127116146401 took 22 seconds, refused to render an empty report and skipped the write
step, and issue #6 did not move.

3.4 closed on somebody else's repository, which is the difference between this row and every run
before it. `posture-sec/stellar-account-fixtures` carries `.github/workflows/posture-watch.yml`,
whose `uses:` line is this repository at `deaf7dcc`, a sha rather than the dogfood's `uses: ./`,
and whose `config:` is that repository's own `.posture/gauge.toml`, holding the one testnet account
its corpus captures. Three dispatches of it from that repository's `main`: a dry run that printed
`gauge exited 0 after writing 2346 bytes of report` and `0 open, 0 high, 0 warn, 0 accepted`, a
write that opened its issue #29 as the baseline, and a third that found the issue by its state
marker and left it alone with `changed=false`. So two shapes this action had never produced on a
runner arrived together: a clean report, whose every findings section says `None.`, and an exit 0
from Gauge, where every run here and there before it exited 1 on the `acct-missing` the dogfood
policy declares on purpose. It is also the first policy file the action has read that this
repository did not write, and the first in a subdirectory. G5 does not move with any of this: the
same maintainer wrote both callers, so what doubled is the code path, not the number of readers.

The ordering that held this repository back was G3, then G4, and both are now closed. A green
hosted CI run told us the code builds and the suite passes on somebody else's machine; an
end-to-end run had to tell us whether the issue body is worth reading, and issue #6 does: one
high finding, three account rows whose every number traces to a report field, and a second run
that recognised its own output. What is left is a claim about what this catches that comes from
this repository rather than from Gauge's fixtures. Gauge's own signer
and threshold rules are still unbuilt (its task 3.1, blocked behind its 0.7). Its 3.5
identity rules merged on 2026-11-03, after every fixture and example file here was captured
or written against `da65673`, which does not carry them; bumping `gauge-ref` to a commit
that does adds `id-no-home-domain`, `id-toml-unreachable` and `id-toml-account-unlisted` to
what an issue can say. So a watch run at the pinned sha reports a missing account, a network
mismatch and two flag rules, and nothing about signers, thresholds or identity. That is
stated in `README.md` rather than worked around, and
it is why this repository's value right now is the plumbing rather than the findings.

## 5. Tasks

### Phase 0: Ground work

- [x] **0.1** Choose the shape. Done-when: the repository holds no CLI of its own and the
  deliverable is `action.yml`. Decided 2026-11-03: a composite action, because the whole
  point is that it runs from a schedule in the consumer's own repository, where a CLI
  would have to be installed and re-run by hand.
- [x] **0.2** D-01, the required pinned sha. Written into `action.yml` as `gauge-ref`,
  `required: true` with no default, and enforced by `validate_inputs.py` before anything
  is fetched.
- [x] **0.3** D-02, stdlib only. `requirements-dev.txt` pins two dev tools and no runtime
  package; `pyproject.toml` builds nothing.
- [x] **0.4** D-03, testnet only. Every file in `tests/fixtures/` is a testnet read or is
  labeled as derived from one.
- [x] **0.5** D-04, no shared code. The two guard scripts and their self-test are copies
  from `posture-sec/stellar-account-fixtures`, and the copies came with their tests.
- [x] **0.6** D-05, D-06 and D-07 written down before the code that depends on them.
- [x] **0.7** Adopt the roadmap gate. `scripts/check_roadmap_touched.sh` and
  `scripts/roadmap_progress.py` are in place and `.github/workflows/roadmap-check.yml`
  runs both on every pull request.

### Phase 1: The action

- [x] **1.1** `validate_inputs.py`. Refuses a `gauge-ref` that is not a full sha, a
  `gauge-repo` that is not `owner/name`, a `fail-on` that is neither `high` nor `warn`, an
  empty or over-long or control-bearing label or title, and a config path that is
  absolute, climbs with `..`, missing, not a regular file, over 1 MiB, not valid TOML, has
  no `version = 1`, no network, no endpoint, a non-https endpoint, no accounts, an account
  that is not a table, or an address that is `M...`, `C...`, seed-shaped, malformed or
  checksum-bad. Reports every problem in one pass rather than the first one. Exit 0 or 2.
  41 tests, run locally 2026-11-03.
- [x] **1.2** `render_report.py`. Reads one Gauge JSON report, refuses anything it cannot
  account for (a missing top-level field, an unknown severity, a finding with no 64-hex
  fingerprint, an exit code that disagrees with the run's), and writes an issue body with
  a summary line, New / Resolved / Current / Accepted / Accounts tables, the limits
  footer, and a base64url state marker. Escapes markdown and breaks mentions, because
  Gauge's report path controls characters but does not escape markup and a `home_domain`
  is attacker-chosen. Exit 0 or 2. 42 tests, run locally 2026-11-03.
- [x] **1.3** `sync_issue.py`. `find` locates the one open issue carrying the marker, or an
  open issue with the configured title to adopt, and hands the current body to the
  renderer. `write` creates the baseline, or updates the body and leaves a comment when
  the finding list moved, and touches nothing when it did not. HTTPS only, no redirects,
  a 30 s timeout, three bounded retries honoring `Retry-After` with a 60 s ceiling, a
  65 536-character body limit with row trimming that says how many rows it dropped, a
  token that comes only from the environment, and redaction on every failure message.
  Exit 0, 2 or 3. 46 tests including a loopback server for the wire behaviour, run
  locally 2026-11-03.
- [x] **1.4** `action.yml`. Ten inputs, four outputs, ten steps, every input arriving as
  an environment variable so nothing is interpolated into a shell command. Exit-code
  mapping per D-05: 0 passes, 1 passes unless `break-build`, 2 and 3 always fail, and an
  unrecognised exit fails as 2. `scripts/check_action.py` (1.11) holds those two rules, and
  it parses with `yaml.safe_load` locally as a second opinion, not as the check.
- [x] **1.5** Fixtures with provenance. Four real testnet reports captured from Gauge built
  at `da656733fff839d5cf20f795460f4365a7254257`, two derived ones labeled derived, and
  `tests/fixtures/README.md` naming the ledger, the exit code and what each exercises. A
  test asserts the table lists every file in the directory and that no fixture contains a
  seed-shaped string.
- [x] **1.6** The state marker contract in one place. `test_marker_contract` pins that
  `sync_issue.MARKER_PREFIX` and `render_report.MARKER_PREFIX` are the same string and
  that a rendered body decodes back through it.
- [x] **1.7** Change detection budget. The marker carries up to 200 findings or 20 000
  characters, whichever comes first, and when anything is left out the body says so in
  bold with both numbers rather than reporting a clean comparison.
- [x] **1.8** Hosted validation of `action.yml`. Observed on GitHub 2026-11-04: job
  `self-check / action` 126439899851 ran this repository's own `self-check.yml` on commit
  `b107b0f` for pull request #1, and the step graph reached the audit step with the pinned sha:
  `actions/checkout` fetched Gauge at `da656733fff839d5cf20f795460f4365a7254257`, `setup-go`
  resolved 1.27.3 from that tree's `go.mod`, the build produced the binary, and the log line
  reads `gauge exited 1 after writing 4646 bytes of report`. The render step then wrote
  2 573 characters and reported `1 open, 1 high, 0 warn, 0 accepted`, and the sync step said
  `dry run, would open an issue titled 'Account posture watch'`. The same sequence ran on the
  first commit of that pull request (job 126438382017) with byte-identical counts, which is what
  a deterministic render over a testnet account that has not moved should look like. What this
  does not do is G3: `dry-run: true` means no issue was created, here or on a runner, so the
  end-to-end write has never happened anywhere.
- [x] **1.9** Refuse a policy whose accounts no consumer will read. Done-when: a policy file
  whose endpoint cannot be read at all produces the exit 3 path and no issue update, observed
  on a runner. Half of this was already read: the first account in `example/gauge.toml` is a
  valid checksummed address the endpoint does not have, and the runner reported it as one high
  finding with exit 1 and still wrote the body, which is the correct outcome for an absence.
  The other half is the one no desk can produce, because it needs a fetch that genuinely fails
  rather than a server that answers with nothing. It is now built rather than described.
  `tests/fixtures/policy-unreachable-endpoint.toml` points at `https://horizon.invalid`, the
  top-level domain RFC 6761 reserves and no resolver answers for, and `self-check.yml` gained a
  second job, `self-check / exit-3 probe`, which runs the action against it with
  `continue-on-error: true` and then requires four things: the step failed, `report.json`
  exists, `report.json` is empty, and `issue-body.md` does not exist. The second claim is what
  keeps the probe honest, because a policy `validate_inputs.py` refuses dies before the audit
  step and writes no report either, which is the same green-looking shape for the wrong reason.
  So that fixture has two shape tests in `tests/test_validate_inputs.py`, one that it passes
  every check before the network and one that its endpoint is the reserved domain, the job's
  own assertions are written out in `CONTRIBUTING.md`, and `ARCHITECTURE.md` section 7 says
  which of its rows a job now proves rather than claims. Closed on 2026-11-05 by the probe's
  own job in the pull request that added it, `self-check / exit-3 probe` 127116146401:
  `gauge exited 3 after writing 0 bytes of report`, then `sync_issue: found issue to update
  (#6)` from the read-only find step, then `render_report: refused: report
  /home/runner/work/_temp/report.json: is empty` and exit code 2, then
  `probe.write; outcome=skipped`. The failed step still exported its outputs, so the assertion
  read `OUTCOME: failure` and `GAUGE_EXIT: 3`, printed `exit-3 probe: no report, no body, no
  issue touched, as section 7 claims` and left the job green. Gauge's stderr went up as the
  `gauge-diagnostics` artifact (278 bytes, ID 13397322544), and issue #6 still reads
  `updated_at` 2026-11-04T11:28:15Z with 0 comments, which is the no-update half proven by a
  skipped step rather than by a dry-run flag. A desk run of the same build at the same sha
  gives the three facts the job asks for: exit 3, zero bytes on stdout, and a stderr naming
  `lookup horizon.invalid: no such host`.
- [x] **1.10** Document the version contract. `ARCHITECTURE.md` section 2 lists the
  load-bearing report fields path by path, names which of them the renderer refuses on and
  which it renders as absent, and states the consequence a Gauge change has to live with: a
  rename of a load-bearing key makes this action exit 2 loudly rather than drop findings
  silently. Written 2026-11-03 against the four fields `read_report` and
  `collect_findings` actually check, so the list is the code's and not a wish.
- [x] **1.11** `check_action.py`: the two `action.yml` rules a reviewer can miss in a diff
  and a runner will not complain about until it has already run with the caller's token.
  Refuses an expression inside a `run:` block, a third-party step not pinned by a full
  40-hex sha, a pin with no comment naming the release it resolved from, a `gauge-ref` that
  is optional or carries a default, an input used in a shell but never declared, an input
  declared and bound nowhere, and an output naming a step id that does not exist. Reports
  every break in one pass, exit 0 or 2, stdlib text scanning per D-09. `ci.yml` runs it
  before the suite. 20 tests, run locally 2026-11-03.

### Phase 2: Public shape

- [x] **2.1** `README.md`, `CONTRIBUTING.md`, `SECURITY.md`. Written 2026-11-03 and re-read
  against the hosted runs on 2026-11-04: the README names the four rules that exist at the
  pinned sha, states that there is no signer or threshold rule yet, and names the three identity
  rules Gauge merged after that sha; `CONTRIBUTING.md` lists each rule with the code that refuses
  it; `SECURITY.md` carries a four-surface threat model (input to shell, fetched code,
  chain-authored markup, the token) and a limits section that says what has been run where.
- [x] **2.2** `.github/CODEOWNERS`, a pull request template and two issue templates.
  CODEOWNERS names `@bolabeatz` and lists the contracts and the guards; the PR template asks
  for real output and has a checkbox for the report contract; `bug.yml` asks for the
  `gauge-ref` because findings come from that code, and `config.yml` routes a wrong answer to
  Gauge rather than here.
- [x] **2.3** `ci.yml`: `check_action.py`, unittest over `tests`, `ruff check`,
  `ruff format --check`, `mypy`, with the two dev tools pinned in `requirements-dev.txt` and
  both actions pinned by sha. Job name `ci / python`, Python 3.11 as the floor. The suite runs
  locally on 3.11.16 and 3.12.3; `ruff` and `mypy` at their pins run locally from a venv whose
  interpreter is 3.14.0, which is the one place this repository's local evidence is not on the
  CI floor. Executed by a runner since 2026-11-04: job `ci / python` 126439899511 on
  `ubuntu-26.04` set up CPython 3.11.17 and passed every step in order, with the log carrying
  `check_action: action.yml holds its rules`, `Ran 167 tests in 5.837s`, `OK`,
  `All checks passed!`, `10 files already formatted` and
  `Success: no issues found in 10 source files`.
- [x] **2.4** `roadmap-check.yml` running both guard scripts. Job name
  `roadmap-check / gate`, `fetch-depth: 0` so every branch ref including the base is in the
  repository before the gate reads it, and the copied guards are themselves tested by
  `tests/test_roadmap_gate.py` (18 cases) inside `ci / python`, so the gate that is required to
  merge is a gate with tests. Its first hosted run caught a fault in the workflow itself: the
  step also ran `git fetch origin "$GITHUB_BASE_REF"`, which exited 128 with "could not read
  Username" because `persist-credentials: false` had already removed the credential the fetch
  needed. Fixed in `b107b0f` by deleting the redundant fetch rather than by re-enabling
  credentials; the gate passed on the same commit afterwards (run 41789685726), which is the
  evidence this task wanted and the reason a guard that needs network is a guard that should
  not.
- [x] **2.5** `ARCHITECTURE.md`: the four scripts, the seam the tests drive, the marker, the
  failure modes, what is deliberately absent, and section 2's version contract (1.10).
- [x] **2.6** Repository profile: description, topics, homepage, and the org profile row.
  Done-when: `gh repo view` shows all four and `posture-sec/.github` names this project. Closed
  2026-11-04. All four are now read back rather than asserted. From the API on `main` at
  `8a308ac`: the description, the description is now
  "Composite GitHub Action: build stellar-gauge at a pinned sha, audit Stellar accounts on a
  schedule, and keep one tracking issue current. Read-only, dry-run by default.", the homepage is
  `https://github.com/posture-sec/stellar-posture-watch#usage`, and ten topics are attached
  (`account-posture`, `audit`, `ci`, `composite-action`, `github-actions`, `horizon`, `python`,
  `security`, `stellar`, `stellar-wave`), and `hasWikiEnabled: false`, as in the three siblings.
  The description that was set when the repository was created ended with "no GitHub runner has
  executed it yet", which stopped being true the same morning. The fourth was never a change to
  this tree: pull request #1 in `posture-sec/.github` added this project's row to the org profile
  page and merged as `06d2db5` at 08:07:19Z, and `raw.githubusercontent.com/.../profile/README.md`
  answers 200 and names `stellar-posture-watch` four times. It waited deliberately, because a
  profile that names a repository nobody outside the org can open is a broken link on a page whose
  whole job is pointing at things.
- [x] **2.7** `main` protection. Done-when: a ruleset requires a pull request plus both checks,
  and a direct push is observed refused. Closed 2026-11-04. The first attempt returned
  `403 Upgrade to GitHub Pro or make this repository public to enable this feature`, so the
  repository was made public first: the tracked tree at `f1dad23` was re-grepped for
  seed-shaped strings, `ghp_` tokens, `github_pat_` tokens and private-key headers and matched
  none of the 38 files, and `PATCH /repos/posture-sec/stellar-posture-watch` with
  `private=false` then answered
  `visibility: public`, which an unauthenticated `GET` and a `200` on the raw README confirmed.
  Ruleset 26515104 `protect main` was created next: `target: branch`, `enforcement: active`,
  `~DEFAULT_BRANCH`, with `deletion`, `non_fast_forward`, `pull_request` (zero approving reviews
  required, stale reviews dismissed on push, resolved threads required, squash and merge allowed)
  and `required_status_checks` naming `ci / python` and `roadmap-check / gate` with the strict
  policy on. It is the corpus's ruleset copied rather than re-argued, which is what D-04 means
  for a GitHub setting. `GET /rulesets?for_ref=refs/heads/main` returns it, so it binds `main`.
  The refusal was then observed: a direct push of one commit to `refs/heads/main` came back
  `remote: - Changes must be made through a pull request.`, `remote: - 2 of 2 required status
  checks are expected.`, `! [remote rejected] HEAD -> main (push declined due to repository rule
  violations)`. A throwaway ruleset on a probe branch (26515121, deleted with the branch
  afterwards) produced the same refusal first, so the `main` attempt was made knowing what a
  bound rule prints; nothing landed on `main` outside a pull request in either case. Note what
  this does not add: no CODEOWNERS approval is required, because
  `.github/CODEOWNERS` names one owner and `require_code_owner_review` is off, so the machine
  now enforces "through a pull request with these two checks green", which is the whole claim.
- [x] **2.8** An OSSF Scorecard run and the README badge. Done-when: a scheduled
  `scorecard-action` job publishes a result for this repository and the badge renders. Closed
  2026-11-04. `.github/workflows/scorecard.yml` is pinned to the same four commits the siblings
  run, `ossf/scorecard-action` at `fa7117db` v2.5.0 included, on push to `main` plus
  `cron: '30 1 * * 6'`, with `publish_results: true`, and is byte-identical to the corpus's
  workflow from `name:` down. Its first run was not scheduled: the merge of pull request #3
  pushed `8a308ac` to `main` at 08:00:43Z and the `push` trigger fired, `scorecard / analysis`
  job 126460914087 in run 41796242453, success. The published result was read from
  `api.scorecard.dev` for this repository: it answers 200 with `date: 2026-11-04T08:00:51Z`,
  `commit: 8a308ac9a21982165b8ee1f967845684e87686f8` and **5.2** over 18 checks, and the badge
  URL was fetched rather than assumed: `api.scorecard.dev/.../badge` redirects to an SVG
  containing `5.2`. `README.md` carries it. What the score does not measure is stated beside it
  rather than here: `Branch-Protection` is 4 because no approver is required, which is 2.7's own
  stated limit arriving as a number, and `Fuzzing` is 0 because `render_report.py` parses a
  report whose contents came off the chain and nothing hammers it.
- [ ] **2.9** A documentation site. Deferred deliberately: the two siblings have one each
  and this repository's surface is one yaml file plus a worked example. Revisit after G3.
- [ ] **2.10** A first release. Done-when: `v0.1.0` is tagged and `action.yml` is consumed
  by ref from another repository. The reason this row held is no longer true: it said the action
  had run only in dry run, so the issue it maintains had never been produced by it. `watch /
  audit` job 126475427542 opened issue #6 from a live testnet read on 2026-11-04, and
  126477058944 and 126543269815 left it alone while 126544009391 rewrote it, which is G3 and G4
  closed. What still holds the tag is the owner's judgement about what a release commits a
  consumer to, and the second half of the done-when is now satisfied: `stellar-account-fixtures`
  pins this repository by sha at `deaf7dcc` and a runner has fetched and executed it there, which
  is 3.4. The tag is what is left, and it is the owner's to decide.
- [x] **2.11** `example/`. `example/gauge.toml` is a testnet policy for three accounts: a
  declared five-of-six signer set (five keys at weight 1 plus the master at weight 0) at
  thresholds 3/3/3 with every flag off, an issuer with `auth_required`, `auth_revocable` and
  `clawback` set and a `home_domain`, and an address that is valid and checksum-correct but is
  not on the endpoint, so a real run has something to say. Its header names the ledger its
  expectations were read at and states that nothing evaluates the signer and threshold
  declarations at this commit. `validate_inputs.py` exits 0 on it. `example/workflow.yml` binds
  all ten inputs with a comment on each and reads the four outputs through `env:` in a final
  step. Both parse and validate locally 2026-11-03; 3.1 and 3.2 are the parts that make the
  policy file one a schedule runs.
- [x] **2.12** `.github/workflows/self-check.yml`. The repository consumes itself: `uses: ./` with
  the pinned `gauge-ref`, `example/gauge.toml`, `fail-on: warn` and `dry-run: true`, so a
  `pull_request` run executes the composite steps instead of only parsing their yaml. It is
  deliberately not a required check, because a testnet outage must not block a merge. Run by a
  runner since 2026-11-04 on both commits of pull request #1, with the step evidence recorded
  under 1.8; the file also parses with `yaml.safe_load` locally. This task exists because
  `check_action.py` guards `action.yml` and no workflow file.
- [x] **2.13** `.gitignore` and `docs/WAVE_SUBMISSION.md`. The ignore file names the caches the
  checks write, the five run artifacts a manual pipeline run leaves in the working directory
  (`report.json`, `issue-body.md`, `summary.json`, `previous-body.md`, `posture-report.json`),
  the `.posture-watch/` Gauge checkout and the built binary, the Scorecard SARIF, `/files/` and
  anything shaped like a credential file. The submission packet points at
  Gauge's for the program facts, states that this repository is not applying, names the reasons,
  and lists the gates that would have to close first. Written locally 2026-11-03.

### Phase 3: Real use

- [x] **3.1** G3, the first end-to-end run. Done-when: a scheduled workflow in this
  repository audits the two testnet accounts Gauge already keeps fixtures for, and the
  issue it opens or updates is read by a human and matches the report it came from.
  `.github/workflows/watch.yml` lands the schedule (Tuesday 05:23 UTC, `workflow_dispatch`
  beside it, `contents: read` plus `issues: write` and nothing else) with `dry-run: "false"`, so
  the delta against `self-check.yml` is the flag and the permission that makes it mean something.
  Closed on 2026-11-04 by two dispatches of it at `f19f12c`. Run 1 (job 126475427542,
  08:36:02Z) printed `gauge exited 1 after writing 4646 bytes of report`, then `1 open, 1 high,
  0 warn, 0 accepted`, then `sync_issue: opened issue #6 as the baseline`, and finished with
  `gauge exited 1, tracking issue 6, changed=true` on a green job. Run 2 (job 126477058944,
  08:39:51Z) printed `sync_issue: found issue to update (#6)`, rendered 2291 characters of no
  change, said `issue #6 needs no change, left alone` and reported `changed=false`; the issue
  read back afterwards still had `updated_at` 08:36:02Z and a byte-identical body. The human
  half of the done-when is the G4 row.
- [x] **3.2** The dogfood policy file. Done-when: `example/gauge.toml` is the file 3.1
  actually runs, not a copy of Gauge's example with the addresses swapped. `watch.yml` points
  `config:` at it, so this is the file the schedule reads and not a stand-in. Closed with 3.1 on
  2026-11-04: both dispatches audited this policy, and the one finding in issue #6 is the absence
  its own header names.
- [ ] **3.3** A mainnet run by the owner. Done-when: one scheduled mainnet audit is
  recorded in `docs/` with its ledger, date and exit code, labeled as the operator's run
  rather than this repository's test. Blocked by D-03, which keeps this repository's own
  checks on testnet; a mainnet run is allowed, it is just not a test.
- [x] **3.4** A second consumer. Done-when: some repository other than this one uses the
  action, or the row in `docs/WAVE_SUBMISSION.md` says nobody does yet. Closed 2026-11-05 by the
  first alternative, so the second half of the done-when did not become necessary: it was the
  fallback, not a requirement. `posture-sec/stellar-account-fixtures` now carries
  `.github/workflows/posture-watch.yml`, and its first line of substance is the one this row
  waits on, `uses: posture-sec/stellar-posture-watch@deaf7dcc482525c4583660643cf8251146afb466`,
  which is this repository's `main` head consumed by sha rather than the local `uses: ./` the
  dogfood uses. The runner agreed it had to fetch that: job 127128709833 printed `Download action
  repository 'posture-sec/stellar-posture-watch@deaf7dcc...' (SHA:deaf7dcc...)` before running the
  step graph. It audits that repository's own `.posture/gauge.toml`, a file in a subdirectory
  rather than `example/`, holding the one testnet account its corpus captures, so this is the
  first caller to read a policy this repository did not write. Three dispatches of it from that
  repository's `main` at `71dfffc`, which merged at 08:08:42Z: job 127127136762 at 08:09:18Z with
  `dry_run` ticked printed `gauge exited 0 after writing 2346 bytes of report`, then `render_report:
  wrote ... (1313 characters); 0 open, 0 high, 0 warn, 0 accepted`, then `sync_issue: dry run,
  would open an issue titled 'Fixture account drift'`; job 127127900716 at 08:11:19Z, flag off,
  printed `sync_issue: opened issue #29 as the baseline` and `gauge exited 0, tracking issue 29,
  changed=true`; job 127128709833 at 08:13:13Z found that issue by its state marker, rendered 1312
  characters of `no change since the previous run`, said `issue #29 needs no change, left alone`
  and reported `changed=false`. Issue #29 reads back through the API at 1313 characters under the
  label `fixture-drift`, `updated_at` equal to `created_at` at 08:11:50Z and 0 comments. Two facts
  here are new to this action rather than merely new copies of the dogfood: it is the first hosted
  render of a clean report, a body whose every findings section says `None.`, and the first
  `gauge exited 0` observed on a runner, since every run before it on either repository exited 1
  on the `acct-missing` the dogfood policy declares on purpose. What this does not close is G5:
  the same maintainer wrote both callers, so the reading is still one person's, and
  `docs/WAVE_SUBMISSION.md` says so in the rows it owed an update.
- [ ] **3.5** Wave-shaped backlog. Done-when: the tasks a stranger could take have tiers
  and acceptance criteria in their issue bodies, and none of them is published before the
  organization's application is approved.
- [x] **3.6** The summary line counts an account that was not read. Found while closing G4 on
  2026-11-04: issue #6 opens with "1 finding open (1 high, 0 warn) across 3 accounts read", while
  its own table marks one of those three `(not read)` and `not found on this endpoint`. The number
  is right and the noun is wrong: two accounts were read and three were asked about. Closed
  2026-11-04. `status_line` now takes the read count and the asked-about count as separate
  arguments, and the call site derives the first from `account_status`, the same function the
  table's `Read` column already uses, so the sentence and the row it summarises cannot drift apart
  again. Rendered from `tests/fixtures/report-findings.json` the first line reads "across 1 account
  read of 2 asked about."; from `report-network-mismatch.json`, where the single account was
  skipped for a network mismatch, "across 0 accounts read of 1 asked about."; a report whose every
  account was read keeps the old shape and says "across 1 account read." with no denominator, which
  is why the change is invisible on the clean fixtures. Four cases in `TestSummaryAccountCounts`
  cover the three branches and cross-check the sentence against the table's own rows, and the
  suite is 171 on this branch where it was 167. The done-when asked that the change "leaves the
  state marker alone": it does, and that is now a test rather than an expectation, because a body
  whose first line is rewritten back to the old sentence still decodes to the same marker and
  renders `changed=false`. Two notes on what this does not do. It does not rewrite issue #6: the
  posture there has not moved, `sync_issue.py:287` leaves an unchanged issue alone, so the old
  sentence stays in the live body until a run reports a change or `update-on-no-change` is flipped,
  which is D-07 working as designed rather than a defect in this fix, and on this pull request
  the design was read on a runner rather than only asserted in a test: `self-check / action` job
  126493053801 decoded the marker of the live issue #6, which the *old* renderer wrote, printed
  `render_report: wrote /home/runner/work/_temp/issue-body.md (2308 characters); no change since
  the previous run (1 open, 1 high, 0 warn, 0 accepted)` and then `sync_issue: issue #6 needs no
  change, left alone`, on the same 4646-byte report. 2308 is 2291 plus 17, and 17 is exactly the
  width of " of 3 asked about", so the second number is the sentence and nothing else moved. And there is no `-update`
  here to regenerate goldens with; the task was written in Go vocabulary, and the only file in this
  repository that quotes the sentence is `README.md`'s schematic, which was re-rendered from the
  fixture and pasted rather than retyped.
- [x] **3.7** The heading below the summary repeats the noun error 3.6 fixed. Found while closing
  3.6 on 2026-11-04: `## Accounts read` sits directly above a table whose last row says
  `(not read)`, so the section that 3.6 made honest in the sentence is wrong again in its title.
  Closed 2026-11-04. The section is the set the summary's denominator names, so it takes that
  denominator's word: the emitted heading is now `## Accounts asked about`, at
  `scripts/render_report.py:367`, and the `Read` column written by `account_status` is the only
  place left that says what happened to a given account. Rendered from
  `tests/fixtures/report-findings.json` the section reads "## Accounts asked about" over two
  rows, one ending `| read |` and one ending `| not found on this endpoint |`, which is the
  contradiction the old title used to set up. Four cases in `TestAccountsHeading`: the exact
  heading over five fixtures with the row count each one owes (2, 2, 1, 1, 1), that same
  invariant stated as a rule the renderer cannot break, namely that an account heading may not
  claim read while any row under it does not end `| read |`, checked against every
  `report-*.json` fixture, that the not-read row is still *under* the heading rather than
  dropped to make the title true, and the D-07 check 3.6 added for a sentence repeated for a
  section name: a body titled `## Accounts read` fed in as `--previous-body` renders
  `no change since the previous run` with the state marker byte-identical to the one in it, so the
  rename reaches a live issue only when posture moves, which is the limitation 3.8 exists for. At the desk the same render is 2428
  characters where the old title gives 2421, and 7 is exactly the width of " asked about", so
  nothing but the heading moved. The five test split sites the done-when names, three in
  `tests/test_render_report.py` and two in `tests/test_sync_issue.py`, moved with the string, as
  did `README.md`'s schematic (whose annotation column stays at 35), the paragraph under it, the
  display-only row of `ARCHITECTURE.md` section 2's field table and the fourth constraint in
  `CONTRIBUTING.md`, which now says a claim about the account set is derived from
  `account_status` wherever it appears in the body. The suite is 175 where it was 171.
  `docs/WAVE_SUBMISSION.md`'s Trivial tier is empty, which is stated there rather than filled
  with invented work. Like 3.6 this does not rewrite issue #6, and this time that was read on a
  runner rather than only asserted in a test: `self-check / action` job 126503764248 at 09:40:12Z
  decoded the state marker the old renderer wrote into the live issue #6, printed `render_report:
  wrote /home/runner/work/_temp/issue-body.md (2315 characters); no change since the previous run
  (1 open, 1 high, 0 warn, 0 accepted)` and then `sync_issue: issue #6 needs no change, left
  alone`, on the same 4646-byte report Gauge exited 1 on. 2315 is 2308 plus the 7 characters of
  " asked about", so the live render moved by the heading and nothing else. The suite passes on a
  runner too: `ci / python` job 126503763136 prints `Ran 175 tests in 6.876s` and `OK`, with `All
  checks passed!` and `10 files already formatted` from `ruff==0.17.3` at 09:39:58Z and `Success:
  no issues found in 10 source files` from `mypy==2.4.0` at 09:39:59Z, so the two lint steps are no
  longer desk-only claims. What the 2315 characters are not is a log line: D-06 keeps the body out
  of the runner's output, `render_report.py:454`'s only stdout line prints a path, a character
  count and the finding counts, so the hosted proof of the new title is that number, the identical
  marker and `sync_issue.py:287` leaving the issue alone.
- [ ] **3.8** A wording fix should reach the published body. Found by reading issue #6 after 3.7
  closed rather than by reading the render: its first line still says "1 finding open (1 high, 0
  warn) across 3 accounts read" and its account section is still titled `## Accounts read` over a
  row reading `(not read)`. Both bugs are fixed in the renderer and neither is fixed on the issue,
  because the posture there has not moved and an unchanged issue is left alone. So what 3.6 and 3.7
  claim is true of a render and not yet of the one artifact a stranger opens first. The behaviour
  already exists and already has a test: the action's `update-on-no-change` maps to
  `--update-on-no-change`, which rewrites the body and posts no comment
  (`tests/test_sync_issue.py:383`, `action.yml:44`), and `sync_issue.py:287` is the branch it
  steps over. What was missing was any way to reach it from a dispatch, since `watch.yml` hard-coded
  it to `"false"`. Done-when: `.github/workflows/watch.yml` takes a `refresh_body` boolean on
  `workflow_dispatch`, a `schedule` event resolves it to false through the fallback in the step's
  expression, and two dispatches from `main` are recorded here. The unticked one is the proof that
  the leave-alone path still holds after the edit, read as the fallback a `schedule` run would take;
  the ticked one is the proof that the body is rewritten, that the state marker survives it
  byte-for-byte, that no comment appears, and that `updated_at` moves. The cost is the one
  `action.yml`'s own description names: after a refresh the header date means "the run that last
  wrote the body" rather than "the run that changed something", which is why it is a switch for a
  fix to the words and not a refresh button. Closed 2026-11-04 with both dispatches read from `main`
  at `2f5e1ec`, the merge of this task's own pull request #10. Unticked first, so the fallback is
  read before the override is used: `watch / audit` job 126543269815 at 11:26:11Z shows the input
  rendered as `update-on-no-change: false`, prints `render_report: wrote
  /home/runner/work/_temp/issue-body.md (2315 characters); no change since the previous run (1 open,
  1 high, 0 warn, 0 accepted)` and then `sync_issue: issue #6 needs no change, left alone`, with
  `gauge exited 1, tracking issue 6, changed=false` on the last step and the issue still at
  `updated_at` 08:36:02Z with no comments. Ticked second: job 126544009391 at 11:27:48Z shows
  `update-on-no-change: true`, prints the same 2315 characters over the same unchanged finding list,
  and then `sync_issue: updated issue #6 without a comment`. Read back from the API afterwards the
  body is 2316 characters, which is the render plus the newline after the marker line, its first line
  is "1 finding open (1 high, 0 warn) across 2 accounts read of 3 asked about, unchanged since the
  previous run.", its account section is titled `## Accounts asked about` over the two accounts the
  endpoint had and the one whose Read cell says `not found on this endpoint`, the state marker is the
  same 400 base64url characters saved from the body before the run byte for byte, the issue has no
  comments, and `updated_at` is 11:28:15Z. So 3.6's sentence and 3.7's heading are published at last,
  written by the code that read the chain at ledger 5553610 rather than typed into the issue. Two of
  the three done-when clauses are therefore read, and the entry stays unticked for the third: a
  `schedule` event has no `inputs` context at all, where the unticked dispatch passed a declared
  boolean set to false, which is not the same object. GitHub's or-operator treats them the same and
  the fallback is what the yaml says, but the run that proves the path consumers get is the Tuesday
  schedule itself, 2026-11-10 at 05:23 UTC, and `watch / audit` on that date closes this row.

### Phase 9: Backlog, not scheduled

- [ ] **9.1** SARIF output so findings land in a repository's security tab. Deferred: it
  needs a severity mapping nobody has agreed on and Gauge has no SARIF writer yet.
- [ ] **9.2** A `pull_request` mode that comments on the diff. Deferred: it needs the
  `break-build` semantics settled on a schedule first.
- [ ] **9.3** Watching more than one policy file. Deferred: one file per issue is the
  contract, and a second file needs a state marker per file.
- [ ] **9.4** Pinning Gauge by release tag once Gauge is tagged. Waiting on Gauge's v0.1.0,
  which does not exist yet; D-01 stays until it does.

## 6. Gates

- [x] **G1** CI green on `main`: `ci / python` passing on the merged commit, and
  `roadmap-check / gate` passing on the pull request whose merge produced it rather than
  locally. Both halves were read on GitHub on 2026-11-04. The pull request half is pull request
  #1, green on its third commit `c76c20e` (`ci / python` 126445174034,
  `roadmap-check / gate` 126445174604, `self-check / action` 126445174797; `b107b0f` was green
  before it with 126439899511 and 126439899465). That pull request merged as `db8a5ed` at
  07:19:54Z, and the push it produced ran `ci / python` on `main`: job 126445751941, `ubuntu-26.04`, CPython 3.11.18,
  all nine steps in order, with the log carrying `check_action: action.yml holds its rules`,
  `Ran 167 tests in 6.301s`, `OK`, `All checks passed!`, `10 files already formatted` and
  `Success: no issues found in 10 source files`. That is the merged-commit half, read rather than
  predicted. Note what this gate is and was not when it closed: `ci / python` passing on `main`
  is an observed fact, and on the day G1 closed nothing yet required it, so the gate records an
  observation rather than a rule. The rule is 2.7, which landed later the same day; what stays
  outside both is `roadmap-check / gate`, which does not run on a push to `main` at all, because
  with no pull request to diff it would say "nothing changed" and pass.
- [x] **G2** `main` protected and the profile filled in (2.6, 2.7). Both halves closed on
  2026-11-04. `main` is bound by ruleset 26515104, which was observed refusing a direct push, and
  the profile's four parts are all read back: description, homepage, ten topics and the row in
  `posture-sec/.github` that names this project, merged there as `06d2db5` at 08:07:19Z. Note the
  asymmetry this gate does not close: the ruleset requires a pull request and both checks, and it
  requires no approving review, so the machine enforces the path and the author is the only
  reader. That is what `Branch-Protection` scoring 4 on the first Scorecard run is measuring.
- [x] **G3** The action has run end to end on a GitHub runner and produced or updated an
  issue that matches its report. Closed 2026-11-04 by the two dispatches of
  `.github/workflows/watch.yml` recorded in 3.1: the first opened issue #6 with `changed=true`,
  the second found that issue by its state marker, said `issue #6 needs no change, left alone` and
  reported `changed=false`, with the body reading back byte-identical and `updated_at` unmoved.
  Both jobs are green while Gauge exits 1, which is D-05 doing its job: a finding belongs in the
  issue, not in the colour of a schedule.
- [x] **G4** The rendered body has been read against the JSON it came from and every
  number in it traced. Closed 2026-11-04 against issue #6. The runner's copy of the report is gone
  by design, because D-06 keeps it out of the log and out of every artifact, so the read pairs the
  hosted body with the same report reproduced on the desk: `git archive` of `da656733` into
  `/tmp`, built, run as `stellar-gauge audit --config example/gauge.toml --format json --fail-on
  warn`, which wrote 4646 bytes at 08:37:59Z, the size the runner had printed 118 seconds earlier.
  Every number in the body has a field. The header's ledger is the envelope `ledger` (5551544
  hosted, 5551567 on the desk read, 23 ledgers apart), its network string is `network`, its
  version is `tool_version`, and `da65673` is the `gauge-ref` input cut to seven. The finding row
  is `rule_id` `acct-missing`, `severity` high, `message` verbatim, and the twelve leading hex of
  `fingerprint` `b03faa6106f2405560196e0cad9e0bb74cab9c08d798877c0d795019bddd43d6`, which is also
  what the state marker decodes to. The account rows are the two snapshots and the absence:
  5551541 with 3/3/3 from `thresholds`, 6 from `len(signers)`, 1 from `len(balances)`, `none` from
  four false flags and `(none)` from an empty `home_domain`; 4699329 with 0/0/0, one signer, one
  balance, the three true flags named and `komunitin.org`; and `(not read)` with a dash in every
  column for the snapshot whose `ledger` is 0. `limits` supplies the footer untouched. Rendering
  the desk report against the hosted body printed the same 2291 characters and the same
  `changed: false` that run 2 printed on the runner, so the two reads agree on the no-change path
  to the byte. The one wording bug this pass found is 3.6.
- [ ] **G5** Someone other than the maintainer has run it, or its absence is stated. 3.4 closed
  on 2026-11-05 and this row did not move with it, because the new consumer is this same author's
  second repository: a second caller written by one maintainer doubles the code path without
  adding a reader. What is still absent is anybody else, and `docs/WAVE_SUBMISSION.md` now says so
  in the rows 3.4 owed it.

## 7. Progress

<!-- PROGRESS:START -->
| Phase | Name | Done | Total | Progress |
|---|---|---|---|---|
| 0 | Ground work | 7 | 7 | 100% |
| 1 | The action | 11 | 11 | 100% |
| 2 | Public shape | 11 | 13 | 85% |
| 3 | Real use | 5 | 8 | 62% |
| 9 (backlog) | Backlog, not scheduled | 0 | 4 | 0% |
| **All phases** | **Readiness total** | **34** | **39** | **87%** |
| Gates | G1 to G5 | 4 | 5 | 80% |
<!-- PROGRESS:END -->

## 8. Changelog

| Date (UTC) | Change | Tasks |
| --- | --- | --- |
| 2026-11-03 | The scaffold lands as one commit: `action.yml` with ten inputs and the exit-code mapping, `validate_inputs.py`, `render_report.py` and `sync_issue.py`, six report fixtures with a provenance table naming which four are real testnet reads, the copied roadmap guards with their self-test, and the README, CONTRIBUTING, SECURITY, ARCHITECTURE and `.github` shape. 129 tests pass locally with the transport seam and a loopback server, `ruff check` and `ruff format --check` are clean on Python 3.12.3, and no runner has executed any of it. Corrected 2026-11-04: this row also said `mypy` was clean, and it was not. Ten type errors were found the next day and are listed in the row below. | 0.1 to 0.7, 1.1 to 1.7, 2.1 to 2.5 |
| 2026-11-04 | Phase 1's two desk tasks close and the example layer lands. 1.10: `ARCHITECTURE.md` section 2 is the version contract, naming the report paths whose absence the renderer refuses and the ones deliberately not load bearing. 1.11: `scripts/check_action.py`, a stdlib text scanner for the two `action.yml` rules a reviewer can miss in a diff (any expression inside a `run:` block, and a third-party step not pinned by a full sha with its release named beside it), also refusing an undeclared input, a declared input bound nowhere, an unpinnable `gauge-ref` and an output naming a step id that does not exist; 20 tests, one of which runs it against the shipped `action.yml`, and `ci.yml` runs it before the suite. 2.11 to 2.13: `example/gauge.toml`, `example/workflow.yml`, `self-check.yml`, `.gitignore` and `docs/WAVE_SUBMISSION.md`. The suite is 167 cases (41 validate, 42 render, 46 sync, 18 roadmap gate, 20 checker) and passes on Python 3.11.16 and 3.12.3; `ruff check`, `ruff format --check` (ruff 0.17.3) and `mypy` 2.4.0 are clean on the ten typed files, run from the pinned tool venv, whose own interpreter is 3.14.0 rather than the CI floor. The ten `mypy` errors the previous row claimed away were a `strkey` shape property that blocked a narrowing, an HTTP-date `Retry-After` branch that returned nothing at all, a test attribute named `responses` colliding with `BaseHTTPRequestHandler`'s own, a sleep stub with the wrong signature, three places where an `assertIsNotNone` did not narrow what followed it, and one attribute the stubs do not carry. One manual composition of the real pipeline against live Horizon testnet, observed 2026-11-03 with its artifacts written outside the tree: `validate_inputs.py` exit 0 on `example/gauge.toml`, `stellar-gauge audit` built at the pinned `da65673` exit 1 with one high `acct-missing` finding, `render_report.py` a 2 573-character body. That is a laptop run and is labeled as one, and 1.8, G1 and G3 stayed open until a runner did it: the row below closes 1.8 and closes neither gate. Gauge merged its 3.5 identity rules on 2026-11-03, three rule ids this pinned sha does not carry, which section 4 now says. | 1.10, 1.11, 2.11 to 2.13 |
| 2026-11-04 | The repository is published and its own pipeline runs on a runner. `posture-sec/stellar-posture-watch` is created with GitHub's own `auto_init` commit, so nothing was hand-committed to `main`; the 38-file tree above goes in as pull request #1 (`5d3dea1`), and the roadmap gate's first hosted run fails on its own second step (`Process completed with exit code 128`, `fatal: could not read Username for 'https://github.com'`): the workflow fetched its base ref with `persist-credentials: false` already in force, and `fetch-depth: 0` had named every branch anyway. Fixed in `b107b0f` by deleting the fetch rather than restoring the credential. Then, on `b107b0f`: `ci / python` 126439899511 passes on CPython 3.11.17 with `check_action: action.yml holds its rules`, `Ran 167 tests in 5.837s`, `All checks passed!`, `10 files already formatted` and `Success: no issues found in 10 source files`; `roadmap-check / gate` 126439899465 passes; and `self-check / action` 126439899851 runs the composite action itself, fetching Gauge at `da656733`, resolving Go 1.27.3 from its `go.mod`, logging `gauge exited 1 after writing 4646 bytes of report`, `render_report: wrote /home/runner/work/_temp/issue-body.md (2573 characters); 1 open, 1 high, 0 warn, 0 accepted` and `sync_issue: dry run, would open an issue titled 'Account posture watch'`. That is 1.8 closed and 2.12's claim replaced by a run; the byte-identical body against the laptop composition of 2026-11-03 is the first evidence that the two paths agree. G3 stays open because nothing was written, and the repository is still private until 2.6 and 2.7 land. | 1.8, 2.4, 2.10, 2.12 |
| 2026-11-04 | G1 closes on a push rather than on a prediction. Pull request #1's third commit `c76c20e`, the document corrections in the row above, goes green on all three jobs (`ci / python` 126445174034, `roadmap-check / gate` 126445174604, `self-check / action` 126445174797) and merges as `db8a5ed` at 07:19:54Z. The push that merge produced ran `ci / python` on `main`: job 126445751941 on `ubuntu-26.04`, setup-python resolving CPython 3.11.18, `check_action: action.yml holds its rules`, `Ran 167 tests in 6.301s`, `OK`, `All checks passed!`, `10 files already formatted`, `Success: no issues found in 10 source files`. That is the merged-commit half the gate's own wording waited on. The self-check job on the same commit is a third run of the same sequence with identical output: `gauge exited 1 after writing 4646 bytes of report`, 2 573 characters, `1 open, 1 high, 0 warn, 0 accepted`, `dry run, would open an issue titled 'Account posture watch'`. Two corrections ride along: the row above named G1 in its task column and did not close it, and the four documents now say what G1 is rather than what it was waiting for. Nothing was required on `main` when this row was written, so it records an observed run; 2.7 is the task that turns it into a rule. | G1, 2.1, 2.13 |
| 2026-11-04 | The last sentence in this repository that said nothing had run on a runner is replaced with the runs. Four documents carried it: `README.md` closed its Checks section with "until those rows are green on GitHub, the sentences above describe a laptop", `CONTRIBUTING.md` opened its Status with "and no hosted run" and added that CI had never executed here, `SECURITY.md` said no runner had executed the code, and `docs/WAVE_SUBMISSION.md` named "Nothing has run" as the second reason not to apply. Each now names the three jobs and what `self-check / action` did, and each still says the write has not happened. Two sentences in `ROADMAP.md` called the end-to-end write a laptop claim, which was never true because no laptop run opened an issue either: the dry run stopped the write everywhere, so both rows now say so plainly. The two 2026-11-04 rows above were also swapped back into date order, because the desk row is where the ten `mypy` errors the 2026-11-03 row defers are listed, and `ROADMAP.md`'s progress table regenerates to 25 of 36 with 1.8 ticked. | 2.1, 2.13 |
| 2026-11-04 | The repository is public and `main` is bound. `POST /repos/.../rulesets` answers `403 Upgrade to GitHub Pro or make this repository public to enable this feature` while the repository is private, which is the first fact of this row: the protection 2.7 asks for is not available to a private repository on this plan. So the tracked tree at `f1dad23` is grepped for seed-shaped strings, `ghp_` and `github_pat_` tokens and private-key headers, none of the 38 files matches, and `PATCH /repos/posture-sec/stellar-posture-watch` with `private=false` makes it public, confirmed by an unauthenticated `GET` and a `200` on the raw README. Ruleset 26515104 `protect main` follows: `deletion`, `non_fast_forward`, `pull_request` and `required_status_checks` naming `ci / python` and `roadmap-check / gate` with the strict policy on and no bypass actors, copied from the corpus's ruleset rather than invented. A direct push of one commit to `main` is then refused with `Changes must be made through a pull request`, `2 of 2 required status checks are expected` and `! [remote rejected] HEAD -> main (push declined due to repository rule violations)`. A throwaway ruleset on a probe branch (26515121) was refused the same way first and both it and its branch are deleted afterwards, so the attempt against `main` was made knowing what a bound rule prints, and nothing landed on `main` outside a pull request. 2.6 moves as far as a desk can: description, homepage and ten topics read back from the API, the wiki still off, and the row naming this project in `posture-sec/.github` left open because a public profile page should not link to what was private that morning. `.github/workflows/scorecard.yml` lands here for 2.8, pinned to the four commits the siblings run, on push to `main` plus Saturday 01:30 UTC, publishing its result; it has not run yet, so no score is quoted in this repository and the badge line waits with it. The “The repository is published” row above says the repository is still private at the end of 2026-11-04, and it was: that is what its own date records. | 2.6 (part), 2.7, 2.8 (part) |
| 2026-11-04 | The public shape finishes and a second opinion arrives. 2.6's last done-when was never a change to this tree: pull request #1 in `posture-sec/.github` added this project's row to the org profile page, merged there as `06d2db5` at 08:07:19Z, and the raw profile README answers 200 naming `stellar-posture-watch` four times. `gh repo view` reads back the other three on `main` at `8a308ac`: the description, `homepageUrl`, ten topics, wiki off. 2.8's first run was not the schedule. The merge of pull request #3 pushed `8a308ac` at 08:00:43Z and the `push` trigger fired: `scorecard / analysis` job 126460914087 in run 41796242453, success, and `api.scorecard.dev` answers 200 with the result dated 08:00:51Z at that commit: **5.2** over 18 checks. `README.md` now carries the badge, which was fetched and checked for the number rather than assumed to render, and the paragraph beside it separates what the score measures from what it does not. `Dangerous-Workflow` and `Token-Permissions` are 10, which are the two checks that matter for an action that fetches and compiles another repository's Go. `Branch-Protection` is 4 for the three warnings 2.7 already states as its own limit, so the ruleset requiring no approver now arrives as a number rather than as a footnote. `Pinned-Dependencies` is 6 for one `pip install -r` line in `ci.yml`, the same reason the corpus scores 6, and `Fuzzing` is 0 for a reason that does measure something here: `render_report.py` parses a report whose contents came off the chain and nothing hammers it. `Maintained`, `Code-Review`, `Contributors`, `CII-Best-Practices`, `Dependency-Update-Tool` and `SAST` are states of a one-maintainer repository created this month, and `Packaging` and `Signed-Releases` are -1 because nothing is published from here at all. None of the eighteen touches the sentence a consumer would most want, which is still G3. Gate G2 closes with the two rows it names. Two smaller corrections ride along: section 1 carried the em dash this repository's own writing rule forbids, and the `ci.yml` header still said nothing required the check on `main`. | 2.6, 2.8, G2 |
| 2026-11-04 | The schedule that writes lands. `.github/workflows/watch.yml` is `self-check.yml`'s call with `dry-run` off: Tuesday 05:23 UTC, `workflow_dispatch` beside it so the first read does not wait for the cron, `contents: read` plus `issues: write` and nothing else, `uses: ./` rather than a sha pin because a local reference resolves from the commit the run is at, `gauge-ref` the same `da656733` and `config` the same `example/gauge.toml` as the dry run. So the delta against `self-check.yml`, which has gone green on all six of its runs here, is the flag, the permission that makes the flag mean something and the token named in the `with:` block rather than defaulted: the accounts, the Gauge sha and the renderer are untouched. The expectation is written down before the run rather than after it: three accounts in the policy, two of them the testnet addresses `tests/fixtures/` holds real reports for and one a valid checksum-correct address the endpoint does not have, so the first issue should carry exactly one high `acct-missing` and exit 1 with the run green. An empty issue would mean the audit step died, not that the accounts are clean, and a second finding would mean the pinned code changed; both readings are G4's job, not this row's, which is why 3.1 and 3.2 gain text and keep their boxes. `self-check` ran again on this pull request (job 126473116440, 08:30:39Z) and its log narrows the expectation without closing it: `gauge exited 1 after writing 4646 bytes of report`, `render_report: wrote /home/runner/work/_temp/issue-body.md (2573 characters); 1 open, 1 high, 0 warn, 0 accepted`, then `sync_issue: dry run, would open an issue titled 'Account posture watch'`. So the number of findings is now an observed hosted fact at this sha against this config; which finding it is stays an inference from the four rules in `da656733` and the three accounts in the policy, because D-06 keeps the report out of the log. Nothing was merged to `main` with the write on, no issue exists yet, and no number in this repository quotes one. | 3.1 (part), 3.2 (part) |
| 2026-11-04 | The write happened, and it was read. `.github/workflows/watch.yml` merged as `f19f12c` and the first `workflow_dispatch` of it, job 126475427542 at 08:36:02Z, built Gauge at `da656733`, read `example/gauge.toml` against live testnet, rendered 2573 characters and opened issue #6 carrying one high `acct-missing` with `changed=true`, on a green job while Gauge exited 1. At 08:39:51Z job 126477058944 found the same issue by its state marker, rendered 2291 characters of no change, said `issue #6 needs no change, left alone` and reported `changed=false`; the body read back byte-identical with `updated_at` still 08:36:02Z. So the sentence four documents carried, that no issue had ever been opened or edited by this action, is now false and each of them names the two runs instead. G4 closed by reproducing the report rather than by trusting the body: the pinned sha went out through `git archive`, built on the desk and run against the same policy at 08:37:59Z, which wrote the same 4646 bytes the runner had printed 118 seconds earlier, and every number in the hosted body maps to a field of it, from the header ledger to the 64-hex fingerprint the state marker decodes to. Rendering that desk report against the hosted body printed the same 2291 characters and the same `changed: false` the runner printed, so the two reads agree to the byte. 3.1 and 3.2 close with the runs, 2.10 loses its blocker, and the reading found one wording bug, 3.6: the summary line says "across 3 accounts read" for a set in which one account was never read. Phase 3 moves to 2 of 6, the readiness total to 30 of 37 and the gate row to 4 of 5. Nothing in `action.yml`, its scripts or its tests changed to produce any of this, which is the point: the second caller of the same code is the whole diff. | 3.1, 3.2, G3, G4 |
| 2026-11-04 | The summary line stops calling an unread account read. 3.6, found while closing G4, is closed here: `status_line` took one number, `len(report["accounts"])`, and called it "read", so a policy naming three accounts of which the endpoint had two printed "across 3 accounts read" above a table whose own last row says `(not read)`. It now takes the read count and the asked-about count, and the first comes from `account_status`, the same function that writes that column, so the sentence and the rows it summarises cannot drift apart again. A render of `tests/fixtures/report-findings.json` says "across 1 account read of 2 asked about." and `report-network-mismatch.json`, whose one account was skipped, says "across 0 accounts read of 1 asked about."; a report whose every account was read keeps the old shape and prints no denominator. Four cases in `TestSummaryAccountCounts` cover those branches, cross-check the line against the table, and prove the state marker byte-for-byte unchanged with `changed=false` when the previous body carries the old wording, which turns D-07's fingerprint keying from a sentence in a doc into a test, and the same pull request's `self-check / action` run read that property against the live body: job 126493053801 decoded the marker the old renderer had written into issue #6, printed 2308 characters of "no change since the previous run" and said `issue #6 needs no change, left alone`, which is 2291 plus the 17 characters of " of 3 asked about" and nothing else. The suite is 171 where it was 167, `check_action` holds its rules and `roadmap_progress.py --check` exits 0 on this branch, and the two lint steps ran locally because `ruff==0.17.3` and `mypy==2.4.0` were installed from `requirements-dev.txt` into a temporary venv outside the repository: `All checks passed!`, `10 files already formatted` after one wrapped test line was reformatted, and `Success: no issues found in 10 source files`. `README.md`'s schematic sentence is a re-render from the fixture rather than a retyping. 3.7 records the same noun error one section lower, in the heading `## Accounts read`, which is a body string keyed on by five test sites and so is not bundled here. Nothing in `action.yml` changed and no JSON field moved, so `ARCHITECTURE.md` section 2's report contract is untouched; issue #6 keeps its old first line until a run finds a change, because an unchanged issue is left alone by design. | 3.6, 3.7 (added) |
| 2026-11-04 | 3.7 closes the noun error 3.6 left one section lower: the account table was titled `## Accounts read` above a row whose own Read cell says `(not read)`. The emitted heading is now `## Accounts asked about`, at `scripts/render_report.py:367`, which is the word the summary's denominator already uses for that same set, so the Read column `account_status` writes is the only place left in the body that says what happened to an account. Four cases in `TestAccountsHeading`: the exact string over five fixtures with the row count each one owes; the same rule stated generally, that an account heading may not claim read while any row under it contradicts that in its Read cell, so the bug cannot come back by editing a title; that the unread row stays in the section rather than being dropped to make the title true; and 3.6's D-07 check run against a section name instead of a sentence, where a body titled the old way and fed in as `--previous-body` renders `no change since the previous run` with a byte-identical state marker. At the desk the same render is 2428 characters where the old title gives 2421, and 7 is exactly the width of " asked about", so nothing else moved; the hosted half agrees, because `self-check / action` job 126503764248 re-rendered the live report at 2315 characters, 2308 plus those same 7, printed `no change since the previous run` and said `issue #6 needs no change, left alone`. The five test split sites the done-when names move with the string, as do `README.md`'s schematic, whose annotation column stays at 35, the paragraph under it, the display-only row of `ARCHITECTURE.md` section 2 and `CONTRIBUTING.md`'s fourth constraint, which now says a claim about the account set is derived from `account_status` wherever it appears in the body. `docs/WAVE_SUBMISSION.md`'s Trivial tier says it is empty rather than inventing a replacement. The suite is 175 where it was 171, and both halves were read on a runner: `ci / python` job 126503763136 prints `Ran 175 tests in 6.876s` and `OK`, `All checks passed!`, `10 files already formatted` after one wrapped comprehension was reformatted, `Success: no issues found in 10 source files`, `check_action: action.yml holds its rules` and `roadmap_progress.py --check` exiting 0 with Phase 3 at 4 of 7 and the readiness total at 32 of 38. One formatting repair came with it: the 3.6 row above had been written across five physical lines, which GitHub renders as four table rows with empty cells, so it is one line again. Nothing in `action.yml` changed and no report field moved, so the body a caller reads keeps its shape with one truer title. | 3.7 |
| 2026-11-04 | 3.8 is found by reading the live issue rather than the render: issue #6 still opens with "1 finding open (1 high, 0 warn) across 3 accounts read" and still titles its account section `## Accounts read` above a row whose own Read cell says `(not read)`, because every run since the baseline has found the same posture and `sync_issue.py:287` leaves an unchanged issue alone. 3.6 and 3.7 are therefore true of a render and not yet of the artifact a reader opens first. The rewrite itself has been in the action since the scaffold: `update-on-no-change` becomes `--update-on-no-change` at `action.yml:193`, `tests/test_sync_issue.py:383` asserts it sends one PATCH and no comment, and `ARCHITECTURE.md` section 4 already names it. What was missing was a caller, since `watch.yml` held the input at `"false"` and its `workflow_dispatch` took no inputs at all. This adds one boolean, `refresh_body`, defaulted off, and the step passes it through a fallback to the string false so a `schedule` event, which resolves `inputs` to nothing, still takes the leave-alone path. No Python changed, so the suite is 175 here exactly as it was on `main` at `7ef214e`, and nothing on this row is claimed as observed on a runner: the done-when asks for two dispatches from `main` after this merges, one unticked and one ticked, and until both are read the statement is that the wiring exists and the wiring is what review can see. `README.md` gains the paragraph on when the override is the right call and what it costs, `CONTRIBUTING.md`'s write-path section names the box for whoever fixes a word next, and `docs/WAVE_SUBMISSION.md` is untouched because this is not work a stranger can take: it writes to this repository's own issue. Adding the task moves Phase 3 to 4 of 8 and the readiness total to 32 of 39, which the regeneration below records. | 3.8 (added) |
| 2026-11-04 | 3.8's two dispatches ran from `main` at `2f5e1ec`, the merge of the pull request that added the input. Unticked first, so the fallback is read before the override is used: `watch / audit` job 126543269815 at 11:26:11Z shows the input rendered as `update-on-no-change: false`, prints `render_report: wrote /home/runner/work/_temp/issue-body.md (2315 characters); no change since the previous run (1 open, 1 high, 0 warn, 0 accepted)` and then `sync_issue: issue #6 needs no change, left alone`, with `gauge exited 1, tracking issue 6, changed=false` on the last step and the issue still at `updated_at` 08:36:02Z and no comments. Ticked second: job 126544009391 at 11:27:48Z shows `update-on-no-change: true`, prints the same 2315 characters over the same unchanged finding list and then `sync_issue: updated issue #6 without a comment`. Read back from the API the body is 2316 characters, which is the render plus the newline after the marker line, its first line is "1 finding open (1 high, 0 warn) across 2 accounts read of 3 asked about, unchanged since the previous run.", its account section is titled `## Accounts asked about` over the two accounts the endpoint had and the one whose Read cell says `not found on this endpoint`, the state marker is the same 400 base64url characters saved from the body before the run byte for byte, and `updated_at` is 11:28:15Z. So 3.6's sentence and 3.7's heading are published at last, written by the code that read the chain at ledger 5553610 rather than typed into the issue. The row stays unticked for its third done-when clause: a `schedule` event has no `inputs` context at all rather than a declared boolean set to false, GitHub's or-operator treats them the same, and only Tuesday 2026-11-10 at 05:23 UTC can show the path a consumer gets, so the entry names the run it waits for instead of reasoning the operator away. No code or test moved here, so the suite is 175 and the table below is the same 32 of 39 as when 3.8 was added. One defect in the previous row came out of reading the file rather than the render: the 3.8 row had been inserted after the blank line that closes the changelog table, which makes it its own one-row table on the rendered page, so it sits with its neighbours again and the section heading keeps its separator. | 3.8 |
| 2026-11-05 | The exit-3 path stops being a claim. 1.9 needs a fetch that genuinely fails, which no desk run can produce, so the repository now produces one on every pull request: `tests/fixtures/policy-unreachable-endpoint.toml` points at `https://horizon.invalid`, the top-level domain RFC 6761 reserves and no resolver answers for, and `self-check.yml` gains a second job, `self-check / exit-3 probe`, that runs the action against the file with `continue-on-error: true` and then requires four things, that the step failed, that `report.json` exists, that it holds zero bytes and that `issue-body.md` was never written. The second claim is what keeps the probe honest: a policy `validate_inputs.py` refuses dies before the audit step and leaves no report either, so the wrong failure would look exactly like the right result. Two shape tests in `tests/test_validate_inputs.py` hold the fixture up, that it passes every check before the network and that its endpoint is the reserved domain, which takes the suite from 175 cases to 177, and `ARCHITECTURE.md` section 7, `CONTRIBUTING.md` and `README.md` name the row a job now proves. A desk run of the pinned build against this fixture gives exit 3, zero bytes of stdout and a stderr naming `lookup horizon.invalid: no such host`, which is the shape the job then requires; the hosted reading is the row below, from the same pull request. | 1.9 (part) |
| 2026-11-05 | 1.9 closes on its own pull request. `self-check / exit-3 probe` job 127116146401 ran the action against `tests/fixtures/policy-unreachable-endpoint.toml` and printed, in order: `gauge exited 3 after writing 0 bytes of report`, `sync_issue: found issue to update (#6)`, `render_report: refused: report /home/runner/work/_temp/report.json: is empty`, `##[error]Process completed with exit code 2`, and then `probe.write; outcome=skipped`. The failed composite step still exported its outputs, so the assertion step read `OUTCOME: failure` and `GAUGE_EXIT: 3`, printed `exit-3 probe: no report, no body, no issue touched, as section 7 claims`, and the job finished green in 22 seconds. Gauge's stderr went up as the `gauge-diagnostics` artifact (278 bytes, ID 13397322544) and issue #6 still reads `updated_at` 2026-11-04T11:28:15Z with 0 comments, which is the no-update half proven by a skipped step rather than by `dry-run`. Phase 1 is 11 of 11 and the total 33 of 39. | 1.9 (done) |
| 2026-11-05 | The sentence in 2.10 that said the action had only ever run in dry run is false and is replaced with the runs. It was written when G3 was still open; `watch / audit` 126475427542 opened issue #6 from a live testnet read on 2026-11-04, 126477058944 and 126543269815 found the finding list unchanged and left it alone, and 126544009391 rewrote it at 11:28:15Z, so G3 and G4 have been closed for a day and the row's own reason for holding the tag went stale with them. What remains is stated as what it is: the tag is the owner's judgement about what a release commits a consumer to, and the done-when's second half is 3.4. No code, test or document other than this file moves, so the suite stays 177 and the table stays 33 of 39 with 4 of 5 gates. It was found by grepping the shipped documents for claims about the write path rather than by a run, which is the cheapest way to catch a row that a later piece of work left behind. | 2.10 (text) |
| 2026-11-05 | 3.4 closes on a runner that is not this repository's. `posture-sec/stellar-account-fixtures` merged pull request #28 as `71dfffc` at 08:08:42Z, and its `.github/workflows/posture-watch.yml` is the first call of this action written outside this repository: `uses: posture-sec/stellar-posture-watch@deaf7dcc482525c4583660643cf8251146afb466`, the pinned form rather than the dogfood's `uses: ./`, against that repository's own `.posture/gauge.toml` and the one testnet account its corpus captures. Job 127127136762 at 08:09:18Z ran it with `dry_run` ticked and printed `gauge exited 0 after writing 2346 bytes of report`, then `render_report: wrote /home/runner/work/_temp/issue-body.md (1313 characters); 0 open, 0 high, 0 warn, 0 accepted`, then `sync_issue: dry run, would open an issue titled 'Fixture account drift'`. Job 127127900716 at 08:11:19Z, flag off, printed `sync_issue: opened issue #29 as the baseline` and `gauge exited 0, tracking issue 29, changed=true`. Job 127128709833 at 08:13:13Z found that issue by its state marker, rendered 1312 characters of `no change since the previous run`, said `issue #29 needs no change, left alone` and reported `changed=false`; the issue reads back through the API at 1313 characters, label `fixture-drift`, `updated_at` equal to `created_at` at 08:11:50Z and 0 comments. So two shapes this action has never produced on a runner arrived in one afternoon: a clean report, whose every findings section says `None.`, and `gauge exited 0`, where every hosted run here and there before this one exited 1 on the `acct-missing` the dogfood policy declares on purpose. The runner also proved the pin before using it, printing `Download action repository 'posture-sec/stellar-posture-watch@deaf7dcc...' (SHA:deaf7dcc...)`, which is the evidence 2.10's second done-when half waits on, so that row loses the clause claiming no other repository pins the ref. G5 does not move with 3.4 and says why in its own text: both callers are the same author, so the code path doubled and the reader count did not. Four stale sentences came out of the same grep that found the 2.10 one. `docs/WAVE_SUBMISSION.md` gave "no consumer but this repository" as a reason not to apply, listed a second consumer as work left for a stranger, said `three of those six` about a checklist whose counts had moved, and closed with `written, tested, documented, and unexecuted`, which stopped being true the morning issue #6 opened; its header also still said five pull requests and one tracking issue where the API now answers twelve merged and two kept. `README.md`'s Usage paragraph names the pinned consumer as the worked example to copy, because until now the only caller in this repository's own docs was the one with no pin. Nothing here changed to produce any of this: no script, no test, no workflow, so the suite stays 177 and the table below regenerates to Phase 3 at 5 of 8 and the readiness total at 34 of 39, with the gates unchanged at 4 of 5. | 3.4, 2.10 (text) |

## 9. Last updated line format

`Last updated: <YYYY-MM-DDTHH:MMZ> (<what moved>)`. The minute is when the edit was
written, not when it merged.
