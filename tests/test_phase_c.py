"""
Exercise V5 Phase C failure recovery only inside disposable HOME/XDG-style roots.

The suite runs real candidate install and update operations, injects failures at final Registry
publication, and verifies exact canary bytes, commits, links, and Registry state. It also checks the
pure artifact-bound approval gate and the explicit inspect-before-apply recovery boundary.
"""

from __future__ import annotations  # Keep annotations stable on Python 3.12.

import copy  # Derive stale approval cases without mutating the valid fixture record.
import hashlib  # Compare pre-existing canary and Registry bytes across failure paths.
import os  # Supply isolated child-process roots and create the Linux link-collision case.
import subprocess  # Launch the hard-exit child fixture without shell interpolation.
import sys  # Reuse the candidate virtual-environment Python for the child process.
import tempfile  # Keep every Phase C mutation under a disposable directory.
import unittest  # Run focused fault scenarios with the standard test runner.
from pathlib import Path  # Express transaction, activity, source, and canary paths explicitly.
from unittest.mock import patch  # Inject bounded Registry failures without editing host state.

from jsonschema import Draft202012Validator, FormatChecker  # Prove the durable recovery record matches the frozen V5 Schema.

from skill_lifecycle.contracts import ContractBlocked, require_current_approval  # Prove stale decisions cannot authorize artifacts.
from skill_lifecycle.inventory import write_registry  # Create one prior canonical Registry inside fixtures.
from skill_lifecycle.operations import inspect_install, install_skill, update_skill  # Exercise real candidate transaction boundaries.
from skill_lifecycle.paths import LifecycleBlocked, atomic_json  # Publish durable fixture evidence and assert hard stops.
from skill_lifecycle.recovery import apply_recovery, inspect_recovery  # Require read-only assessment before cleanup.
from support import create_skill, git, layout  # Build deterministic Skills, Git state, and host roots.
from tests.test_contracts import load_schemas  # Reuse the offline Schema registry without network access.
from test_update import update_fixture  # Reuse the accepted origin/publisher/managed update topology.


APPROVAL_ID = "decision-11111111-1111-4111-8111-111111111111"  # Stable fixture authority identifier.
ARTIFACT_A = f"sha256:{'a' * 64}"  # Current artifact approved by the valid decision.
ARTIFACT_B = f"sha256:{'b' * 64}"  # Changed artifact that must invalidate the old approval.
TRANSACTION_ID = "transaction-44444444-4444-4444-8444-444444444444"  # Stable interrupted transaction ID.


