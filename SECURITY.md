# Security policy

## Reporting a vulnerability

Report it privately through
[a security advisory](https://github.com/posture-sec/stellar-posture-watch/security/advisories/new).
Do not open a public issue for it. This is a one-maintainer project, so expect an
acknowledgement within seven days.

Include the workflow file or the step that shows the problem, the command you ran, the exit
code, and the output. Account ids and ledgers are public ledger state, so leave them in.
**Never paste a secret seed (`S...`) into a report or an issue.** If a seed did reach a file
in this tree, treat the key as compromised, move it, then report; `validate_inputs.py` prints
only the head and tail of a token it refuses, and tells you whether its checksum verifies,
which is what decides whether it has to be treated as live.

## Threat model

There are four things worth breaking here, and the code is arranged around them.

**Shell injection through an input.** A composite action that interpolates `${{ inputs.foo }}`
into a `run:` block hands the caller's repository a shell on the runner, and an attacker who
can open a pull request can set that input. No input in `action.yml` is interpolated into a
command: each arrives as an environment variable and is quoted at the call site.
`validate_inputs.py` is the second line, not the first.

**Code fetched from another repository.** This action checks out Gauge at a sha and compiles
it. That is supply chain, not a sandbox (`ROADMAP.md` D-08): pinning makes the code auditable
and the bump reviewable in a diff, and `persist-credentials: false` on the checkout keeps the
runner's token out of the fetched tree. A finding about what Gauge's code does is Gauge's, and
its own `SECURITY.md` is the place to report it.

**Chain-authored strings reaching markdown.** `home_domain`, a data value, and any message
built from them are chosen by whoever owns the account. GitHub issue bodies are markdown, and
an unescaped value there can render a link a reviewer clicks or notify `@all` on a repository
where nobody expected a ping. `render_report.py` escapes markup and breaks mentions at the
point of writing, and `tests/fixtures/report-hostile-strings.json` is the case that proves it.
Gauge's own JSON path controls characters but deliberately does not escape markup, so this is
the layer that owns it.

**The token.** `sync_issue.py` reads it from the environment only, sends it only to an https
bare host it constructs itself, refuses a redirect rather than following it to another host,
masks bearer values in every failure message it prints, and never receives it as an argument,
where it would be visible in a step log and in `ps`.

## What is in scope

- An input that reaches a shell, a URL or an argument unsanitized.
- A string from the report, the policy file or the chain that produces live markup, a working
  link, or a real mention in the issue body.
- A refusal that does not refuse: a non-sha `gauge-ref` accepted, a `M...` or `C...` address
  accepted, a seed-shaped value that reaches a log whole, a report missing a load-bearing
  field that renders anyway, an exit code that disagrees with the run and is not caught.
- The report or Gauge's stderr appearing in the step log or in an artifact uploaded on
  success.
- A body sent to a host that was not named by `api_base()`, a redirect followed, or a retry
  loop with no bound.
- A change that makes a schedule fail on findings by default, or makes exit 2 and exit 3 pass,
  since both turn a control into noise (`ROADMAP.md` D-05).
- A workflow step in this repository that a pull request can edit and then have executed with
  the pull request's own inputs.
- An action in any workflow here pinned by tag rather than by commit sha.

## What is out of scope

- The configuration of any account a watch run reads. A report that a threshold is wrong is a
  finding for Gauge, not a vulnerability here; that is the whole product.
- A finding that a policy did not declare, or a rule Gauge does not have yet. There is no
  signer or threshold rule today, `README.md` says so, and "this did not catch it" is not a
  defect in plumbing.
- A state marker rewritten by somebody with write access to the issues of the repository that
  uses this action. That person can edit the issue directly; the marker buys nothing against
  them, and `ARCHITECTURE.md` section 4 records the consequence (the next run re-baselines).
- Vulnerabilities in Horizon, Stellar Core, the SDKs, GitHub Actions runners or the `actions/*`
  packages this workflow consumes.
- Anything reproduced only in a fork or an untagged commit, unless it also reproduces on `main`.

## Known limits, stated plainly

**Unaudited.** No third party has reviewed this code. It has run on GitHub's runners: three
jobs green on pull request #1 at `b107b0f` on 2026-11-04, including `self-check / action`,
which builds Gauge at the pinned sha and audits a live testnet account, and `ci / python` green
on the resulting push to `main` at `db8a5ed`. Its write has since been exercised, by a fourth
workflow rather than by those jobs: `watch / audit` ran with `dry-run` off on 2026-11-04, opened
issue #6 in this repository at 08:36:02Z, and at 08:39:51Z a second run found that issue by
the state marker in its body and left it byte-identical. `ROADMAP.md` gates G3 and G4 record what
those two runs prove and what they do not: an issue written by unaudited code is still written by
unaudited code. What is enforced
now is the path into `main`: ruleset 26515104 refuses a direct push and requires both
`ci / python` and `roadmap-check / gate`, so anything on the default branch arrived as a pull
request with those two green. It does not require a second reader, and with one maintainer it
cannot: `ROADMAP.md` 2.7 states that limit rather than hiding it.

**The renderer is only as strict as its tests.** 167 cases cover the refusals above, and the
ones that matter for the wire were observed against a loopback server rather than asserted
against a mock. A defect may still be waiting; a suite is not a proof.

**Findings are Gauge's judgement.** Nothing here decides that a posture is bad. If Gauge's
rules are wrong, this action will publish that error on a schedule, tidily, with a pinned sha
next to it. That sha is how you check which code produced an answer, not a guarantee that the
answer is right.

**The action trusts the caller's repository.** It runs with whatever permissions the calling
workflow grants and reads a policy file from that workspace. `config` is confined to a path
inside the workspace and the API base is confined to https, but a caller that hands this
action a token with more than `issues: write` has done that to itself.

**A pinned sha is not a reviewed diff.** The pins in these workflow files were resolved from
the tags named in the comment, and the same commits the sibling repositories use. Nobody
outside this organization has read those diffs, and a bump is supposed to be a deliberate
change with a changelog row, not a refresh.

**Change detection can be partial and says so.** Past 200 findings or 20 000 characters the
marker drops entries and the body opens with a bold line naming both numbers. A comparison
that reports "unchanged" while carrying a partial marker is the failure this design refuses to
hide.

## What this action cannot tell you

It publishes what four rules said about a policy at one ledger on one network. It cannot see
who holds a key, whether signers are separate people or separate devices, whether a threshold
is reachable, or any off-chain control. A clean tracking issue means the rules agreed. It does
not mean the account cannot be used, and every body it writes carries Gauge's own footer saying
exactly that.
