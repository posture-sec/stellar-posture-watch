from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestReadmeMetrics(unittest.TestCase):
    def test_script_discovers_the_complete_suite_without_pythonpath(self) -> None:
        loader = unittest.TestLoader()
        expected = loader.discover(str(ROOT / "tests")).countTestCases()
        self.assertEqual(loader.errors, [])
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        code = (
            "import json,sys,unittest; "
            "sys.path[0]=sys.argv[1]; "
            "import sync_readme; "
            "count=sync_readme.count_tests(); "
            "print(json.dumps([count, unittest.defaultTestLoader.errors]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "scripts")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        count, errors = json.loads(result.stdout)
        self.assertEqual(errors, [])
        self.assertEqual(count, expected)


if __name__ == "__main__":
    unittest.main()
