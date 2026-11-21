# Escape Contract

The tracking issue body is rendered in markdown from JSON reports. Report strings originate from on-chain account data, Horizon responses, or policy files. Because Gauge controls character formatting but does not escape markdown markup, `scripts/render_report.py` escapes all report-derived strings at render time.

## Escape Order and the Mention Rewrite

The order of substitutions inside `escape()` (`scripts/render_report.py:52-60`) is strictly ordered:

```python
text = MARKDOWN_SPECIAL.sub(r"\\\1", str(value))
return MENTION.sub(lambda m: "@&#8203;" + m.group(1), text)
```

1. **`MARKDOWN_SPECIAL` backslash-escapes markdown characters**:
   The regular expression at `scripts/render_report.py:33` matches `([\\*_\[\]<>#|~`&])`. This escapes markdown delimiters and HTML brackets, including the ampersand `&`.
2. **`MENTION` neutralizes user and team pings**:
   The regular expression at `scripts/render_report.py:34` matches `(?<![\w/])@(\w{1,39})` and inserts a zero-width space entity (`@&#8203;name`).

### Why the Order Cannot Be Reversed

The ampersand `&` is a member of `MARKDOWN_SPECIAL`. If mention rewriting ran before `MARKDOWN_SPECIAL`, the entity `&#8203;` produced by the mention pass would have its ampersand escaped into `\\&` during the special character pass. The result would render literally as `@\\&#8203;name` in GitHub issue markdown, leaving the mention active and notifying users, teams, or `@all`.

By escaping `MARKDOWN_SPECIAL` first, the ampersand in `@&#8203;name` is inserted after the character pass and reaches the issue body untouched as an active zero-width space.

## Escaped vs Fenced Rule

The renderer applies two distinct sanitization functions based on whether a field is free text or a constrained token:

- **`escape()` for free text**: Used for any string that can contain arbitrary characters, links, formatting, or mentions chosen by account owners or policy authors.
- **`fenced()` only for values Gauge constrains**: Used exclusively for fields whose format is strictly constrained by Stellar specifications or Gauge validation (such as rule IDs, 56-character public keys, and 64-character hexadecimal fingerprints). `fenced()` wraps the value in backticks and replaces any inner backtick with `&#96;` (`scripts/render_report.py:62-65`).

## Report-Derived Fields and Their Treatment

Every report-derived string rendered in the tracking issue body is listed below with its treatment and code location:

| Field | Source Path | Treatment | Line in `scripts/render_report.py` | Justification |
| --- | --- | --- | --- | --- |
| Severity | `finding['severity']` | `escape()` | line 216 | Free text representation in markdown table cell |
| Rule ID | `finding['rule']` | `fenced()` | line 216 | Gauge-constrained rule identifier token |
| Account ID | `finding['account']` | `fenced()` | line 217 | Stellar public key (`G...`), constrained 56 chars |
| Fingerprint prefix | `finding['fingerprint'][:12]` | `fenced()` | line 217 | Hexadecimal hash prefix, constrained format |
| Message | `finding['message']` | `escape()` | line 218 | Free text finding explanation; may hold arbitrary chars |
| Snapshot ID | `snapshot.get('id')` | `fenced()` | lines 238, 251 | Stellar public key (`G...`), constrained format |
| Account Status | `account_status(account)` | `escape()` | lines 239, 255 | Status string (`not read: ...`), may carry reason |
| Flag Name | `flags.items()` key | `fenced()` | line 245 | Stellar account flag name, constrained token |
| Home Domain | `snapshot.get('home_domain')` | `escape()` | line 255 | On-chain string set by account owner; hostile vector |
| Network | `report['network']` | `escape()` | line 345 | Network name string from report header |
| Tool Version | `tool_version` | `escape()` (in backticks) | line 346 | Software release or git description string |
| Limits | `report['limits']` | `escape()` | line 368 | Free text limitations block in report footer |

## Test Coverage and Adding New Fields

Existing test coverage in `tests/test_render_report.py` verifies this contract:
- `test_a_home_domain_of_markup_is_escaped` (`tests/test_render_report.py:425`): Verifies that link syntax and markdown markup in `home_domain` are backslash-escaped rather than rendered as live markdown links.
- `test_mentions_in_chain_fields_cannot_notify_anyone` (`tests/test_render_report.py:431`): Verifies that `@all` and `@somebody` mentions in chain-derived fields are rewritten to use `@&#8203;` zero-width spaces.

When a contributor adds a new report field to the issue body:
1. Determine whether the field is free text or a constrained token.
2. If free text, pass it through `escape()`. If constrained, pass it through `fenced()`.
3. Add a test in `tests/test_render_report.py` under `TestHostileStrings` proving that hostile markdown markup and `@mentions` placed in the new field cannot produce live formatting or pings.
