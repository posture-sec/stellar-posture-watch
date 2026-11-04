# Drips Wave notes: stellar-posture-watch

Working notes for adding a fourth repository to the organization's Drips Wave position.
The authoritative packet is
[`posture-sec/guage/docs/WAVE_SUBMISSION.md`](https://github.com/posture-sec/guage/blob/main/docs/WAVE_SUBMISSION.md),
which carries the program facts, the runbook and the caps, all read from the Drips
maintainer docs rather than recalled. This file does not repeat those facts: it says what
changes for the organization now that this repository exists, and what has to be true here
before this repository is a candidate.

Last read of the program itself: 2026-11-02, in the Gauge packet. Nothing here claims this
repository is approved, applied to, or eligible. Its git history is two hours old (first commit
2026-11-04T06:58Z), five pull requests have merged into `main`, and it maintains one scheduled
tracking issue, #6.

## 1. What this repository adds to the argument

The organization's pitch has always been the same observation in three places: Stellar
accounts and repositories carry public configuration that nobody reviews, and the tools to
review it are not missing so much as unused. Gauge is a gate you walk through. Airlock
scans a repository. The corpus proves the shapes are real. This one is the clock: a
composite Action whose whole job is that it runs on a schedule in the consumer's own
repository, whether or not anybody remembered.

That is the difference between a tool and a control, and it is the sentence this repository
exists to make true. It also means the submission value here is plumbing, not detection.
Every finding an issue carries came from four rules in Gauge, and this repository adds no
rule and argues with none. A reviewer who wants to know what the wave work would be should
read section 3, not the roadmap.

## 2. Why this repository is not applying

Four reasons, in order of how long each takes to clear.

1. **No cycle is open.** The Gauge packet records that as of 2026-11-02 the Stellar Wave
   page shows no active or upcoming wave. There is nothing to apply into, and the caps are
   dashboard-only facts.
2. **What a reviewer would check is now real, and only one person has checked it.** The write
   ran on 2026-11-04: `watch / audit` job 126475427542 built Gauge at the pinned sha, read
   `example/gauge.toml` against live testnet and opened issue #6 with one high `acct-missing`,
   on a green job while Gauge exited 1; job 126477058944 at 08:39:51Z found that issue by
   the state marker in its body, rendered 2291 characters of no change and left it byte-identical.
   Gates G1 to G4 are closed on those runs and on the body having been read against a report
   reproduced at the same sha. What has not changed is who did the reading and what is pinned to
   it: there is no tag (2.10, whose blocker cleared with the write), no consumer but this
   repository (3.4, G5), and nobody second who would notice a wrong finding.
3. **The findings are thin because Gauge's are.** Four rules, no signer family, no threshold
   rule, blocked behind Gauge's 0.7, which needs a transaction Gauge is written never to
   build. A scheduled watch that reports a vanished account and a moved network is real;
   presenting it as account security review would oversell it, and the repository says so in
   three places.
4. **One maintainer, four repositories.** Wave weeks are a review load, not a merge load.
   The Gauge packet's conclusion holds with an extra repository in the pool: applying more
   than one per cycle is not realistic for one person, and a rejection is not refundable.

## 3. What wave work here would look like

Not published as issues, per the standing rule that wave-scoped issues go up only after an
application is approved, and none of these is shaped for a stranger yet. The tiers named are
the program's three, and they are a guess about effort, not a label.

| Shape | Work | Why it suits a contributor |
|---|---|---|
| Trivial | Nothing left after 3.7. The bug that was in this row, a section heading `## Accounts read` sitting above a table whose own last row says `(not read)`, is renamed to `## Accounts asked about` on this branch: one string in `render_report.py`, five test split sites, `README.md`'s schematic and `ARCHITECTURE.md` section 2. | The shape is the part worth keeping. A run printed a claim its own table contradicts, a grep found every site keyed on the string, and 3.6 had fixed the sentence half the day before. That is what to look for next time. |
| Medium | The escape surface as a test matrix: hostile `home_domain`, data values and messages assembled into one fixture per markdown construct, each with the render it must not produce (roadmap 1.2 follow-on). | Pure, self-contained, and the failure mode is visible in the diff. |
| Medium | A documentation site for the action (roadmap 2.9), with a rendered example issue beside the report that produced it. | Deferred by the maintainer on purpose, so it is work a stranger can own without a design argument. |
| Medium | A second consumer: point this action at one of the organization's own repositories watching a real treasury policy, or write down that nobody uses it (roadmap 3.4, G5). | The honest version is two paragraphs and one decision. |
| High | SARIF output so findings land in a repository's security tab (roadmap 9.1). | Needs a severity mapping nobody has agreed on and a SARIF writer in Gauge, so it is a design task first. |
| Medium | Upstream to Gauge: the signer and threshold rule families this watch cannot report without (Gauge 3.1, and its 0.7 blocker). | The highest-value work in the organization is not in this repository, and a contributor should know that. |

The guard scripts, the marker contract, and the exit-code mapping in D-05 are not on this
list. They are the parts a maintainer has to own, because each is a decision dressed as code.

## 4. What has to be true before this is a candidate

- [x] G1: `ci / python` and `roadmap-check / gate` green on `main`, observed rather than local.
  Closed 2026-11-04: pull request #1's push to `main` (`db8a5ed`) passed `ci / python` as job
  126445751941 on CPython 3.11.18 with all 167 cases, and the gate ran green on that pull
  request. A green run on `main` is an observation, and since 2026-11-04 it is also a rule:
  ruleset 26515104 refuses a direct push to `main` and requires both checks.
- [x] G2: `main` protected, profile filled in, and the org profile row (`posture-sec/.github`).
  Closed 2026-11-04: ruleset 26515104 was observed refusing a direct push to `main`, the four
  profile fields read back from the API, and the row landed in `posture-sec/.github` as `06d2db5`.
  Its first Scorecard run on the same morning reads **5.2** over 18 checks, with
  `Branch-Protection` at 4 because the ruleset requires the pull request and the two checks and
  no approving review.
- [x] G3: the action has run end to end on a runner and produced or updated an issue. Closed
  2026-11-04: `watch / audit` opened issue #6 (job 126475427542) and a second dispatch found and
  left it alone (126477058944, `changed=false`).
- [x] G4: that issue body read against the JSON it came from, every number traced. Closed the same
  day against a report reproduced on the desk at `da656733`, which is 4646 bytes for the runner's
  4646 bytes; `ROADMAP.md` G4 lists the field behind each number.
- [ ] G5: somebody other than the maintainer has run it, or the README says nobody has.
- [ ] `v0.1.0` tagged, so a consumer can pin a release rather than a commit nobody named.
- [ ] A screen recording of a scheduled run and the issue it updated, which the program
      playbook treats as the difference between a submission and an unfinished one.

Three of those six need a runner, not a pull request. That is the honest summary of where
this repository is: written, tested, documented, and unexecuted.

## 5. Sources

The program documents are listed once, in the Gauge packet, section 6. Read those rather
than this file for cadence, tiers, caps, budgets, the appeal path and the dashboard runbook.
The one fact here that is not inherited: the state of this repository was read from its own
files and its own hosted runs, and where a gate is open it says so.
