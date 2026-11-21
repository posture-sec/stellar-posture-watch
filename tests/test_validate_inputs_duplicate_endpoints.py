#!/usr/bin/env python3
"""A policy that names one endpoint twice is a mistake, and the pre-flight says so.

`check_endpoint()` looks at one entry at a time: a string, the `https` scheme, a host, no query
string. Nothing compared entries with each other, so an array that repeats a URL passed, Gauge
read the same account from the same host twice, and the report could carry one finding twice
under one fingerprint. The tracking issue then shows one row or two depending on how rows group,
and the operator is left reading a half-edited policy as a valid one.

The array is refused, not rewritten. What Gauge receives is what the file says, so a fix here is
the operator deleting a line rather than an action quietly dropping one.
"""

from __future__ import annotations

import re
import unittest

from test_validate_inputs import MINIMAL, Harness

FIRST = "https://horizon-testnet.stellar.org"
SECOND = "https://horizon.example.org"


def with_endpoints(entries: str) -> str:
    """`MINIMAL` with its one endpoint replaced by the array literal `entries`."""
    return MINIMAL.replace(f'endpoints = ["{FIRST}"]', f"endpoints = [{entries}]")


class TestDuplicateEndpoints(Harness):
    def problems(self, err: str) -> list[str]:
        return [line.removeprefix("  - ") for line in err.splitlines() if line.startswith("  - ")]

    def test_two_distinct_endpoints_pass(self) -> None:
        code, _, err = self.run_cli(config=self.policy(with_endpoints(f'"{FIRST}", "{SECOND}"')))
        self.assertEqual(code, 0, err)

    def test_an_exact_duplicate_is_refused_with_both_indexes(self) -> None:
        code, _, err = self.run_cli(config=self.policy(with_endpoints(f'"{FIRST}", "{FIRST}"')))
        self.assertEqual(code, 2, err)
        self.assertEqual(
            self.problems(err),
            [f"config gauge.toml: endpoint {FIRST} is listed twice, at index 0 and index 1"],
        )

    def test_a_repeat_after_a_distinct_entry_names_the_first_one_it_saw(self) -> None:
        text = with_endpoints(f'"{FIRST}", "{SECOND}", "{FIRST}"')
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2, err)
        self.assertEqual(
            self.problems(err),
            [f"config gauge.toml: endpoint {FIRST} is listed twice, at index 0 and index 2"],
        )

    def test_a_third_copy_reports_against_the_original(self) -> None:
        text = with_endpoints(f'"{FIRST}", "{FIRST}", "{FIRST}"')
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2, err)
        self.assertEqual(len(self.problems(err)), 2)
        self.assertIn("at index 0 and index 1", err)
        self.assertIn("at index 0 and index 2", err)

    def test_a_url_differing_only_by_a_trailing_slash_stays_accepted(self) -> None:
        # Two spellings of one host are two strings. Normalizing them here would decide what
        # Gauge is asked to read, which is the policy's business and not the pre-flight's.
        code, _, err = self.run_cli(config=self.policy(with_endpoints(f'"{FIRST}/", "{FIRST}"')))
        self.assertEqual(code, 0, err)

    def test_a_duplicate_sits_beside_the_per_entry_refusal(self) -> None:
        # Both entries are bad for their own reason and bad together, and the point of
        # collecting problems is that one pass names all three.
        text = with_endpoints('"http://horizon.invalid", "http://horizon.invalid"')
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2, err)
        self.assertEqual(len(re.findall(r"is not https", err)), 2)
        self.assertEqual(len(re.findall(r"is listed twice", err)), 1)
        self.assertIn("at index 0 and index 1", err)

    def test_two_identical_non_strings_are_not_compared(self) -> None:
        # An integer entry has no URL to quote in a message about URLs, and hashing what cannot
        # be a string to find out would report one collision where there are two bad entries.
        code, _, err = self.run_cli(config=self.policy(with_endpoints("3, 3")))
        self.assertEqual(code, 2, err)
        self.assertEqual(
            self.problems(err),
            [
                "an endpoint entry is not a string",
                "an endpoint entry is not a string",
            ],
        )

    def test_an_empty_array_keeps_its_own_message(self) -> None:
        code, _, err = self.run_cli(config=self.policy(with_endpoints("")))
        self.assertEqual(code, 2, err)
        self.assertEqual(
            self.problems(err), ["config gauge.toml: endpoints must be a non-empty array"]
        )


if __name__ == "__main__":
    unittest.main()
