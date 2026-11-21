# State Marker Budget and Change Detection

The tracking issue body embeds its own previous state inside an HTML comment at the foot of the markdown body (`scripts/render_report.py:377`). This enables change detection between consecutive scheduled runs without external state storage (decision D-07, `ROADMAP.md:72`).

## Marker Budgets and Encoding

The state marker is constrained by two limits defined in `scripts/render_report.py`:

- **Entry limit**: `MAX_STATE_ENTRIES = 200` (`scripts/render_report.py:28`).
- **Character limit**: `MAX_MARKER_CHARS = 20_000` (`scripts/render_report.py:29`).

The marker payload is encoded as base64url (`scripts/render_report.py:148-150`). Standard HTML comments cannot contain the character sequence `--`. Because finding messages can contain arbitrary strings and characters (including `--`), base64url encoding guarantees the payload safely round-trips through GitHub Issue API markdown parsers without prematurely closing the comment.

Entries are packed in ascending fingerprint order (`scripts/render_report.py:153`). As a result, finding severity does not influence retention priority: high-severity and warn-severity findings have equal likelihood of being retained or omitted.

## Shrink Step and Omission Notice

When the serialized and encoded state exceeds `MAX_MARKER_CHARS` (20,000 characters) or the entry count exceeds `MAX_STATE_ENTRIES` (200), `encode_state` iteratively sheds entries in a loop (`scripts/render_report.py:155-161`). Each iteration drops at least one-eighth of the total entries:

```python
limit = max(limit - max(1, len(ordered) // 8), 0)
```

The loop repeats until the marker fits within 20,000 characters or the limit drops to 0.

When one or more findings are omitted, the renderer emits an explicit notice verbatim:

```markdown
**Change detection is partial.** The state marker carries {kept} of {total} open findings; {omitted} were left out of it, so a run that only moves those findings will report none change.
```

### Notice Placement in the Issue Body

The omission notice is emitted directly following the status line and header paragraph (`scripts/render_report.py:350-355`), right before the `## New since the previous run` heading. It does not open the issue body. `ARCHITECTURE.md` section 4 previously claimed the body opened with this line; that location was incorrect.

## The Blind Spot

Change detection compares open findings from the current report against findings decoded from the previous marker (`scripts/render_report.py:325-327`):

```python
before = {f["fingerprint"]: f for f in previous}
new = [current[fp] for fp in sorted(set(current) - set(before))]
resolved = [before[fp] for fp in sorted(set(before) - set(current))]
```

This introduces an unavoidable blind spot:
If an open finding was omitted from the state marker due to budget limits, the subsequent run has no record that the finding ever existed. When that omitted finding is later fixed on-chain, it cannot appear under `## Resolved since the previous run`. The subtraction `set(before) - set(current)` only detects resolutions for findings recorded in `before`.

## Visibility of Omitted Counts

- **Who sees the number**: The operator reading the rendered issue body or examining the step output log sees the omission notice and exact counts.
- **Who does not see the number**: `sync_issue.py` ignores `omitted`. Its summary reader (`scripts/sync_issue.py:243`) extracts only five keys (`changed`, `open`, `high`, `warn`, `accepted`). The GitHub issue syncer and step comments do not inspect or propagate the omitted count.

The marker budget is not a guarantee that all findings will be tracked across runs. The explicit notice in the rendered markdown is the sole admission that change detection is partial.
