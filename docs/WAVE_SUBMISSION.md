# Drips Wave notes: stellar-posture-watch

Working notes for adding a fourth repository to the organization's Drips Wave position.
The authoritative packet is
[`posture-sec/guage/docs/WAVE_SUBMISSION.md`](https://github.com/posture-sec/guage/blob/main/docs/WAVE_SUBMISSION.md),
which carries the program facts, the runbook and the caps, all read from the Drips
maintainer docs rather than recalled. This file does not repeat those facts: it says what
changes for the organization now that this repository exists, and what has to be true here
before this repository is a candidate.

Last read of the program itself: 2026-11-05, from the program page, which is what changed reason 1
below. The caps, the tiers and the runbook still come from the Gauge packet written against the
2026-11-02 reading. Nothing here claims this repository is approved, applied to, or eligible. Its
git history is a day old (first commit
2026-11-04T06:58Z), twelve pull requests have merged into `main`, and it keeps two tracking
issues: #6 here, and #29 in `posture-sec/stellar-account-fixtures`, whose workflow is the second
caller of this action and the closing evidence of roadmap 3.4.

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

1. **A cycle is dated now, and it is thirteen days out.** The Gauge packet records that as of
   2026-11-02 the Stellar Wave page showed no active or upcoming wave. Read again on 2026-11-05,
   the page shows Stellar Wave #11 upcoming, November 18 to 25, with a $75,000 budget and a cap of
   five repositories per contributor and five per organization. So this reason is no longer that
   there is nothing to apply into. It is that the application is one act by the owner for the whole
   organization, into a capped slot, and that choosing this repository is his call rather than a
   gap this repository can close on its own.
2. **What a reviewer would check is now real, and only one person has checked it.** The write
   ran on 2026-11-04: `watch / audit` job 126475427542 built Gauge at the pinned sha, read
   `example/gauge.toml` against live testnet and opened issue #6 with one high `acct-missing`,
   on a green job while Gauge exited 1; job 126477058944 at 08:39:51Z found that issue by
   the state marker in its body, rendered 2291 characters of no change and left it byte-identical.
   Gates G1 to G4 are closed on those runs and on the body having been read against a report
   reproduced at the same sha. What has not changed is who did the reading. There is no tag
   (2.10, whose blocker cleared with the write), and nobody second who would notice a wrong
   finding. The other half of that sentence was false and is now corrected: 3.4 closed on
   2026-11-05, when `posture-sec/stellar-account-fixtures` began consuming this action by sha and
   published its own tracking issue from a live testnet read. The same maintainer wrote both
   callers, so the code path doubled and the reader count did not; that is G5, still open.
3. **The findings are thin because Gauge's are.** Four rules, no signer family, no threshold
   rule, blocked behind Gauge's 0.7, which needs a transaction Gauge is written never to
   build. A scheduled watch that reports a vanished account and a moved network is real;
   presenting it as account security review would oversell it, and the repository says so in
   three places.
4. **One maintainer, four repositories.** Wave weeks are a review load, not a merge load.
   The Gauge packet's conclusion holds with an extra repository in the pool: applying more
   than one per cycle is not realistic for one person, and a rejection is not refundable.

## 3. What wave work here would look like

These are published as issues now, by D-10 rather than by the approval this file used to wait for:
every open roadmap task in `ROADMAP.md` has an issue whose body carries that task's done-when as its
acceptance criteria, and the six shapes a stranger could take carry the label `Stellar Wave`. The
tiers named are the program's three, and they are a guess about effort, not a label.

| Shape | Work | Issue | Why it suits a contributor |
|---|---|---|---|
| Trivial | Nothing left after 3.7. The bug that was in this row, a section heading `## Accounts read` sitting above a table whose own last row says `(not read)`, is renamed to `## Accounts asked about` on `main`: one string in `render_report.py`, five test split sites, `README.md`'s schematic and `ARCHITECTURE.md` section 2. | none | The shape is the part worth keeping. A run printed a claim its own table contradicts, a grep found every site keyed on the string, and 3.6 had fixed the sentence half the day before. That is what to look for next time. |
| Medium | The escape surface as a test matrix: hostile `home_domain`, data values and messages assembled into one fixture per markdown construct, each with the render it must not produce. | #24, roadmap 9.5 | Pure, self-contained, and the failure mode is visible in the diff. |
| Medium | A documentation site for the action, with a rendered example issue beside the report that produced it. | #15, roadmap 2.9 | Deferred by the maintainer on purpose, so it is work a stranger can own without a design argument. |
| Medium | Watching a repository that is not one of this maintainer's four. The row this replaces, a second consumer at all, closed on 2026-11-05: `posture-sec/stellar-account-fixtures` calls the action from its own `.github/workflows/posture-watch.yml` pinned by sha, audits its own `.posture/gauge.toml`, and has published and left alone its issue #29 across three runs. | no issue, gate G5 | One workflow file, one policy file and one issue to read, against a worked example in a sibling repository. `CONTRIBUTING.md` keeps gate rows out of the issue tracker, and this one needs a reader rather than a pull request. |
| Medium | More than one policy file in one repository, which is one state marker per file. | #22, roadmap 9.3 | The contract is written down, the tests are the hard part, and nothing about the shipped schedule has to move. |
| Medium | The four Scorecard gaps this repository can close: hashed dev dependencies, an update tool, an analyzer, and a matrix or fuzz target for the renderer. | #25, roadmap 9.6 | Each one is a number this repository's own Scorecard run printed and explained, so the done state is readable without an argument about taste. |
| High | SARIF output so findings land in a repository's security tab. | #20, roadmap 9.1 | Needs a severity mapping nobody has agreed on and a SARIF writer in Gauge, so it is a design task first. |
| High | A `pull_request` mode that comments on the diff. | #21, roadmap 9.2 | The code is small and the decision is not: D-05 says a schedule stays green for findings and red for failures, and a merge check promises the opposite. |
| Medium | Upstream to Gauge: the signer and threshold rule families this watch cannot report without (Gauge 3.1, and its 0.7 blocker). | not in this repository | The highest-value work in the organization is not here, and a contributor should know that before choosing. |

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

Two of those three open rows are an owner action and a schedule: `v0.1.0` is a tag nobody has
pressed, and the recording wants a `scheduled` run, which for `watch.yml` is Tuesday 2026-11-10
at 05:23 UTC. The third, G5, is not available to the maintainer by definition, and 3.4's second
consumer did not supply it because that consumer is also his. So the summary of where this
repository is has moved once and no further on its own: written, tested, documented, executed on
a runner by two callers, and read by one person.

## 5. Sources

The program documents are listed once, in the Gauge packet, section 6. Read those rather
than this file for cadence, tiers, caps, budgets, the appeal path and the dashboard runbook.
The one fact here that is not inherited: the state of this repository was read from its own
files and its own hosted runs, and where a gate is open it says so.
