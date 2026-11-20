#!/usr/bin/env python3
"""Test that action.yml's config default matches the example workflow and README.

Per Issue #83 and decisions D-02 / D-09:
Reads text without YAML parsers and verifies that:
1. action.yml declares default: .posture/gauge.toml
2. example/workflow.yml specifies config: .posture/gauge.toml
3. README.md specifies config: .posture/gauge.toml
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDocsConfigDefault(unittest.TestCase):
    def test_config_defaults_match_across_docs_and_action(self) -> None:
        action_text = (ROOT / "action.yml").read_text(encoding="utf-8")
        workflow_text = (ROOT / "example" / "workflow.yml").read_text(encoding="utf-8")
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

        # 1. Extract action.yml default for config
        # Looking in inputs -> config -> default
        action_match = re.search(
            r"^\s+config:\n(?:[ ]{4}.*\n)*?[ ]{4}default:\s*(\S+)",
            action_text,
            re.MULTILINE,
        )
        self.assertIsNotNone(action_match, "Could not find default for config in action.yml")
        action_default = action_match.group(1)

        # 2. Extract example/workflow.yml config path
        workflow_match = re.search(r"^\s+config:\s*(\S+)", workflow_text, re.MULTILINE)
        self.assertIsNotNone(workflow_match, "Could not find config in example/workflow.yml")
        workflow_config = workflow_match.group(1)

        # 3. Extract README.md usage config path
        readme_match = re.search(r"^\s+config:\s*(\S+)", readme_text, re.MULTILINE)
        self.assertIsNotNone(readme_match, "Could not find config in README.md")
        readme_config = readme_match.group(1)

        expected = ".posture/gauge.toml"
        self.assertEqual(
            (action_default, workflow_config, readme_config),
            (expected, expected, expected),
            f"Config paths do not agree: action.yml={action_default!r}, "
            f"workflow.yml={workflow_config!r}, README.md={readme_config!r}",
        )


if __name__ == "__main__":
    unittest.main()
