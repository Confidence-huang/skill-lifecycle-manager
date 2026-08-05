"""Prove preview, physical hashing, link recording, and safe empty restore."""

import json  # Inspect the completed version-1 backup manifest.
import tempfile  # Keep recovery fixtures disposable.
import unittest  # Run without third-party dependencies.
from pathlib import Path  # Create executable files and symbolic links.

from skill_lifecycle.operations import backup_preview, create_backup, restore_backup
from skill_lifecycle.paths import LifecycleBlocked
from support import layout


class BackupRestoreTests(unittest.TestCase):
    """Validate that backup never follows links and restore never recreates them."""

    def test_backup_preview_counts_without_creating_backup_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = root / "source"
            source.mkdir()
            (source / "data.txt").write_text("safe", encoding="utf-8")
            (source / "data-link").symlink_to(source / "data.txt")
            result = backup_preview(host, [source])
            backup_exists = (host.data_root / "backups").exists()
        self.assertEqual((result["fileCount"], result["linkCount"]), (1, 1))
        self.assertFalse(backup_exists)

    def test_link_aware_backup_and_empty_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = root / "source"
            source.mkdir()
            executable = source / "run.sh"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            (source / "run-link").symlink_to(executable)
            result = create_backup(host, [source])
            backup = Path(result["backupPath"])
            manifest = json.loads((backup / "backup-manifest.json").read_text(encoding="utf-8"))
            restored = root / "restored"
            preview = restore_backup(backup, restored, False)
            applied = restore_backup(backup, restored, True)
            restored_file = restored / manifest["files"][0]["backupRelative"]
            restored_mode = restored_file.stat().st_mode & 0o777
        self.assertEqual(preview["mutations"], 0)
        self.assertEqual(result["linkCount"], 1)
        self.assertEqual(restored_mode, 0o755)
        self.assertEqual(len(applied["linksForReview"]), 1)

    def test_backup_refuses_recursive_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            host.data_root.mkdir(parents=True)
            with self.assertRaises(LifecycleBlocked):
                create_backup(host, [root])
            backup_exists = (host.data_root / "backups").exists()
        self.assertFalse(backup_exists)

    def test_restore_rejects_path_traversal_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = root / "source"
            source.mkdir()
            (source / "data.txt").write_text("safe", encoding="utf-8")
            backup = Path(create_backup(host, [source])["backupPath"])
            manifest_path = backup / "backup-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["backupRelative"] = "../escape.txt"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(LifecycleBlocked):
                restore_backup(backup, root / "restored", True)
            restored_exists = (root / "restored").exists()
        self.assertFalse(restored_exists)

    def test_restore_refuses_nonempty_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = root / "source"
            source.mkdir()
            (source / "data.txt").write_text("safe", encoding="utf-8")
            backup = Path(create_backup(host, [source])["backupPath"])
            target = root / "target"
            target.mkdir()
            (target / "existing.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(LifecycleBlocked):
                restore_backup(backup, target, True)
            existing_text = (target / "existing.txt").read_text(encoding="utf-8")
        self.assertEqual(existing_text, "keep")


if __name__ == "__main__":
    unittest.main()
