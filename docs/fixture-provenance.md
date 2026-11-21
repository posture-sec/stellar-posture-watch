# Fixture Provenance and Capture Procedure

The report fixtures in `tests/fixtures/` provide stable JSON inputs for testing `scripts/render_report.py` and `scripts/sync_issue.py` without network access.

## Verification Policy and Testnet Rule

As stated in `SECURITY.md`:
> Four of the six were produced by a real run on **testnet** on 2026-11-03 (UTC), which is this organization's verification policy: Gauge is only ever run against testnet for its own checks.

Fixtures must only ever be captured from Stellar testnet Horizon endpoints. Mainnet reads are prohibited for fixture generation.

## Seed-Shaped String Refusal

As stated in `SECURITY.md`:
> **Never paste a secret seed (`S...`) into a report or an issue.** If a seed did reach a file in this tree, treat the key as compromised, move it, then report

No fixture in this repository may carry a secret seed or seed-shaped string (`S[A-Z2-7]{55}`). This invariant is strictly enforced by unit test:
- `test_no_fixture_contains_a_seed_shaped_string` (`tests/test_render_report.py:599`).

## Capture Procedure

To capture a fresh report from testnet and register it as a fixture:

1. **Build `stellar-gauge` from the pinned commit sha**:
   Checkout `posture-sec/guage` at the commit pinned in `ROADMAP.md` (for example, `da656733fff839d5cf20f795460f4365a7254257`) and build the binary:
   ```bash
   cargo build --release
   ```
2. **Execute the capture command against testnet**:
   Run `stellar-gauge` in `check` or `audit` mode targeting testnet, redirecting stdout to the target fixture file:
   ```bash
   stellar-gauge audit --network testnet --endpoint https://horizon-testnet.stellar.org \
     --config policy.toml --format json > tests/fixtures/report-example.json
   ```
3. **Compute the SHA256 digest**:
   Calculate the raw byte SHA256 checksum of the captured JSON file:
   ```bash
   sha256sum tests/fixtures/report-example.json
   ```
4. **Register the row in `tests/fixtures/README.md`**:
   Add an entry to the markdown table in `tests/fixtures/README.md` containing all four required columns.
5. **Verify the manifest suite**:
   Run `python3 -m unittest discover -s tests -t tests` to ensure `tests/test_fixture_manifest.py` and `tests/test_render_report.py` pass.

## Row Definition

Each report in `tests/fixtures/README.md` has a table row with four columns:

1. **File**: Name of the fixture file (such as `report-findings.json`).
2. **Origin**: Run metadata. For captured files, record `real run, ledger <number>, exit <0|1>`. For derived files, record `derived from <source_filename>`.
3. **sha256**: Lowercase 64-character hexadecimal SHA256 checksum over raw file bytes.
4. **What it exercises**: Specific test scenarios or code branches this fixture triggers.

## Captured versus Derived Fixtures

- **Captured fixture**: An unmodified JSON output produced directly by `stellar-gauge` against testnet. Its origin column must state the ledger sequence number and exit code.
- **Derived fixture**: A hand-edited variant created to test conditions not easily observed on testnet (such as `accepted: true` policies or hostile markdown injection). A derived fixture omits live ledger metadata, states its source fixture file in the origin column, and must document every field modified from the original source.
