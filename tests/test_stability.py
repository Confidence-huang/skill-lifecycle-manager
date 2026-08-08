"""Prove immutable rebaseline, zero-write health, and explicit drift evidence."""

import tempfile  # Keep Git, state, backup, and activity evidence disposable.
import unittest  # Run stable acceptance without third-party test dependencies.
from pathlib import Path  # Build one complete host-local baseline fixture.
from unittest.mock import patch  # Point installed-manager identity at the fixture Git repository.

from skill_lifecycle.inventory import governance_result
from skill_lifecycle.operations import create_backup
from skill_lifecycle.paths import LifecycleBlocked
from skill_lifecycle.stability import health, stabilize
from support import create_git_skill, layout, link_directory


def prepared_host(root: Path):
    """Build one clean manager source, activity link, reports, Registry, and complete backup."""
    host = layout(root / "host")
    manager = create_git_skill(root / "manager", "skill-lifecycle-manager")
    host.activity_root.mkdir(parents=True)
    link_directory(host, manager, host.activity_root / "skill-lifecycle-manager")
    governance_result(host, True)
    create_backup(host, [manager, host.activity_root])
    return host, manager


class StabilityTests(unittest.TestCase):
    """Validate frozen local evidence without remote freshness claims."""

    def test_stabilize_preview_writes_no_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                result = stabilize(host, False, False)
            baseline_exists = host.baseline_path.exists()
        self.assertEqual(result["mutations"], 0)
        self.assertFalse(baseline_exists)

    def test_stable_baseline_uses_the_structured_manager_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            expected_repository = str(manager.resolve(strict=True))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                result = stabilize(host, False, False)

        manager_record = result["baseline"]["manager"]
        self.assertEqual(manager_record["repository"], expected_repository)
        self.assertEqual(manager_record["version"], "5.1.0")
        self.assertRegex(manager_record["sourceTree"], r"^[0-9a-f]{40}$")
        self.assertRegex(manager_record["identitySHA256"], r"^[0-9A-F]{64}$")

    def test_stabilize_apply_and_health_pass_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                stabilize(host, True, False)
            baseline_time = host.baseline_path.stat().st_mtime_ns
            result = health(host)
            baseline_time_after = host.baseline_path.stat().st_mtime_ns
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["mutations"], 0)
        self.assertEqual(baseline_time_after, baseline_time)
        self.assertEqual(result["upstreamFreshness"], "UNKNOWN_NOT_FETCHED")

    def test_existing_baseline_requires_explicit_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                stabilize(host, True, False)
                with self.assertRaises(LifecycleBlocked):
                    stabilize(host, True, False)

    def test_explicit_rebaseline_preserves_prior_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                stabilize(host, True, False)
                prior = host.baseline_path.read_bytes()
                result = stabilize(host, True, True)
            archived = Path(result["archivedBaselinePath"])
            archived_bytes = archived.read_bytes()
        self.assertEqual(archived_bytes, prior)

    def test_inventory_drift_blocks_health(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, manager = prepared_host(Path(temporary))
            with patch("skill_lifecycle.stability.manager_repository", return_value=manager):
                stabilize(host, True, False)
            (manager / "SKILL.md").write_text((manager / "SKILL.md").read_text(encoding="utf-8") + "\nDrift\n", encoding="utf-8")
            result = health(host)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["managerClean"])
        self.assertFalse(result["checks"]["inventoryFingerprint"])


if __name__ == "__main__":
    unittest.main()
