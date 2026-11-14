#!/usr/bin/env python3
"""Provenance hash manifest checks for tests/fixtures/ (task 9.7).

`tests/fixtures/README.md` states which Gauge JSON reports came from real testnet runs and
which two were hand-built from them. `TestFixtureProvenance` in `tests/test_render_report.py`
checks row presence and the `derived from` note; this suite binds each row to the raw bytes of
its `*.json` report via `hashlib.sha256` so an edit to a fixture cannot silently keep the old
provenance claim.

Run the suite:
    python -m unittest discover -s tests -t tests -p 'test_fixture_manifest.py' -v

Regenerate the markdown table rows:
    python3 tests/test_fixture_manifest.py --print-rows
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
REGEN_CMD = "python3 tests/test_fixture_manifest.py --print-rows"
REQUIRED_COLUMNS = ("File", "Origin", "sha256", "What it exercises")
LEGACY_COLUMNS = ("File", "Origin", "What it exercises")
HAND_BUILT_FIXTURES = ("report-accepted.json", "report-hostile-strings.json")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


class ManifestError(AssertionError):
    """Raised when the fixture directory and its README provenance table disagree."""


@dataclass(frozen=True, slots=True)
class ManifestRow:
    """One parsed row of the report fixture provenance table."""

    file: str
    origin: str
    sha256: str
    exercises: str


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        raise ManifestError(f"malformed markdown table row: {line!r}")
    parts = CELL_SPLIT_RE.split(stripped)
    return [cell.strip() for cell in parts[1:-1]]


def _strip_code_span(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_table_lines(readme_text: str) -> list[str]:
    lines = readme_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("| File |"):
            block: list[str] = []
            for candidate in lines[index:]:
                if not candidate.strip().startswith("|"):
                    break
                block.append(candidate)
            return block
    raise ManifestError(
        f"tests/fixtures/README.md has no '| File |' provenance table; run `{REGEN_CMD}`"
    )


def parse_manifest_table(readme_text: str) -> list[ManifestRow]:
    """Parse the four-column provenance table from `tests/fixtures/README.md`."""
    table_lines = _extract_table_lines(readme_text)
    if len(table_lines) < 3:
        raise ManifestError(
            f"provenance table has fewer than 3 lines (header, divider, rows); run `{REGEN_CMD}`"
        )

    headers = tuple(_split_markdown_row(table_lines[0]))
    if "sha256" not in headers:
        raise ManifestError(
            "provenance table in tests/fixtures/README.md is missing required 'sha256' column; "
            f"regenerate with `{REGEN_CMD}`"
        )
    if headers != REQUIRED_COLUMNS:
        raise ManifestError(
            f"provenance table columns {headers!r} do not match expected {REQUIRED_COLUMNS!r}; "
            f"regenerate with `{REGEN_CMD}`"
        )

    divider = _split_markdown_row(table_lines[1])
    if len(divider) != len(REQUIRED_COLUMNS) or not all(
        cell and set(cell) <= {"-", ":"} and "-" in cell for cell in divider
    ):
        raise ManifestError(f"malformed markdown table divider: {table_lines[1]!r}")

    rows: list[ManifestRow] = []
    seen: set[str] = set()
    for raw_line in table_lines[2:]:
        cells = _split_markdown_row(raw_line)
        if len(cells) != len(REQUIRED_COLUMNS):
            raise ManifestError(
                f"row has {len(cells)} cells, expected {len(REQUIRED_COLUMNS)}: {raw_line!r}"
            )
        name = _strip_code_span(cells[0])
        origin = cells[1].strip()
        digest = _strip_code_span(cells[2])
        exercises = cells[3].strip()
        if not name:
            raise ManifestError(f"row has empty File cell: {raw_line!r}")
        if name in seen:
            raise ManifestError(f"duplicate manifest row for {name!r}")
        if not origin:
            raise ManifestError(f"{name}: Origin cell must not be empty")
        if not exercises:
            raise ManifestError(f"{name}: 'What it exercises' cell must not be empty")
        seen.add(name)
        rows.append(ManifestRow(file=name, origin=origin, sha256=digest, exercises=exercises))

    return rows


def verify_fixture_manifest(
    fixtures_dir: Path = FIXTURES,
    hand_built: tuple[str, ...] = HAND_BUILT_FIXTURES,
) -> list[ManifestRow]:
    """Verify every `*.json` report in `fixtures_dir` against `README.md`."""
    readme_path = fixtures_dir / "README.md"
    if not readme_path.is_file():
        raise ManifestError(f"missing fixture provenance file: {readme_path}")

    rows = parse_manifest_table(readme_path.read_text(encoding="utf-8"))
    by_name = {row.file: row for row in rows}
    present_json = {path.name for path in fixtures_dir.glob("*.json") if path.is_file()}
    listed_names = set(by_name)

    unlisted = sorted(present_json - listed_names)
    missing_on_disk = sorted(listed_names - present_json)
    if unlisted or missing_on_disk:
        details: list[str] = []
        if unlisted:
            details.append(f"unlisted JSON fixture(s) missing a table row: {', '.join(unlisted)}")
        if missing_on_disk:
            details.append(
                f"manifest row(s) with no matching JSON file on disk: {', '.join(missing_on_disk)}"
            )
        raise ManifestError(f"{'; '.join(details)}. Regenerate rows with `{REGEN_CMD}`")

    for name in hand_built:
        if name in by_name and "derived" not in by_name[name].origin.lower():
            raise ManifestError(
                f"{name}: hand-built fixture row must state 'derived' in Origin, "
                f"got {by_name[name].origin!r}"
            )

    mismatches: list[str] = []
    for row in rows:
        fixture_path = fixtures_dir / row.file
        computed = _sha256_file(fixture_path)
        if not HEX64_RE.match(row.sha256):
            mismatches.append(
                f"{row.file}: invalid sha256 cell {row.sha256!r} (computed {computed})"
            )
            continue
        if computed != row.sha256:
            mismatches.append(
                f"{row.file}: manifest sha256 {row.sha256} != computed sha256 {computed}"
            )

    if mismatches:
        joined = "; ".join(mismatches)
        raise ManifestError(
            f"fixture digest mismatch: {joined}. "
            f"If the fixture regeneration was intentional, run `{REGEN_CMD}`"
        )

    return rows


def _read_existing_metadata(readme_path: Path) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Read row order and `(origin, exercises)` metadata from a 3- or 4-column table."""
    if not readme_path.is_file():
        return [], {}
    try:
        table_lines = _extract_table_lines(readme_path.read_text(encoding="utf-8"))
    except ManifestError:
        return [], {}
    if len(table_lines) < 3:
        return [], {}

    headers = tuple(_split_markdown_row(table_lines[0]))
    order: list[str] = []
    metadata: dict[str, tuple[str, str]] = {}
    for raw_line in table_lines[2:]:
        cells = _split_markdown_row(raw_line)
        if headers == REQUIRED_COLUMNS and len(cells) == 4:
            name = _strip_code_span(cells[0])
            metadata[name] = (cells[1].strip(), cells[3].strip())
            order.append(name)
        elif headers == LEGACY_COLUMNS and len(cells) == 3:
            name = _strip_code_span(cells[0])
            metadata[name] = (cells[1].strip(), cells[2].strip())
            order.append(name)
    return order, metadata


