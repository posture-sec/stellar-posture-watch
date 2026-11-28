# Mainnet Run Records

This document records operational audit runs performed against Stellar public mainnet (`https://horizon.stellar.org`).

Under decision D-03 (`ROADMAP.md:68`), this repository's automated CI checks and scheduled dogfood workflows run exclusively against testnet. No scheduled mainnet workflow run exists yet. Tests depending on live mainnet state can fail due to ledger state movements unrelated to code defects.

The run below is a verified read-only `stellar-gauge check` execution against Horizon mainnet, not a scheduled Action workflow run.

## Run 1: 2026-11-28T12:53:16Z (Read-Only CLI Check)

- **Date (UTC)**: `2026-11-28T12:53:16Z`
- **Method**: `go run ./cmd/stellar-gauge check --network mainnet --endpoint https://horizon.stellar.org GAUA7XL5K54CC2DDGP77FJ2YBHRJLT36CPZDXWPM6MP7MANOGG77PNJU`
- **Network**: Stellar Mainnet (passphrase: `Public Global Stellar Network ; September 2015`)
- **Endpoint**: `https://horizon.stellar.org`
- **Gauge Commit**: `3a2aad12088d61541c53fb33bcba4b40fa440b93` (`stellar-gauge 0.1.0-dev`)
- **Ledger Sequence**: `65716863` (account `as of ledger 65716863`, sequence `206632444273623301`)
- **Exit Code**: `0`
- **Accounts**: 1 account read of 1 asked about
- **Findings**: 1 open (0 high, 0 warn, 1 info, 0 accepted)
  - `[info] sig-single-key-high` (`3f4f7fb0090c38a0aee6399849571dcb72b53cc8e4d88c9a18269b5fc5786dfe`)

### Findings Summary

The read-only check executed against the verified public Horizon mainnet endpoint at ledger `65716863` against public multisig account `GAUA7XL5K54CC2DDGP77FJ2YBHRJLT36CPZDXWPM6MP7MANOGG77PNJU`. Thresholds are `2/2/2` with 9 signers (two weight-2 signers, six weight-1 signers, and the master key at weight 0), so `[info] sig-single-key-high` fires at baseline INFO while exit code remains `0` under the default `--fail-on high`. In accordance with decision D-06, raw report JSON and issue bodies are not reproduced in this log.
