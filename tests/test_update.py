"""Prove remote preview, detached candidate validation, fast-forward, and dirty-tree blocking."""

import tempfile  # Keep bare origin and managed clones inside one disposable root.
import unittest  # Run source update acceptance with the standard library.
from pathlib import Path  # Build exact repositories and activity links.

from skill_lifecycle.inventory import write_registry
from skill_lifecycle.operations import update_skill
from skill_lifecycle.paths import LifecycleBlocked
from support import create_git_skill, git, layout, link_directory


def update_fixture(root: Path):
    """Create one origin, publisher checkout, managed checkout, and canonical Registry."""
    origin = root / "origin.git"
    git("init", "--bare", str(origin))
    publisher = create_git_skill(root / "publisher", "updatable", str(origin))
    git("push", "-u", "origin", "main", cwd=publisher)
    managed = root / "managed"
    git("clone", str(origin), str(managed))
    git("checkout", "main", cwd=managed)
    host = layout(root / "host")
    host.activity_root.mkdir(parents=True)
    link_directory(host, managed, host.activity_root / "updatable")
    write_registry(host)
    return host, publisher, managed


class UpdateTests(unittest.TestCase):
    """Validate that source updates never rewrite or bypass candidate validation."""

    def test_preview_then_apply_fast_forwards_managed_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, publisher, managed = update_fixture(Path(temporary))
            skill_file = publisher / "SKILL.md"
            skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nUpdated\n", encoding="utf-8")
            git("add", "--", "SKILL.md", cwd=publisher)
            git("commit", "-m", "update", cwd=publisher)
            candidate = git("rev-parse", "HEAD", cwd=publisher)
            git("push", "origin", "main", cwd=publisher)
            preview = update_skill(host, "updatable", False)
            applied = update_skill(host, "updatable", True)
            managed_head = git("rev-parse", "HEAD", cwd=managed)
        self.assertEqual(preview["candidate"], candidate)
        self.assertEqual(preview["mutations"], 0)
        self.assertEqual(applied["action"], "UPDATED")
        self.assertEqual(managed_head, candidate)

    def test_dirty_managed_source_is_blocked_before_remote_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, _, managed = update_fixture(Path(temporary))
            (managed / "local.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(LifecycleBlocked):
                update_skill(host, "updatable", False)
            local_text = (managed / "local.txt").read_text(encoding="utf-8")
        self.assertEqual(local_text, "keep")


if __name__ == "__main__":
    unittest.main()
