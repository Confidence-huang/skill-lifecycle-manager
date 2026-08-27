"""Prove cross-platform inventory identity and generated governance views."""

import json  # Inspect the exact machine-readable generator identity written to Registry state.
import tempfile  # Dispose every activity and state fixture after each assertion.
import unittest  # Keep acceptance dependency-free under uv.
import sys  # Keep broken-symlink evidence distinct from Windows junction coverage.
from pathlib import Path  # Create native files and activity entries.

from skill_lifecycle import __version__
from skill_lifecycle.inventory import governance_result, registry_result, report_result, scan_skills, write_registry
from support import create_skill, layout, link_directory, write_lifecycle_record


class InventoryTests(unittest.TestCase):
    """Validate physical identity and evidence publication boundaries."""

    def test_aliases_deduplicate_and_distinct_entries_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            activity = host.activity_root
            source = create_skill(root / "source/alpha", "alpha")
            activity.mkdir(parents=True)
            link_directory(host, source, activity / "alpha")
            link_directory(host, source, activity / "alpha-alias")
            create_skill(activity / "beta", "beta")
            inventory = scan_skills([activity])
        self.assertEqual(inventory["summary"]["inventory"]["physicalEntries"], 2)
        self.assertEqual({record["name"] for record in inventory["skills"]}, {"alpha", "beta"})
        self.assertEqual(len(next(record for record in inventory["skills"] if record["name"] == "alpha")["activePaths"]), 2)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Broken symbolic-link evidence is POSIX-specific.")
    def test_broken_link_is_visible_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary) / "host")
            activity = host.activity_root
            activity.mkdir(parents=True)
            link_directory(host, activity / "missing", activity / "broken")
            inventory = scan_skills([activity])
        self.assertEqual(inventory["summary"]["brokenLinks"], 1)
        self.assertEqual(inventory["skills"], [])

    def test_same_name_physical_entries_require_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            activity = Path(temporary) / "activity"
            create_skill(activity / "one", "duplicate")
            create_skill(activity / "two", "duplicate")
            inventory = scan_skills([activity])
        self.assertEqual(inventory["summary"]["inventory"]["nameCollisionGroups"], 1)
        self.assertTrue(all(record["governanceState"] == "REVIEW_REQUIRED" for record in inventory["skills"]))
        self.assertTrue(all(record["overallGrade"] == "UNRATED" for record in inventory["skills"]))

    def test_package_provenance_and_updates_are_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            activity = Path(temporary) / "activity"
            skill = create_skill(activity / "spec-kit", "spec-kit")
            lifecycle = {
                "schemaVersion": 1,
                "lifecycleMode": "PACKAGE",
                "origin": "/reviewed/package",
                "remote": None,
                "commit": None,
                "selectedSkillPath": ".",
                "installedAt": "2026-08-05T00:00:00+00:00",
                "updates": {
                    "strategy": "git-tags",
                    "repository": "https://github.com/github/spec-kit.git",
                    "tagPrefix": "v",
                    "baselineVersion": "0.13.0",
                    "baselineCommit": "9a30db484b0876cb7e5a391cf735d59bd968e985",
                    "cli": {"command": "specify", "arguments": ["version"]},
                    "packageTransaction": {
                        "driver": "uv-tool-git",
                        "distribution": "specify-cli",
                        "executable": "specify",
                        "versionArguments": ["version"],
                        "helpArguments": ["--help"],
                        "smokeArguments": [["integration", "--help"]],
                    },
                },
            }
            write_lifecycle_record(skill, lifecycle)
            observed = scan_skills([activity])["skills"][0]
        self.assertEqual(observed["origin"], "/reviewed/package")
        self.assertEqual(observed["updates"]["baselineVersion"], "0.13.0")
        self.assertEqual(observed["updates"]["packageTransaction"]["driver"], "uv-tool-git")
        self.assertEqual(observed["updates"]["baselineCommit"], "9a30db484b0876cb7e5a391cf735d59bd968e985")
        self.assertIsNotNone(observed["lifecycleSHA256"])

    def test_package_lifecycle_change_affects_inventory_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            activity = Path(temporary) / "activity"
            skill = create_skill(activity / "package", "package")
            lifecycle = {"schemaVersion": 1, "lifecycleMode": "PACKAGE", "origin": "/one"}
            write_lifecycle_record(skill, lifecycle)
            before = scan_skills([activity])["inventoryFingerprint"]
            lifecycle["origin"] = "/two"
            write_lifecycle_record(skill, lifecycle)
            after = scan_skills([activity])["inventoryFingerprint"]
        self.assertNotEqual(before, after)

    def test_invalid_package_lifecycle_record_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            activity = Path(temporary) / "activity"
            skill = create_skill(activity / "package", "package")
            (skill / ".skill-lifecycle.json").write_text("{ invalid", encoding="utf-8")
            observed = scan_skills([activity])["skills"][0]
        self.assertEqual(observed["status"], "UNKNOWN")
        self.assertTrue(any("provenance is unreadable" in issue for issue in observed["issues"]))

    def test_registry_preview_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
            create_skill(host.activity_root / "alpha", "alpha")
            result = registry_result(host)
            state_exists = host.state_root.exists()
        self.assertEqual(result["mutations"], 0)
        self.assertFalse(state_exists)

    def test_registry_apply_publishes_json_and_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
            create_skill(host.activity_root / "alpha", "alpha")
            result = write_registry(host)
            json_text = host.registry_path.read_text(encoding="utf-8")
            yaml_text = host.registry_yaml_path.read_text(encoding="utf-8")
        self.assertEqual(result["action"], "REGISTRY_WRITTEN")
        self.assertEqual(json_text, yaml_text)
        self.assertEqual(json.loads(json_text)["generator"], f"skill-lifecycle-manager/{__version__}")

    def test_report_and_governance_preview_do_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
            create_skill(host.activity_root / "alpha", "alpha")
            report = report_result(host, False)
            governance = governance_result(host, False)
            state_exists = host.state_root.exists()
        self.assertEqual((report["mutations"], governance["mutations"]), (0, 0))
        self.assertFalse(state_exists)

    def test_governance_apply_refreshes_all_generated_views(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
            create_skill(host.activity_root / "alpha", "alpha")
            result = governance_result(host, True)
            registry_exists = host.registry_path.is_file()
            capability_exists = host.capability_report_path.is_file()
            governance_exists = host.governance_report_path.is_file()
        self.assertEqual(result["mutations"], 4)
        self.assertTrue(registry_exists)
        self.assertTrue(capability_exists)
        self.assertTrue(governance_exists)


if __name__ == "__main__":
    unittest.main()
