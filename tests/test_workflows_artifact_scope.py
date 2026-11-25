#!/usr/bin/env python3
"""Tests that the diagnostics artifact belongs to the audit's own failure (#82).

The upload step ran `if: failure() || steps.gauge.outputs.exit-code == '2' || ... == '3'`. The
`failure()` half cannot describe the audit: that step ends `exit 0` and publishes its status
through an output, so it always looks successful to the runner. What `failure()` actually caught
was the checkout, the Go install, the build, the render and the write step — and on a render
refusal the artifact was a stderr file from an audit that had succeeded, filed under a name that
said nothing about which run shape produced it. The condition is now the two audit codes alone,
and the name carries the code.

The step is read out of `action.yml` by the same text scanner the checker uses, so a rename or a
reorder is a failure here rather than a test that quietly stopped asserting anything.

Run: python3 -m unittest discover -s tests -t tests
"""

from __future__ import annotations

import unittest
from pathlib import Path

from action_fixture import check_action

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "action.yml"

UPLOAD = "Upload Gauge's diagnostics"
AUDIT = "Run the audit"
EXIT_CODE = "steps.gauge.outputs.exit-code"
CONDITION = f"{EXIT_CODE} == '2' || {EXIT_CODE} == '3'"


class StepReader(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ACTION.read_text(encoding="utf-8")
        self.spans = dict(
            (body[0].strip(), "\n".join(body))
            for _, body in check_action.step_spans(self.text.splitlines())
        )

    def step(self, needle: str) -> str:
        matches = [body for header, body in self.spans.items() if needle in header]
        self.assertEqual(len(matches), 1, f"{needle!r} matched {len(matches)} steps")
        return matches[0]


class TestUploadCondition(StepReader):
    def test_condition_is_the_two_audit_codes(self) -> None:
        self.assertIn(f"      if: {CONDITION}", self.step(UPLOAD))

    def test_failure_is_not_part_of_the_condition(self) -> None:
        # The audit reports through an output and exits 0, so `failure()` never means "the audit
        # failed"; it means something before it did, and then the artifact is a lie about which.
        self.assertNotIn("failure()", self.step(UPLOAD))

    def test_the_condition_is_written_once(self) -> None:
        self.assertEqual(self.step(UPLOAD).count("      if:"), 1)

    def test_name_carries_the_audit_exit_code(self) -> None:
        self.assertIn(
            f"        name: gauge-diagnostics-audit-exit-${{{{ {EXIT_CODE} }}}}", self.step(UPLOAD)
        )

    def test_name_does_not_stop_at_the_stem(self) -> None:
        # `gauge-diagnostics` alone cannot tell an exit-2 policy refusal from an exit-3 read
        # failure, which is the difference the run history is for.
        self.assertNotIn("        name: gauge-diagnostics\n", self.step(UPLOAD))

    def test_the_other_upload_properties_are_untouched(self) -> None:
        step = self.step(UPLOAD)
        self.assertIn("        path: ${{ runner.temp }}/gauge-stderr.log", step)
        self.assertIn("        if-no-files-found: ignore", step)
        self.assertIn("        retention-days: 7", step)

    def test_the_artifact_stays_the_only_carrier_of_stderr(self) -> None:
        # CONTRIBUTING: the stderr never reaches the log, so dropping the upload would lose it.
        self.assertIn("actions/upload-artifact@", self.step(UPLOAD))


class TestGaugeIdIsUnique(StepReader):
    def test_the_audit_step_carries_the_id(self) -> None:
        self.assertIn("      id: gauge", self.step(AUDIT))

    def test_no_other_step_declares_it(self) -> None:
        # The condition resolves through this id, so a second `id: gauge` would make the artifact
        # read another step's output.
        declared = [
            header for header, body in self.spans.items() if "      id: gauge\n" in f"{body}\n"
        ]
        self.assertEqual(declared, [f"- name: {AUDIT}"])

    def test_the_audit_still_ends_zero(self) -> None:
        # Out of scope for #82 and the reason `failure()` was never the right term: the step that
        # writes the stderr reports through outputs, not through its exit status.
        self.assertIn("exit 0", self.step(AUDIT))


if __name__ == "__main__":
    unittest.main()
