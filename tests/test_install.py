"""Prove install preview, PACKAGE provenance, activation, collision refusal, and reverse cleanup."""

import json  # Read the installed PACKAGE provenance contract as exact evidence.
import tempfile  # Keep every source and destination below a disposable root.
import unittest  # Run with the Python standard library.
from pathlib import Path  # Inspect package files and activity symbolic links.

from skill_lifecycle.operations import inspect_install, install_skill
from skill_lifecycle.paths import LifecycleBlocked
from support import create_git_skill, create_skill, layout


class InstallTests(unittest.TestCase):
    """Validate one-entity activation and transaction-owned rollback."""

    def test_install_preview_leaves_live_roots_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "example")
            result = inspect_install(host, str(package), "package", None)
            activity_exists = host.activity_root.exists()
            data_exists = host.data_root.exists()
            state_exists = host.state_root.exists()
        self.assertEqual(result["action"], "INSTALL_PREVIEW")
        self.assertFalse(activity_exists)
        self.assertFalse(data_exists)
        self.assertFalse(state_exists)

    def test_package_install_creates_one_entity_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "example")
            installed = install_skill(host, str(package), "package")
            activity = Path(installed["activityPath"])
            activity_is_directory = activity.is_dir()
            activity_is_link = host.platform.is_directory_link(activity)
            same_destination = activity.resolve() == Path(installed["destination"]).resolve()
            registry_exists = host.registry_path.is_file()
            lifecycle = json.loads((activity / ".skill-lifecycle.json").read_text(encoding="utf-8"))
        self.assertTrue(activity_is_directory)
        self.assertFalse(activity_is_link)
        self.assertTrue(same_destination)
        self.assertTrue(registry_exists)
        self.assertEqual(lifecycle["lifecycleMode"], "PACKAGE")
        self.assertEqual(lifecycle["origin"], str(package))

    def test_source_install_uses_the_native_activity_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = create_git_skill(root / "source", "linked-source")
            installed = install_skill(host, str(source), "source")
            activity = Path(installed["activityPath"])
            destination = Path(installed["destination"])
            link_is_native = host.platform.is_directory_link(activity)
            resolved_target = activity.resolve(strict=True)
        self.assertTrue(link_is_native)
        self.assertEqual(resolved_target, destination.resolve())
        self.assertEqual(installed["mode"], "SOURCE")

    def test_package_install_preserves_valid_update_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "example")
            lifecycle = {
                "schemaVersion": 1,
                "lifecycleMode": "PACKAGE",
                "origin": "/publisher/source",
                "updates": {
                    "strategy": "git-tags",
                    "repository": "https://example.invalid/example.git",
                    "tagPrefix": "v",
                    "baselineVersion": "1.2.3",
                    "cli": {"command": "example", "arguments": ["version"]},
                },
            }
            (package / ".skill-lifecycle.json").write_text(json.dumps(lifecycle), encoding="utf-8")
            installed = install_skill(host, str(package), "package")
            record = json.loads((Path(installed["activityPath"]) / ".skill-lifecycle.json").read_text(encoding="utf-8"))
        self.assertEqual(record["origin"], str(package))
        self.assertEqual(record["updates"], lifecycle["updates"])

    def test_existing_activity_is_a_hard_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "example")
            install_skill(host, str(package), "package")
            with self.assertRaises(LifecycleBlocked):
                inspect_install(host, str(package), "package", None)

    def test_invalid_source_creates_no_live_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            invalid = root / "invalid"
            invalid.mkdir()
            with self.assertRaises(LifecycleBlocked):
                install_skill(host, str(invalid), "package")
            activity_exists = host.activity_root.exists()
            data_exists = host.data_root.exists()
        self.assertFalse(activity_exists)
        self.assertFalse(data_exists)

    def test_invalid_package_provenance_is_blocked_during_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "example")
            (package / ".skill-lifecycle.json").write_text("{ invalid", encoding="utf-8")
            with self.assertRaises(LifecycleBlocked):
                inspect_install(host, str(package), "package", None)
            live_roots_exist = host.activity_root.exists() or host.state_root.exists()
        self.assertFalse(live_roots_exist)

    def test_registry_failure_rolls_back_activity_and_entity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            package = create_skill(root / "package", "rollback-example")
            host.state_root.parent.mkdir(parents=True)
            host.state_root.write_text("collision", encoding="utf-8")
            with self.assertRaises(OSError):
                install_skill(host, str(package), "package")
            activity_exists = (host.activity_root / "rollback-example").exists()
            destination_exists = (host.data_root / "packages/rollback-example").exists()
        self.assertFalse(activity_exists)
        self.assertFalse(destination_exists)


if __name__ == "__main__":
    unittest.main()
