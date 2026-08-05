"""Prove Linux inventory identity, Registry preview/apply, and generated governance views."""

import tempfile  # Dispose every activity and state fixture after each assertion.
import unittest  # Keep acceptance dependency-free under uv.
from pathlib import Path  # Create native case-sensitive files and symbolic links.

from skill_lifecycle.inventory import governance_result, registry_result, report_result, scan_skills, write_registry
from support import create_skill, layout  # Reuse deterministic Skill and host fixtures.


class InventoryTests(unittest.TestCase):
    """Validate physical identity and evidence publication boundaries."""

    def test_aliases_deduplicate_and_case_distinct_entries_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            activity = root / "activity"
            source = create_skill(root / "source/alpha", "alpha")
            activity.mkdir()
            (activity / "alpha").symlink_to(source, target_is_directory=True)
            (activity / "alpha-alias").symlink_to(source, target_is_directory=True)
            create_skill(activity / "Alpha", "Alpha")
            inventory = scan_skills([activity])
        self.assertEqual(inventory["summary"]["inventory"]["physicalEntries"], 2)
        self.assertEqual({record["name"] for record in inventory["skills"]}, {"alpha", "Alpha"})
        self.assertEqual(len(next(record for record in inventory["skills"] if record["name"] == "alpha")["activePaths"]), 2)

    def test_broken_link_is_visible_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            activity = Path(temporary) / "activity"
            activity.mkdir()
            (activity / "broken").symlink_to(activity / "missing", target_is_directory=True)
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
