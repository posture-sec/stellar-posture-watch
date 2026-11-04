# Drips Wave notes: stellar-posture-watch

Working notes for adding a fourth repository to the organization's Drips Wave position.
The authoritative packet is
[`posture-sec/guage/docs/WAVE_SUBMISSION.md`](https://github.com/posture-sec/guage/blob/main/docs/WAVE_SUBMISSION.md),
which carries the program facts, the runbook and the caps, all read from the Drips
maintainer docs rather than recalled. This file does not repeat those facts: it says what
changes for the organization now that this repository exists, and what has to be true here
before this repository is a candidate.

Last read of the program itself: 2026-11-02, in the Gauge packet. Nothing here claims this
repository is approved, applied to, or eligible. Its git history is just over an hour old
(first commit 2026-11-04T06:58Z) and its first pull request is still open.

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
2. **The write has not run.** The action executed on a GitHub runner once, on 2026-11-04 in
   `self-check / action` at `b107b0f`: it built Gauge at the pinned sha, read a live testnet
   account and rendered the body. It opened no issue, edited none, and has no tag. Gates G1 to
   G5 in `ROADMAP.md` are all open, and G3 ("the action has run end to end and produced an
   issue that matches its report") is the one every claim in the README depends on. The run
   proves the plumbing loads; the sentence a reviewer would actually be checking, that the
   issue stays current, is still unproven. A submission would then invite the reviewer to
   check the one promise the README makes, which is the worst thing to hand a stranger.
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
| Medium | Get G3 true: a scheduled workflow in this repository, on testnet, that opens the tracking issue, plus the reading of the body against the JSON it came from (roadmap 3.1, 3.2, G3, G4). | It is an operator task with a checklist, and the acceptance criterion is a link to a run. |
| Medium | The escape surface as a test matrix: hostile `home_domain`, data values and messages assembled into one fixture per markdown construct, each with the render it must not produce (roadmap 1.2 follow-on). | Pure, self-contained, and the failure mode is visible in the diff. |
| Trivial | `docs/` page with a rendered example issue beside the report that produced it, with ledger and date. | Reading is the deliverable. |
| Medium | A second consumer: point this action at one of the organization's own repositories watching a real treasury policy, or write down that nobody uses it (roadmap 3.4, G5). | The honest version is two paragraphs and one decision. |
| High | SARIF output so findings land in a repository's security tab (roadmap 9.1). | Needs a severity mapping nobody has agreed on and a SARIF writer in Gauge, so it is a design task first. |
| Medium | Upstream to Gauge: the signer and threshold rule families this watch cannot report without (Gauge 3.1, and its 0.7 blocker). | The highest-value work in the organization is not in this repository, and a contributor should know that. |

The guard scripts, the marker contract, and the exit-code mapping in D-05 are not on this
list. They are the parts a maintainer has to own, because each is a decision dressed as code.

## 4. What has to be true before this is a candidate

- [ ] G1: `ci / python` and `roadmap-check / gate` green on `main`, observed rather than local.
- [ ] G2: `main` protected, profile filled in, and the org profile row (`posture-sec/.github`).
- [ ] G3: the action has run end to end on a runner and produced or updated an issue.
- [ ] G4: that issue body read against the JSON it came from, every number traced.
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