# --- Hash one canary file exactly ---
def file_sha256(path: Path) -> str:
    """Return lowercase SHA256 for byte-preservation assertions."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Build one valid append-only approval record ---
def approved_decision() -> dict:
    """Return an artifact-bound approval with evidence and a future expiry."""
    return {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_APPROVAL_DECISION",
        "decisionID": APPROVAL_ID,
        "artifactID": ARTIFACT_A,
        "skillName": "phase-c-skill",
        "requestedBy": "phase-c-user",
        "requestedAt": "2026-08-07T00:00:00Z",
        "decision": "APPROVED",
        "decidedBy": "phase-c-user",
        "decidedAt": "2026-08-07T00:01:00Z",
        "policyVersion": "phase-c-policy-v1",
        "evidenceRefs": ["evidence-22222222-2222-4222-8222-222222222222"],
        "reason": "Synthetic Phase C behavior fixture.",
        "expiresAt": "2026-08-08T00:00:00Z",
        "supersedesDecisionID": None,
    }


# --- Build one recoverable interrupted transaction record ---
def interrupted_transaction(created_path: str) -> dict:
    """Return a Schema-compatible IN_PROGRESS transaction with one declared created path."""
    return {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_TRANSACTION",
        "transactionID": TRANSACTION_ID,
        "action": "INSTALL",
        "skillName": "interrupted",
        "approvalDecisionID": APPROVAL_ID,
        "beforeArtifactID": None,
        "afterArtifactID": ARTIFACT_A,
        "startedAt": "2026-08-07T00:02:00Z",
        "endedAt": None,
        "executedBy": "phase-c-fixture",
        "createdPaths": [created_path],
        "modifiedPaths": [],
        "steps": [{"name": "activate", "status": "PENDING", "detail": "Registry publication pending."}],
        "rollbackPlan": {"type": "REMOVE_CREATED_PATHS", "backupRef": None},
        "rollbackResult": None,
        "finalStatus": "IN_PROGRESS",
    }


@unittest.skipUnless(sys.platform.startswith("linux"), "Reviewed Phase C recovery remains Linux-only.")
class PhaseCBehaviorTests(unittest.TestCase):
    """Prove interruption, rollback, collision, approval, and canary boundaries."""

    # --- Recover one hard-exit install only after explicit inspection ---
    def test_hard_exit_requires_inspection_then_removes_only_created_path(self) -> None:
        """Leave an entity through `os._exit`, inspect it, then preserve its sibling canary on recovery."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_root = root / "host"
            host_root.mkdir()
            package = create_skill(root / "package", "interrupted")
            canary = create_skill(host_root / "activity/canary", "canary") / "SKILL.md"
            canary_before = file_sha256(canary)
            transaction_path = root / "transaction.json"
            transaction = interrupted_transaction("activity/interrupted")
            schemas, schema_registry = load_schemas()
            validator = Draft202012Validator(
                schemas["transaction.schema.json"],
                registry=schema_registry,
                format_checker=FormatChecker(),
            )  # Validate the same durable record that later authorizes bounded recovery.
            self.assertEqual(list(validator.iter_errors(transaction)), [])
            atomic_json(transaction_path, transaction)

            environment = os.environ.copy()
            environment["PHASE_C_HOST_ROOT"] = str(host_root)
            environment["PHASE_C_PACKAGE_ROOT"] = str(package)
            child = Path(__file__).with_name("phase_c_child.py")
            completed = subprocess.run([sys.executable, str(child)], env=environment, check=False)
            residual = host_root / "activity/interrupted"
            self.assertEqual(completed.returncode, 86)
            self.assertTrue(residual.is_dir())
            self.assertFalse((host_root / "state/skills-registry.json").exists())

            preview = inspect_recovery(transaction_path, host_root)
            self.assertEqual(preview["mutations"], 0)
            self.assertEqual(preview["present"], [True])
            self.assertTrue(residual.is_dir())
            recovered = apply_recovery(transaction_path, host_root)

            self.assertEqual(recovered["mutations"], 1)
            self.assertFalse(residual.exists())
            self.assertEqual(file_sha256(canary), canary_before)
            self.assertTrue(transaction_path.is_file())

    # --- Roll back install after final Registry publication fails ---
    def test_install_registry_failure_preserves_prior_registry_and_canary(self) -> None:
        """Remove the new PACKAGE entity while keeping prior observed state byte-identical."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            canary = create_skill(host.activity_root / "canary", "canary") / "SKILL.md"
            write_registry(host)
            registry_before = host.registry_path.read_bytes()
            canary_before = file_sha256(canary)
            package = create_skill(root / "package", "registry-failure")

            with patch("skill_lifecycle.operations.write_registry", side_effect=OSError("injected final write failure")):
                with self.assertRaises(OSError):
                    install_skill(host, str(package), "package")

            self.assertFalse((host.activity_root / "registry-failure").exists())
            self.assertEqual(host.registry_path.read_bytes(), registry_before)
            self.assertEqual(file_sha256(canary), canary_before)

    # --- Restore the prior clean commit when update publication fails ---
    def test_update_registry_failure_restores_prior_commit_and_registry(self) -> None:
        """Return a fast-forwarded fixture to its exact clean pre-apply identity after final-write failure."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                host, publisher, managed = update_fixture(root)
            except OSError as error:
                self.skipTest(f"Host cannot create the SOURCE activity symbolic link: {error}")
            prior_commit = git("rev-parse", "HEAD", cwd=managed)
            prior_registry = host.registry_path.read_bytes()
            canary = root / "canary.txt"
            canary.write_text("preserve phase c canary\n", encoding="utf-8")
            canary_before = file_sha256(canary)
            skill_file = publisher / "SKILL.md"
            skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nCandidate update\n", encoding="utf-8")
            git("add", "--", "SKILL.md", cwd=publisher)
            git("commit", "-m", "phase c update", cwd=publisher)
            git("push", "origin", "main", cwd=publisher)

            with patch("skill_lifecycle.guardian.require_guardian_approval", return_value={}):
                with patch("skill_lifecycle.operations.write_registry", side_effect=OSError("injected final write failure")):
                    with self.assertRaises(OSError):
                        update_skill(host, "updatable", True)

            self.assertEqual(git("rev-parse", "HEAD", cwd=managed), prior_commit)
            self.assertEqual(git("status", "--porcelain=v1", cwd=managed), "")
            self.assertEqual(host.registry_path.read_bytes(), prior_registry)
            self.assertEqual(file_sha256(canary), canary_before)

    # --- Block a physical activity collision before writes ---
    def test_activity_collision_preserves_existing_entity(self) -> None:
        """Refuse a same-name PACKAGE before creating data, state, or recovery evidence."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            existing = create_skill(host.activity_root / "collision", "collision") / "SKILL.md"
            existing_before = file_sha256(existing)
            package = create_skill(root / "package", "collision")

            with self.assertRaises(LifecycleBlocked):
                inspect_install(host, str(package), "package", None)

            self.assertEqual(file_sha256(existing), existing_before)
            self.assertFalse(host.registry_path.exists())
            self.assertFalse(host.data_root.exists())

    # --- Block a symbolic-link activity collision without retargeting it ---
    def test_link_collision_preserves_existing_target(self) -> None:
        """Keep an existing activity link byte-for-byte when the requested name collides."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            existing = create_skill(root / "existing", "linked-collision")
            host.activity_root.mkdir(parents=True)
            activity = host.activity_root / "linked-collision"
            try:
                activity.symlink_to(existing, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Host cannot create an unprivileged symbolic link: {error}")
            target_before = os.readlink(activity)
            package = create_skill(root / "package", "linked-collision")

            with self.assertRaises(LifecycleBlocked):
                inspect_install(host, str(package), "package", None)

            self.assertTrue(activity.is_symlink())
            self.assertEqual(os.readlink(activity), target_before)
            self.assertFalse(host.registry_path.exists())

    # --- Reject old approval across mismatch, expiry, and revocation ---
    def test_stale_approval_never_authorizes_changed_artifact(self) -> None:
        """Accept only the current artifact-bound record and keep every stale variant write-free."""
        valid = approved_decision()
        accepted = require_current_approval([valid], APPROVAL_ID, ARTIFACT_A, "2026-08-07T01:00:00Z")
        self.assertEqual(accepted["decisionID"], APPROVAL_ID)

        with self.assertRaises(ContractBlocked):
            require_current_approval([valid], APPROVAL_ID, ARTIFACT_B, "2026-08-07T01:00:00Z")
        expired = copy.deepcopy(valid)
        expired["expiresAt"] = "2026-08-07T00:30:00Z"
        with self.assertRaises(ContractBlocked):
            require_current_approval([expired], APPROVAL_ID, ARTIFACT_A, "2026-08-07T01:00:00Z")
        revoked = copy.deepcopy(valid)
        revoked.update(
            {
                "decisionID": "decision-33333333-3333-4333-8333-333333333333",
                "decision": "REVOKED",
                "decidedAt": "2026-08-07T00:40:00Z",
                "evidenceRefs": [],
                "expiresAt": None,
                "supersedesDecisionID": APPROVAL_ID,
            }
        )
        with self.assertRaises(ContractBlocked):
            require_current_approval([valid, revoked], APPROVAL_ID, ARTIFACT_A, "2026-08-07T01:00:00Z")

    # --- Refuse an escaping recovery record before deletion ---
    def test_unsafe_recovery_path_preserves_canary(self) -> None:
        """Block parent traversal with zero mutations and leave the neighboring canary intact."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = root / "owner"
            owner.mkdir()
            canary = root / "canary.txt"
            canary.write_text("outside owner\n", encoding="utf-8")
            canary_before = file_sha256(canary)
            transaction_path = root / "unsafe-transaction.json"
            atomic_json(transaction_path, interrupted_transaction("../canary.txt"))

            with self.assertRaises(LifecycleBlocked):
                inspect_recovery(transaction_path, owner)

            self.assertEqual(file_sha256(canary), canary_before)
            self.assertTrue(transaction_path.is_file())


if __name__ == "__main__":
    unittest.main()