def format_manifest_table(fixtures_dir: Path = FIXTURES) -> str:
    """Render the four-column provenance markdown table with recomputed `sha256` digests."""
    readme_path = fixtures_dir / "README.md"
    existing_order, metadata = _read_existing_metadata(readme_path)
    present = {path.name: path for path in fixtures_dir.glob("*.json") if path.is_file()}

    ordered_names = [name for name in existing_order if name in present]
    ordered_names.extend(sorted(name for name in present if name not in metadata))

    lines = [
        "| File | Origin | sha256 | What it exercises |",
        "| --- | --- | --- | --- |",
    ]
    for name in ordered_names:
        origin, exercises = metadata.get(name, ("TODO: record origin", "TODO: record behaviour"))
        digest = _sha256_file(present[name])
        lines.append(f"| `{name}` | {origin} | `{digest}` | {exercises} |")
    return "\n".join(lines)


class TestFixtureManifest(unittest.TestCase):
    def _copy_fixtures_with_table(self, directory: Path, table: str | None = None) -> Path:
        target = directory / "fixtures"
        target.mkdir(parents=True, exist_ok=True)
        for path in FIXTURES.iterdir():
            if path.is_file():
                shutil.copy2(path, target / path.name)
        if table is not None:
            readme_path = target / "README.md"
            text = readme_path.read_text(encoding="utf-8")
            old_block = "\n".join(_extract_table_lines(text))
            self.assertIn(old_block, text)
            readme_path.write_text(
                text.replace(old_block, table, 1), encoding="utf-8", newline="\n"
            )
        return target

    def test_shipped_fixtures_match_provenance_manifest(self) -> None:
        rows = verify_fixture_manifest(FIXTURES)
        json_files = {path.name for path in FIXTURES.glob("*.json")}
        self.assertEqual(len(rows), 6)
        self.assertEqual({row.file for row in rows}, json_files)
        self.assertTrue((FIXTURES / "policy-unreachable-endpoint.toml").is_file())
        self.assertNotIn("policy-unreachable-endpoint.toml", {row.file for row in rows})
        for row in rows:
            self.assertRegex(row.sha256, HEX64_RE)
            self.assertEqual(row.sha256, _sha256_file(FIXTURES / row.file))

    def test_absent_sha256_column_fails(self) -> None:
        legacy_table = "\n".join(
            [
                "| File | Origin | What it exercises |",
                "| --- | --- | --- |",
                "| `report-clean.json` | real run | clean path |",
            ]
        )
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), legacy_table)
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("sha256", message)
        self.assertIn(REGEN_CMD, message)

    def test_missing_row_for_existing_fixture_fails(self) -> None:
        full_lines = format_manifest_table(FIXTURES).splitlines()
        without_warn = "\n".join(line for line in full_lines if "`report-warn.json`" not in line)
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), without_warn)
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("report-warn.json", message)
        self.assertIn(REGEN_CMD, message)

    def test_unlisted_extra_json_file_fails(self) -> None:
        valid_table = format_manifest_table(FIXTURES)
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), valid_table)
            (fixtures_dir / "report-extra.json").write_bytes(b"{}\n")
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("report-extra.json", message)
        self.assertIn(REGEN_CMD, message)

    def test_row_referencing_missing_file_on_disk_fails(self) -> None:
        valid_table = format_manifest_table(FIXTURES)
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), valid_table)
            (fixtures_dir / "report-clean.json").unlink()
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("report-clean.json", message)
        self.assertIn(REGEN_CMD, message)

    def test_hand_built_row_must_say_derived(self) -> None:
        rewritten = format_manifest_table(FIXTURES).replace(
            "derived from `report-findings.json`",
            "real run, ledger 5535642, exit 1",
        )
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), rewritten)
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("report-accepted.json", message)
        self.assertIn("derived", message)

    def test_one_byte_change_fails_naming_both_digests_and_regeneration_command(self) -> None:
        valid_table = format_manifest_table(FIXTURES)
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), valid_table)
            target_file = fixtures_dir / "report-clean.json"
            original_bytes = target_file.read_bytes()
            expected_digest = hashlib.sha256(original_bytes).hexdigest()

            flipped_last = b" " if original_bytes[-1:] != b" " else b"\n"
            mutated_bytes = original_bytes[:-1] + flipped_last
            self.assertEqual(len(mutated_bytes), len(original_bytes))
            self.assertNotEqual(mutated_bytes, original_bytes)
            target_file.write_bytes(mutated_bytes)
            computed_digest = hashlib.sha256(mutated_bytes).hexdigest()

            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)

        message = str(ctx.exception)
        self.assertIn("report-clean.json", message)
        self.assertIn(expected_digest, message)
        self.assertIn(computed_digest, message)
        self.assertIn(REGEN_CMD, message)

    def test_malformed_digest_cell_fails_with_computed_digest(self) -> None:
        original_digest = _sha256_file(FIXTURES / "report-warn.json")
        corrupted_table = format_manifest_table(FIXTURES).replace(
            f"`{original_digest}`", "`not-a-sha256`", 1
        )
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), corrupted_table)
            with self.assertRaises(ManifestError) as ctx:
                verify_fixture_manifest(fixtures_dir)
        message = str(ctx.exception)
        self.assertIn("report-warn.json", message)
        self.assertIn("not-a-sha256", message)
        self.assertIn(original_digest, message)
        self.assertIn(REGEN_CMD, message)

    def test_print_rows_cli_round_trips_and_skips_policy_toml(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--print-rows"],
            check=True,
            capture_output=True,
            text=True,
        )
        rendered_table = proc.stdout.strip()
        self.assertTrue(rendered_table.startswith("| File | Origin | sha256 | What it exercises |"))
        self.assertNotIn("policy-unreachable-endpoint.toml", rendered_table)
        with TemporaryDirectory() as tmp:
            fixtures_dir = self._copy_fixtures_with_table(Path(tmp), rendered_table)
            rows = verify_fixture_manifest(fixtures_dir)
        self.assertEqual(len(rows), 6)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--print-rows" in args:
        parser = argparse.ArgumentParser(
            description="Print the report fixture provenance markdown table with sha256 digests."
        )
        parser.add_argument(
            "--print-rows",
            action="store_true",
            help="Print the four-column provenance table to stdout.",
        )
        parser.add_argument(
            "--fixtures-dir",
            type=Path,
            default=FIXTURES,
            help="Directory holding README.md and the *.json report fixtures.",
        )
        parsed = parser.parse_args(args)
        print(format_manifest_table(parsed.fixtures_dir))
        return 0

    unittest.main(argv=[sys.argv[0], *args])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
