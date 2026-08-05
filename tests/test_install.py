"""Prove install preview, activation, collision refusal, and reverse cleanup."""

import tempfile  # Keep every source and destination below a disposable root.
import unittest  # Run with the Python standard library.
from pathlib import Path  # Inspect package files and activity symbolic links.

from skill_lifecycle.operations import inspect_install, install_skill
from skill_lifecycle.paths import LifecycleBlocked
from support import create_skill, layout


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
            activity_is_link = activity.is_symlink()
            same_destination = activity.resolve() == Path(installed["destination"]).resolve()
            registry_exists = host.registry_path.is_file()
        self.assertTrue(activity_is_directory)
        self.assertFalse(activity_is_link)
        self.assertTrue(same_destination)
        self.assertTrue(registry_exists)

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
