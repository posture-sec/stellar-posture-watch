"""Issue #58: decode_state() must raise Refused for bad severity or fingerprint.

A well-formed state marker whose entries carry an unknown severity or a non-hex-64
fingerprint is not silently re-baselined: that would let a hand-edited marker forge a
clean state. Instead decode_state() raises Refused so sync_issue.py exits with code 2.

Bad base64 / a missing required field still returns None (no previous state), because
those inputs cannot plausibly be a hand-edited forgery.
"""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402
from render_report import MARKER_PREFIX, MARKER_SUFFIX, Refused  # noqa: E402


def _make_marker(entries: list[dict]) -> str:
    payload = json.dumps(entries, separators=(",", ":"), sort_keys=True)
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{MARKER_PREFIX}{encoded}{MARKER_SUFFIX}"


VALID_ENTRY: dict = {
    "account": "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP",
    "fingerprint": "a" * 64,
    "rule": "flag-drift",
    "severity": "high",
}


class TestDecodeStateValidation(unittest.TestCase):
    """decode_state() refuses bad severity/fingerprint; returns None for missing/bad base64."""

    # --- good path ---

    def test_valid_entry_decoded(self) -> None:
        body = _make_marker([VALID_ENTRY])
        result = render_report.decode_state(body)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)  # type: ignore[arg-type]
        self.assertEqual(result[0]["severity"], "high")  # type: ignore[index]

    def test_warn_severity_accepted(self) -> None:
        entry = {**VALID_ENTRY, "severity": "warn"}
        body = _make_marker([entry])
        result = render_report.decode_state(body)
        self.assertIsNotNone(result)

    # --- bad severity raises Refused ---

    def test_unknown_severity_raises(self) -> None:
        entry = {**VALID_ENTRY, "severity": "critical"}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_empty_severity_raises(self) -> None:
        entry = {**VALID_ENTRY, "severity": ""}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_uppercase_severity_raises(self) -> None:
        entry = {**VALID_ENTRY, "severity": "HIGH"}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    # --- bad fingerprint raises Refused ---

    def test_short_fingerprint_raises(self) -> None:
        entry = {**VALID_ENTRY, "fingerprint": "abc123"}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_non_hex_fingerprint_raises(self) -> None:
        entry = {**VALID_ENTRY, "fingerprint": "g" * 64}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_uppercase_hex_fingerprint_raises(self) -> None:
        entry = {**VALID_ENTRY, "fingerprint": "A" * 64}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_65_char_fingerprint_raises(self) -> None:
        entry = {**VALID_ENTRY, "fingerprint": "a" * 65}
        body = _make_marker([entry])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    # --- bad base64 / structural problems return None ---

    def test_no_marker_returns_none(self) -> None:
        self.assertIsNone(render_report.decode_state("no marker here"))

    def test_bad_base64_returns_none(self) -> None:
        body = f"{MARKER_PREFIX}!!!not-valid-base64!!!{MARKER_SUFFIX}"
        self.assertIsNone(render_report.decode_state(body))

    def test_not_a_list_returns_none(self) -> None:
        payload = json.dumps({"key": "value"}, separators=(",", ":"))
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        body = f"{MARKER_PREFIX}{encoded}{MARKER_SUFFIX}"
        self.assertIsNone(render_report.decode_state(body))

    def test_missing_severity_field_returns_none(self) -> None:
        entry = {k: v for k, v in VALID_ENTRY.items() if k != "severity"}
        body = _make_marker([entry])
        self.assertIsNone(render_report.decode_state(body))

    def test_missing_fingerprint_field_returns_none(self) -> None:
        entry = {k: v for k, v in VALID_ENTRY.items() if k != "fingerprint"}
        body = _make_marker([entry])
        self.assertIsNone(render_report.decode_state(body))

    def test_non_string_severity_returns_none(self) -> None:
        entry = {**VALID_ENTRY, "severity": 1}
        body = _make_marker([entry])
        self.assertIsNone(render_report.decode_state(body))

    def test_non_dict_entry_returns_none(self) -> None:
        body = _make_marker(["not-a-dict"])  # type: ignore[list-item]
        self.assertIsNone(render_report.decode_state(body))

    # --- second entry triggers the same rules ---

    def test_second_entry_bad_severity_raises(self) -> None:
        bad = {**VALID_ENTRY, "severity": "medium", "fingerprint": "b" * 64}
        body = _make_marker([VALID_ENTRY, bad])
        with self.assertRaises(Refused):
            render_report.decode_state(body)

    def test_second_entry_bad_fingerprint_raises(self) -> None:
        bad = {**VALID_ENTRY, "fingerprint": "not-a-fingerprint"}
        body = _make_marker([VALID_ENTRY, bad])
        with self.assertRaises(Refused):
            render_report.decode_state(body)


if __name__ == "__main__":
    unittest.main()
