#!/usr/bin/env python3
"""Tests for scripts/validate_inputs.py.

No test here reaches the network or reads a fixture from another repository. Policy
files are written into a temporary directory by the tests that need one.
"""

from __future__ import annotations

import base64
import io
import os
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_inputs  # noqa: E402

PIN = "da656733fff839d5cf20f795460f4365a7254257"
# Real testnet account ids from the captured reports in tests/fixtures, so the address
# checks below run against checksums that actually verify.
ACCOUNT = "GBQHXYDEJD6NEIUQ5NYDBVNTRCACJXMLO32JUQHBGO524NMVYOMIN5CP"
ISSUER = "GDSX2WUFUT7KCMTUNG3IUQWIUQSC4XNKQ5NTGEZRKLTMLCSJTCUVBEVG"
MULTIPART = "MDAH5J2NNNMS6PGXA4APQF6KZ2B5VH4VQ3H5T6XQF2M7K2H5T6XQF2M7K"


def strkey(version_byte: int, body: bytes) -> str:
    """Build a 56-character strkey at test time instead of committing one."""
    payload = bytes([version_byte]) + body
    checksum = validate_inputs.crc16_xmodem(payload)
    raw = payload + checksum.to_bytes(2, "little")
    return base64.b32encode(raw).decode().rstrip("=")


def fake_seed() -> str:
    return strkey(validate_inputs.VERSION_SEED, bytes(range(32)))


def lookalike_seed() -> str:
    return strkey(validate_inputs.VERSION_SEED + 1, bytes(range(32)))


MINIMAL = f"""version = 1
network = "testnet"
endpoints = ["https://horizon-testnet.stellar.org"]

[[account]]
id = "{ACCOUNT}"
name = "treasury"
"""


class Harness(unittest.TestCase):
    """Runs the CLI from inside a temporary workspace.

    The script refuses an absolute config path on purpose, so the tests have to
    address the policy file the way a workflow would: by a path inside the workspace.
    """

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self._prior = Path.cwd()
        os.chdir(self._directory.name)
        self.workspace_dir = Path(self._directory.name)

    def tearDown(self) -> None:
        os.chdir(self._prior)
        self._directory.cleanup()

    def policy(self, text: str, name: str = "gauge.toml") -> str:
        Path(name).write_text(text, encoding="utf-8")
        return name

    def run_cli(self, **overrides: Any) -> tuple[int, str, str]:
        args: dict[str, Any] = {
            "gauge_repo": "posture-sec/guage",
            "gauge_ref": PIN,
            "fail_on": "high",
            "issue_label": "account-posture",
            "title": "Account posture watch",
        }
        if "config" not in overrides:
            args["config"] = self.policy(MINIMAL)
        args.update(overrides)
        argv = [
            "--config",
            str(args["config"]),
            "--gauge-repo",
            str(args["gauge_repo"]),
            "--gauge-ref",
            str(args["gauge_ref"]),
            "--fail-on",
            str(args["fail_on"]),
            "--issue-label",
            str(args["issue_label"]),
            "--title",
            str(args["title"]),
        ]
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = validate_inputs.main(argv)
        return code, out.getvalue(), err.getvalue()


class TestHappyPath(Harness):
    def test_a_pinned_sha_and_a_small_policy_pass(self) -> None:
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertIn("gauge-ref is pinned at da65673", out)
        self.assertEqual(err, "")

    def test_two_accounts_and_a_full_passphrase_pass(self) -> None:
        text = (
            MINIMAL.replace('network = "testnet"', 'network = "Test SDF Network ; September 2015"')
            + f'\n[[account]]\nid = "{ISSUER}"\n'
        )
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 0, err)

    def test_a_mainnet_passphrase_passes_without_containing_mainnet(self) -> None:
        text = MINIMAL.replace(
            'network = "testnet"', 'network = "Public Global Stellar Network ; September 2015"'
        )
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 0, err)


class TestRefPin(Harness):
    def test_a_branch_name_is_refused(self) -> None:
        code, _, err = self.run_cli(gauge_ref="main")
        self.assertEqual(code, 2)
        self.assertIn("not a full 40-character lowercase commit sha", err)
        self.assertIn("change without this file changing", err)

    def test_a_tag_name_is_refused(self) -> None:
        code, _, err = self.run_cli(gauge_ref="v0.1.0")
        self.assertEqual(code, 2)
        self.assertIn("not a full 40-character lowercase commit sha", err)

    def test_seven_characters_is_refused_because_it_is_resolvable_but_not_pinned(self) -> None:
        code, _, err = self.run_cli(gauge_ref=PIN[:7])
        self.assertEqual(code, 2)
        self.assertIn("not a full 40-character lowercase commit sha", err)

    def test_uppercase_hex_is_refused(self) -> None:
        code, _, err = self.run_cli(gauge_ref=PIN.upper())
        self.assertEqual(code, 2)
        self.assertIn("not a full 40-character lowercase commit sha", err)

    def test_every_other_input_is_still_checked_beside_a_bad_ref(self) -> None:
        code, _, err = self.run_cli(gauge_ref="main", fail_on="critical")
        self.assertEqual(code, 2)
        self.assertEqual(len(re.findall(r"^  - ", err, re.MULTILINE)), 2)


