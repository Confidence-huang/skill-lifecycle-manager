"""Prove configured PACKAGE release checks are semantic, bounded, and zero-write."""

import json  # Snapshot canonical Registry bytes around read-only checks.
import tempfile  # Keep package and Git-tag fixtures below one disposable root.
import unittest  # Run freshness acceptance with the Python standard library.
from pathlib import Path  # Create exact package, Registry, and upstream paths.
from unittest.mock import patch  # Control CLI discovery without changing the process PATH.

from skill_lifecycle.cli import parser  # Prove the public trigger accepts one name or all configured packages.
from skill_lifecycle.freshness import check_updates  # Exercise the PACKAGE release evidence command.
from skill_lifecycle.inventory import write_registry  # Publish one isolated canonical Registry fixture.
from support import create_skill, git, layout, write_lifecycle_record  # Build deterministic local package and Git evidence.


# --- Create a stable-tag upstream without network access ---
def create_release_repository(root: Path) -> Path:
    repository = root / "upstream"
    repository.mkdir()  # One normal repository is enough for local git ls-remote.
    git("init", "-b", "main", cwd=repository)
    git("config", "user.name", "Fixture", cwd=repository)
    git("config", "user.email", "fixture@localhost", cwd=repository)
    (repository / "README.md").write_text("release fixture\n", encoding="utf-8")
    git("add", "--", "README.md", cwd=repository)
    git("commit", "-m", "initial", cwd=repository)
    for tag in ("v0.13.0", "v0.15.2", "v0.16.0", "v0.17.0-rc.1", "newsletter"):
        git("tag", tag, cwd=repository)  # Stable and ignored tags share one immutable commit.
    return repository


# --- Publish one configured PACKAGE into an isolated Registry ---
def freshness_fixture(root: Path):
    host = layout(root / "host")
    package = create_skill(host.activity_root / "spec-kit", "spec-kit")
    upstream = create_release_repository(root)
    write_lifecycle_record(
        package,
        {
            "schemaVersion": 1,
            "lifecycleMode": "PACKAGE",
            "origin": "/reviewed/spec-kit",
            "updates": {
                "strategy": "git-tags",
                "repository": str(upstream),
                "tagPrefix": "v",
                "baselineVersion": "0.13.0",
                "cli": {"command": "specify", "arguments": ["version"]},
            },
        },
    )
    write_registry(host)  # The freshness command consumes canonical Registry evidence only.
    return host


class FreshnessTests(unittest.TestCase):
    """Validate release discovery without fetch, install, upgrade, or state writes."""

    def test_missing_cli_uses_adapter_baseline_and_reports_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = freshness_fixture(Path(temporary))
            before = host.registry_path.read_bytes()
            with patch("skill_lifecycle.freshness.shutil.which", return_value=None):
                result = check_updates(host, "spec-kit")
                batch = check_updates(host, None)
            after = host.registry_path.read_bytes()
        update = result["updates"][0]
        self.assertEqual(update["cliStatus"], "NOT_INSTALLED")
        self.assertEqual(update["currentVersion"], "0.13.0")
        self.assertEqual(update["currentVersionSource"], "ADAPTER_BASELINE")
        self.assertEqual(update["latestVersion"], "0.16.0")
        self.assertEqual(update["updateStatus"], "UPDATE_AVAILABLE")
        self.assertEqual(result["mutations"], 0)
        self.assertEqual(batch["summary"]["checked"], 1)
        self.assertEqual(batch["updates"][0]["updateStatus"], "UPDATE_AVAILABLE")
        self.assertEqual(batch["mutations"], 0)
        self.assertEqual(before, after)

    def test_installed_cli_version_overrides_adapter_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = freshness_fixture(root)
            executable = root / "specify"
            executable.write_text("#!/bin/sh\nprintf 'specify-cli 0.16.0\\n'\n", encoding="utf-8")
            executable.chmod(0o755)
            with patch("skill_lifecycle.freshness.shutil.which", return_value=str(executable)):
                result = check_updates(host, "spec-kit")
        update = result["updates"][0]
        self.assertEqual(update["cliStatus"], "INSTALLED")
        self.assertEqual(update["currentVersionSource"], "CLI")
        self.assertEqual(update["updateStatus"], "CURRENT")

    def test_named_package_without_update_contract_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
            create_skill(host.activity_root / "plain", "plain")
            write_registry(host)
            result = check_updates(host, "plain")
        self.assertEqual(result["updates"][0]["updateStatus"], "NOT_CONFIGURED")
        self.assertEqual(result["mutations"], 0)

    def test_cli_requires_name_or_all(self) -> None:
        parsed_name = parser().parse_args(["updates", "--name", "spec-kit"])
        parsed_all = parser().parse_args(["updates", "--all"])
        self.assertEqual(parsed_name.name, "spec-kit")
        self.assertTrue(parsed_all.all_skills)


if __name__ == "__main__":
    unittest.main()
