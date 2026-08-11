"""Prove the installed manager reports one deterministic zero-write identity."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


class ManagerIdentityTests(unittest.TestCase):
    """Exercise identity through the same module entry used by the installed command."""

    def test_version_reports_package_commit_tree_and_zero_mutations(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "-m", "skill_lifecycle", "--version"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        identity = json.loads(completed.stdout)
        self.assertEqual(identity["status"], "PASS")
        self.assertEqual(identity["action"], "MANAGER_IDENTITY")
        self.assertEqual(identity["managerVersion"], "5.3.0")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", identity["sourceCommit"]))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", identity["sourceTree"]))
        self.assertTrue(re.fullmatch(r"[0-9A-F]{64}", identity["identitySHA256"]))
        self.assertEqual(Path(identity["sourcePath"]), repository)
        self.assertIsInstance(identity["sourceClean"], bool)
        self.assertEqual(identity["mutations"], 0)


if __name__ == "__main__":
    unittest.main()