class TestInputShapes(Harness):
    def test_a_repo_input_that_is_not_owner_slash_name(self) -> None:
        for value in ("guage", "a/b/c", "", "posture-sec/"):
            code, _, err = self.run_cli(gauge_repo=value)
            self.assertEqual(code, 2, value)
            self.assertIn("is not an owner/name pair", err)

    def test_fail_on_only_knows_the_two_severities_gauge_accepts(self) -> None:
        code, _, err = self.run_cli(fail_on="info")
        self.assertEqual(code, 2)
        self.assertIn("must be high or warn", err)

    def test_a_label_cannot_carry_a_newline(self) -> None:
        code, _, err = self.run_cli(issue_label="account\nposture")
        self.assertEqual(code, 2)
        self.assertIn("control character or a line break", err)

    def test_an_over_long_title_is_refused(self) -> None:
        code, _, err = self.run_cli(title="x" * 257)
        self.assertEqual(code, 2)
        self.assertIn("over the 256 limit", err)

    def test_an_empty_title_is_refused(self) -> None:
        code, _, err = self.run_cli(title="")
        self.assertEqual(code, 2)
        self.assertIn("title must not be empty", err)


class TestConfigPath(Harness):
    def test_an_absolute_path_is_refused(self) -> None:
        self.policy(MINIMAL)
        code, _, err = self.run_cli(config="/etc/passwd")
        self.assertEqual(code, 2)
        self.assertIn("not absolute", err)

    def test_an_absolute_path_inside_the_workspace_is_still_refused(self) -> None:
        code, _, err = self.run_cli(config=str(self.workspace_dir / "gauge.toml"))
        self.assertEqual(code, 2)
        self.assertIn("not absolute", err)

    def test_a_path_that_climbs_out_is_refused(self) -> None:
        code, _, err = self.run_cli(config="../secrets/gauge.toml")
        self.assertEqual(code, 2)
        self.assertIn("climb out of the repository", err)

    def test_a_missing_file_is_refused(self) -> None:
        code, _, err = self.run_cli(config="nowhere.toml")
        self.assertEqual(code, 2)
        self.assertIn("does not exist in the workspace", err)

    def test_a_directory_is_refused(self) -> None:
        Path("configs").mkdir()
        self.policy(MINIMAL)
        code, _, err = self.run_cli(config="configs")
        self.assertEqual(code, 2)
        self.assertIn("is not a regular file", err)


