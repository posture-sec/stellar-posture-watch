# SARIF Severity Mapping

This document records the mapping from Gauge finding severities to SARIF 2.1.0 levels,
per issue #20.

## Gauge severities

Gauge emits two finding severities:

| Gauge severity | Description |
| --- | --- |
| `high`  | A configuration gap that directly raises account risk. `--fail-on high` exits 1 on these. |
| `warn`  | A configuration gap worth noting but below the `high` threshold. `--fail-on warn` includes these. |

Additionally, an account may be `skipped` (Gauge could not read it) or `missing` (the
account was not found on the endpoint). These produce no finding rows; they appear in the
Accounts table as a `Read` column value, not in the finding list.

## SARIF 2.1.0 levels

SARIF defines five result levels: `error`, `warning`, `note`, `none`, and `open`
(the last is for rule-agnostic results). The GitHub security tab displays `error`
and `warning`; `note` does not appear there but is valid SARIF.

## Mapping

| Gauge severity | SARIF level | Rationale |
| --- | --- | --- |
| `high` | `error` | High is the stricter threshold; it maps to the signal GitHub shows as an error. |
| `warn` | `warning` | Warn is advisory; it maps to warning so it appears in the security tab without escalating. |

An account that was skipped or is missing produces no finding row and therefore no SARIF
result. The run writes an empty `results` array in that case.

## Schema and tool identity

The emitted SARIF file declares:

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "stellar-gauge",
          "version": "<tool_version from report>",
          "informationUri": "https://github.com/<gauge-repo>"
        }
      }
    }
  ]
}
```

`tool_version` comes from the Gauge JSON report field of the same name and is the same
string that appears in the issue body's audit line.

## Location encoding

SARIF results require a `locations` array. Because Gauge findings are account-level (not
line-level in a file), each result uses a `logicalLocations` entry with:

- `name`: the full Stellar account address (G...)
- `kind`: `"account"`

This is a valid SARIF `logicalLocation` and allows the security tab to group results by
account.

## Implementation

`render_sarif()` in `scripts/render_report.py` produces the SARIF dict. The caller
passes `--sarif-out <path>` to write it; without that flag, no SARIF is written and the
action runs in its default markdown mode.

The `output-format` action input controls whether SARIF is written:

- `markdown` (default): tracking issue is updated, no SARIF file
- `sarif`: SARIF file is written, and the `sarif-path` output carries its path for
  `actions/upload-sarif`
