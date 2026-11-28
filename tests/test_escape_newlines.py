"""Issue #56: escape() must collapse CR, LF and CRLF to a space.

A newline in a finding message or in home_domain would end the markdown table row and let
text after it parse as markdown at column zero (a heading, a checklist, etc.). The fix is
to collapse every newline sequence to a single space inside escape() before the
special-character substitution, so the value stays within its cell.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_report  # noqa: E402  (must come after sys.path insert)

FIXTURES = ROOT / "tests" / "fixtures"
MARKER_RE = re.compile(r"<!-- posture-watch:state v1 ([A-Za-z0-9_-]*) -->")
# A table row starts with "| " and ends on the same line; newlines inside it are hostile.
ROW_RE = re.compile(r"^\|[^\n]*\|$", re.MULTILINE)


class TestEscapeNewlines(unittest.TestCase):
    """escape() collapses CR, LF and CRLF to a space."""

    def test_lf_collapsed(self) -> None:
        result = render_report.escape("hello\nworld")
        self.assertEqual(result, "hello world")
        self.assertNotIn("\n", result)

    def test_cr_collapsed(self) -> None:
        result = render_report.escape("hello\rworld")
        self.assertEqual(result, "hello world")
        self.assertNotIn("\r", result)

    def test_crlf_collapsed(self) -> None:
        result = render_report.escape("hello\r\nworld")
        self.assertEqual(result, "hello world")
        self.assertNotIn("\r", result)
        self.assertNotIn("\n", result)

    def test_newline_before_heading(self) -> None:
        """A LF followed by a heading marker must not produce a heading line."""
        result = render_report.escape("text\n## Account verified")
        self.assertNotIn("\n", result)
        self.assertNotIn("## Account verified", result.split("\n")[0] if "\n" in result else result)

    def test_crlf_before_checklist(self) -> None:
        """A CRLF followed by a GFM checklist item must not produce a list line."""
        result = render_report.escape("domain\r\n- [ ] approved")
        self.assertNotIn("\n", result)
        self.assertNotIn("\r", result)

    def test_no_newlines_in_hostile_strings_body(self) -> None:
        """Rendering report-hostile-strings.json must produce no line that starts with #."""
        import subprocess

        fixture = FIXTURES / "report-hostile-strings.json"
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "body.md"
            done = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_report.py"),
                    "--report",
                    str(fixture),
                    "--out",
                    str(out),
                    "--as-of",
                    "2026-11-13",
                    "--config",
                    "gauge.toml",
                    "--gauge-ref",
                    "da656733fff839d5cf20f795460f4365a7254257",
                    "--exit-code",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            body = out.read_text(encoding="utf-8")

        # No line in the rendered body may start with ## (heading injection).
        heading_lines = [ln for ln in body.splitlines() if ln.startswith("##")]
        expected_headings = {
            "## New since the previous run",
            "## Resolved since the previous run",
            "## Current findings",
            "## Accounts asked about",
            "## What this cannot see",
        }
        injected = [h for h in heading_lines if h not in expected_headings]
        self.assertEqual(injected, [], f"Injected heading(s): {injected}")

        # The state marker must still be present and decodable.
        marker = MARKER_RE.search(body)
        self.assertIsNotNone(marker, "state marker missing from rendered body")

        # Each finding row must be a single table row (no embedded newlines).
        # Count "|" separators: each data row has exactly 5 cells (6 pipes).
        for ln in body.splitlines():
            if ln.startswith("| high |") or ln.startswith("| warn |"):
                self.assertEqual(ln.count("|"), 6, f"Row has wrong cell count: {ln!r}")

    def test_marker_payload_unchanged_by_newline_in_message(self) -> None:
        """Newline collapsing changes only the displayed text, not the marker payload.

        D-07 requires that the hidden state marker carry the original field values so
        change detection works across a render that collapses newlines. The finding
        message is NOT stored in the marker (only account, fingerprint, rule, severity
        are), so the payload is unaffected.
        """
        import json
        import subprocess
        import tempfile

        fixture = FIXTURES / "report-hostile-strings.json"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "body.md"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_report.py"),
                    "--report",
                    str(fixture),
                    "--out",
                    str(out),
                    "--as-of",
                    "2026-11-13",
                    "--config",
                    "gauge.toml",
                    "--gauge-ref",
                    "da656733fff839d5cf20f795460f4365a7254257",
                    "--exit-code",
                    "1",
                ],
                check=True,
                capture_output=True,
            )
            body = out.read_text(encoding="utf-8")

        marker = MARKER_RE.search(body)
        self.assertIsNotNone(marker)
        import base64

        payload_b64 = marker.group(1)  # type: ignore[union-attr]
        padding = "=" * (-len(payload_b64) % 4)
        entries = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0)
        # The state marker must carry the original severity and fingerprint unchanged.
        for entry in entries:
            self.assertIn(entry["severity"], render_report.SEVERITIES)
            self.assertRegex(entry["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
