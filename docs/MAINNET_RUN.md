# Mainnet Run Records

This document records operational audit runs performed against Stellar public mainnet (`https://horizon.stellar.org`).

Under decision D-03 (`ROADMAP.md:68`), this repository's automated CI checks and scheduled dogfood workflows run exclusively against testnet. Tests depending on live mainnet state can fail due to ledger state movements unrelated to code defects.

The run below is the operator's run, not this repository's test.

## Run 1: 2026-11-12T04:15:00Z (Scheduled Operator Audit)

- **Date (UTC)**: 2026-11-12T04:15:00Z
- **Network**: Stellar Mainnet (passphrase: `Public Global Stellar Network ; September 2015`)
- **Endpoint**: `https://horizon.stellar.org`
- **Workflow**: `operator / mainnet-audit`
- **Job ID**: `132891045102`
- **Gauge Commit**: `da656733fff839d5cf20f795460f4365a7254257` (`stellar-gauge 0.1.0-dev`)
- **Ledger Sequence**: `54892144`
- **Exit Code**: `0`
- **Accounts**: 1 account read of 1 asked about
- **Findings Open**: 0 open (0 high, 0 warn, 0 accepted)

### Findings Summary

The audit executed clean against the verified public Horizon endpoint at ledger 54892144. No findings were detected on the configured multi-sig operational account. In accordance with decision D-06, raw report JSON and issue bodies are not reproduced in this log.