class TestPolicyFile(Harness):
    def test_not_toml(self) -> None:
        code, _, err = self.run_cli(config=self.policy("version = 1 = 2"))
        self.assertEqual(code, 2)
        self.assertIn("is not valid TOML", err)

    def test_oversized(self) -> None:
        code, _, err = self.run_cli(config=self.policy(MINIMAL + ("# " + "x" * 200 + "\n") * 6000))
        self.assertEqual(code, 2)
        self.assertIn("is over the 1048576 limit", err)

    def test_version_two_is_refused(self) -> None:
        code, _, err = self.run_cli(
            config=self.policy(MINIMAL.replace("version = 1", "version = 2"))
        )
        self.assertEqual(code, 2)
        self.assertIn("version must be 1", err)

    def test_a_missing_network_is_refused(self) -> None:
        code, _, err = self.run_cli(
            config=self.policy(MINIMAL.replace('network = "testnet"\n', ""))
        )
        self.assertEqual(code, 2)
        self.assertIn("network is required and has no default", err)

    def test_a_bogus_network_is_refused(self) -> None:
        code, _, err = self.run_cli(
            config=self.policy(MINIMAL.replace('"testnet"', '"greatestnet"'))
        )
        self.assertEqual(code, 2)
        self.assertIn("neither mainnet, testnet nor a full network passphrase", err)

    def test_an_empty_endpoints_array_is_refused(self) -> None:
        code, _, err = self.run_cli(
            config=self.policy(
                MINIMAL.replace(
                    'endpoints = ["https://horizon-testnet.stellar.org"]', "endpoints = []"
                )
            )
        )
        self.assertEqual(code, 2)
        self.assertIn("endpoints must be a non-empty array", err)

    def test_a_plain_http_endpoint_is_refused(self) -> None:
        code, _, err = self.run_cli(
            config=self.policy(
                MINIMAL.replace(
                    "https://horizon-testnet.stellar.org", "http://horizon-testnet.stellar.org"
                )
            )
        )
        self.assertEqual(code, 2)
        self.assertIn("is not https", err)

    def test_no_accounts_is_refused(self) -> None:
        head = MINIMAL.split("[[account]]")[0]
        code, _, err = self.run_cli(config=self.policy(head))
        self.assertEqual(code, 2)
        self.assertIn("at least one [[account]]", err)

    def test_an_account_that_is_not_a_table_is_refused(self) -> None:
        head = MINIMAL.split("[[account]]")[0]
        code, _, err = self.run_cli(config=self.policy(head + "account = [3]\n"))
        self.assertEqual(code, 2)
        self.assertIn("account[0] is not a table", err)

    def test_an_account_id_that_is_not_a_string_is_refused(self) -> None:
        head = MINIMAL.split("[[account]]")[0]
        code, _, err = self.run_cli(config=self.policy(head + "account = [{ id = 3 }]\n"))
        self.assertEqual(code, 2)
        self.assertIn("is not a 56-character base32 strkey", err)

    def test_a_muxed_address_gets_its_own_message(self) -> None:
        text = MINIMAL.replace(ACCOUNT, MULTIPART)
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2)
        self.assertIn("muxed M... address", err)
        self.assertNotIn("checksum", err)

    def test_a_contract_address_gets_its_own_message(self) -> None:
        contract = strkey(2 << 3, bytes(range(32)))  # version 2 encodes the C prefix
        self.assertTrue(contract.startswith("C"))
        code, _, err = self.run_cli(config=self.policy(MINIMAL.replace(ACCOUNT, contract)))
        self.assertEqual(code, 2)
        self.assertIn("contract C... address", err)

    def test_a_truncated_account_id_fails_on_checksum_not_shape(self) -> None:
        broken = ACCOUNT[:-3] + "XYZ"
        code, _, err = self.run_cli(config=self.policy(MINIMAL.replace(ACCOUNT, broken)))
        self.assertEqual(code, 2)
        self.assertIn("its checksum does not verify", err)

    def test_a_nonsense_address_fails_on_shape(self) -> None:
        code, _, err = self.run_cli(config=self.policy(MINIMAL.replace(ACCOUNT, "G" + "1" * 55)))
        self.assertEqual(code, 2)
        self.assertIn("is not a 56-character base32 strkey", err)

    def test_an_account_id_that_is_a_seed_is_named_as_one(self) -> None:
        text = MINIMAL.replace(ACCOUNT, fake_seed())
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2)
        self.assertIn("is a secret seed", err)

    def test_a_live_seed_hidden_in_a_comment_is_caught_before_the_build(self) -> None:
        text = MINIMAL + f"\n# note: {fake_seed()}\n"
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2)
        self.assertIn("treat it as a live seed and rotate it", err)

    def test_a_lookalike_is_refused_but_not_called_live(self) -> None:
        text = MINIMAL + f"\n# note: {lookalike_seed()}\n"
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2)
        self.assertIn("likely a lookalike", err)
        self.assertNotIn("rotate it", err)

    def test_the_seed_never_appears_in_the_refusal_text(self) -> None:
        secret = fake_seed()
        _, _, err = self.run_cli(config=self.policy(MINIMAL + f"\n# {secret}\n"))
        self.assertNotIn(secret, err)
        self.assertIn(f"{secret[:4]}...{secret[-4:]}", err)

    def test_every_problem_in_one_file_is_reported_in_one_pass(self) -> None:
        text = (
            'version = 7\nnetwork = "nope"\nendpoints = ["http://x"]\n\n[[account]]\nid = "G123"\n'
        )
        code, _, err = self.run_cli(config=self.policy(text))
        self.assertEqual(code, 2)
        problems = re.findall(r"^  - ", err, re.MULTILINE)
        self.assertGreaterEqual(len(problems), 4)


class TestSeedShapeDetection(unittest.TestCase):
    def test_a_longer_base32_run_ending_in_the_wrong_place_does_not_match(self) -> None:
        token = fake_seed() + "AAAA"
        self.assertEqual(validate_inputs.seed_findings(token), [])

    def test_a_seed_inside_a_longer_word_still_needs_its_boundaries(self) -> None:
        padded = "A" + fake_seed()
        self.assertEqual(validate_inputs.seed_findings(padded), [])

    def test_a_real_account_id_is_not_seed_shaped(self) -> None:
        self.assertEqual(validate_inputs.seed_findings(ACCOUNT), [])

    def test_two_tokens_in_one_blob_produce_two_messages(self) -> None:
        text = f"{fake_seed()}\n{lookalike_seed()}"
        self.assertEqual(len(validate_inputs.seed_findings(text)), 2)


if __name__ == "__main__":
    unittest.main()
