"""Prove remote preview, detached candidate validation, fast-forward, and dirty-tree blocking."""

import tempfile  # Keep bare origin and managed clones inside one disposable root.
import json  # Publish an explicit Guardian policy for the update approval fixture.
import unittest  # Run source update acceptance with the standard library.
from pathlib import Path  # Build exact repositories and activity links.

from skill_lifecycle.inventory import write_registry
from skill_lifecycle.guardian import approve_guardian_update, publish_guardian_policy, scan_guardian
from skill_lifecycle.operations import update_skill
from skill_lifecycle.paths import LifecycleBlocked
from support import create_git_skill, git, layout, link_directory


def update_fixture(root: Path, skill_name: str = "updatable"):
    """Create one origin, publisher checkout, managed checkout, and canonical Registry."""
    origin = root / "origin.git"
    git("init", "--bare", str(origin))
    publisher = create_git_skill(root / "publisher", skill_name, str(origin))
    git("push", "-u", "origin", "main", cwd=publisher)
    managed = root / "managed"
    git("clone", str(origin), str(managed))
    git("checkout", "main", cwd=managed)
    host = layout(root / "host")
    host.activity_root.mkdir(parents=True)
    link_directory(host, managed, host.activity_root / skill_name)
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
            policy_source = Path(temporary) / "policy.json"
            policy_source.write_text(json.dumps({
                "schemaVersion": 1,
                "documentType": "SKILL_GUARDIAN_POLICY",
                "policyVersion": "test-v1",
                "skills": [{
                    "name": "updatable",
                    "enabled": True,
                    "riskTier": "MEDIUM",
                    "updatePolicy": "REQUIRE_APPROVAL",
                    "dependencies": [],
                    "compatibilityProbe": None,
                }],
            }), encoding="utf-8")
            publish_guardian_policy(host, policy_source, True)
            scan = scan_guardian(host, apply=True, observed_at="2026-08-08T01:00:00Z")
            approval = approve_guardian_update(
                host,
                report_path=Path(scan["jsonPath"]),
                name="updatable",
                decision_id="approval-33333333-3333-4333-8333-333333333333",
                requested_by="fixture-user",
                requested_at="2026-08-08T01:01:00Z",
                decided_by="fixture-user",
                decided_at="2026-08-08T01:02:00Z",
                expires_at="2026-08-09T01:02:00Z",
                reason="Reviewed test candidate.",
                apply=True,
            )
            applied = update_skill(
                host,
                "updatable",
                True,
                Path(approval["approvalPath"]),
                "2026-08-08T02:00:00Z",
            )
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

    def test_manager_update_previews_but_apply_requires_dedicated_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host, publisher, managed = update_fixture(Path(temporary), "skill-lifecycle-manager")
            skill_file = publisher / "SKILL.md"
            skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nReviewed manager candidate\n", encoding="utf-8")
            git("add", "--", "SKILL.md", cwd=publisher)
            git("commit", "-m", "manager candidate", cwd=publisher)
            candidate = git("rev-parse", "HEAD", cwd=publisher)
            git("push", "origin", "main", cwd=publisher)

            preview = update_skill(host, "skill-lifecycle-manager", False)
            with self.assertRaisesRegex(LifecycleBlocked, "preview-only"):
                update_skill(host, "skill-lifecycle-manager", True)
            managed_head = git("rev-parse", "HEAD", cwd=managed)

        self.assertEqual(preview["candidate"], candidate)
        self.assertEqual(preview["mutations"], 0)
        self.assertNotEqual(managed_head, candidate)


if __name__ == "__main__":
    unittest.main()
