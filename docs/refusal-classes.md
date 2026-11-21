# Refusal Classes and Stderr Messages

`scripts/render_report.py` terminates with exit code 2 when it encounters invalid command line arguments, an unacceptable report payload, or an output destination error. It produces no partial markdown output on exit 2.

Refusals fall into three distinct families based on their stderr formatting:
1. **Argument refusals**: printed directly to stderr without a prefix.
2. **Output write failure**: printed directly to stderr when writing the markdown output fails.
3. **Report validation refusals**: raised as `Refused` exceptions and printed as `render_report: refused: <message>` at line 435.

## Observed Stderr Output Examples

The following real stderr lines were captured by invoking `scripts/render_report.py`:

- **Argument refusal**:
  ```
  render_report: --as-of '2026-11-03-invalid' is not a YYYY-MM-DD date
  ```
- **Report validation refusal (`Refused`)**:
  ```
  render_report: refused: report /dev/null: is empty
  ```

## Catalog of Exit 2 Paths

### 1. Argument Refusals (No Prefix)

These checks validate command line options during argument processing in `main()` before the report is read.

| Condition | Message Shape | Line in `scripts/render_report.py` | Test in `tests/test_render_report.py` |
| --- | --- | --- | --- |
| `--as-of` does not parse as ISO date | `render_report: --as-of {args.as_of!r} is not a YYYY-MM-DD date` | line 424 | `test_a_non_iso_as_of_date` (:535) |
| `--as-of` is not canonical format | `render_report: --as-of {args.as_of!r} is not a canonical ISO date` | line 427 | `test_a_non_iso_as_of_date` (:535) |
| `--gauge-ref` is not 40 hex characters | `render_report: --gauge-ref must be a full 40-character commit sha` | line 430 | `test_a_non_sha_gauge_ref` (:541) |

### 2. Output Write Failure (No Prefix)

Emitted if writing the generated markdown or summary output fails due to filesystem or permissions errors.

| Condition | Message Shape | Line in `scripts/render_report.py` | Test in `tests/test_render_report.py` |
| --- | --- | --- | --- |
| Failed to write output file | `render_report: cannot write {out}: {exc.strerror}` | line 452 | None yet |

### 3. Report Refusals (`render_report: refused: <message>`)

Raised as `Refused` (`scripts/render_report.py:48`), caught in `main()` at line 434, and printed to stderr at line 435.

#### In `read_report`:

| Condition | Message Shape | Line in `scripts/render_report.py` | Test in `tests/test_render_report.py` |
| --- | --- | --- | --- |
| File cannot be read (OS error) | `report {path}: cannot read it ({exc.strerror})` | line 72 | `test_an_unreadable_report_path` (:530) |
| Report file is 0 bytes | `report {path}: is empty` | line 74 | `test_an_empty_file` (:487) |
| Report exceeds size limit (>8 MiB) | `report {path}: {len(raw)} bytes is over the 8 MiB limit` | line 76 | `test_an_oversized_report` (:525) |
| Invalid JSON syntax | `report {path}: is not valid JSON at line {exc.lineno}` | line 80 | `test_an_unparseable_report` (:482) |
| Top-level JSON is not an object | `report {path}: the top level is not an object` | line 82 | `test_a_report_that_is_a_list` (:520) |
| Missing required load-bearing key | `report {path}: is missing the {key!r} field` | line 85 | `test_a_missing_field` (:492) |
| `accounts` is not a list | `report {path}: accounts is not an array` | line 87 | None yet |

#### In `collect_findings`:

| Condition | Message Shape | Line in `scripts/render_report.py` | Test in `tests/test_render_report.py` |
| --- | --- | --- | --- |
| Account entry is not an object | `{where} is not an object` | line 97 | None yet |
| Snapshot missing or has no `id` string | `{where} has no snapshot.id` | line 100 | `test_an_account_with_no_snapshot` (:513) |
| Finding entry is not an object | `{where} has a finding that is not an object` | line 103 | None yet |
| Finding severity not `high` or `warn` | `{where} has a finding with unknown severity {severity!r}` | line 106 | `test_an_unknown_severity` (:499) |
| Fingerprint is not 64 hex characters | `{where} has a finding without a 64-character fingerprint, so it cannot be tracked between runs` | line 109 | `test_a_finding_without_a_useful_fingerprint` (:506) |
| Finding has no `rule_id` string | `{where} has a finding with no rule_id` | line 115 | None yet |

#### In `render`:

| Condition | Message Shape | Line in `scripts/render_report.py` | Test in `tests/test_render_report.py` |
| --- | --- | --- | --- |
| Report `exit_code` != CLI `--exit-code` | `the report carries exit code {reported_exit!r} and the run reported {args.exit_code}` | line 305 | `test_an_exit_code_that_disagrees_with_the_report` (:475) |
| `tool_version` missing or empty | `the report carries no tool_version` | line 310 | None yet |
