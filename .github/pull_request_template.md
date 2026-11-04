## Task IDs

-

## What changed

## How it was tested

Paste the commands and their real output. Say which checks were not run and which do not
exist yet; a local run is a local run, not a hosted one. If this touches `action.yml`, name
the `self-check` run and say whether the audit step was reached.

## Contract changes

- [ ] No load-bearing report field changed (`ARCHITECTURE.md` section 2)
- [ ] A field was added, tightened or relaxed, and the renderer's refusal and its test changed
      with it
- [ ] No Action input changed name, default or meaning
- [ ] An input changed, and `README.md`, `action.yml` and `validate_inputs.py` agree on it

## Posture of the change

- [ ] Nothing was weakened, skipped or deleted to make a check pass
- [ ] No new dependency; nothing installed at runtime
- [ ] No report body, policy text or token reaches stdout, a log line or an artifact on success
- [ ] A schedule still stays green for findings and red for failures, or this PR argues why
      `ROADMAP.md` D-05 should change

## Docs updated

- [ ] `ROADMAP.md` is updated in this pull request: task boxes, a changelog row with the UTC
      time from `date -u`, `python3 scripts/roadmap_progress.py`, and `Last updated`
- [ ] `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` and `SECURITY.md` match what the code
      now does, and every claim names the run or says it is local
- [ ] No claim of a hosted run, a tag, or a consumer that does not exist yet
