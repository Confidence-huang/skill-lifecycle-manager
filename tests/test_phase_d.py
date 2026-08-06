"""Prove the reviewed Phase D approval-to-rollback chain inside disposable Linux roots."""

from __future__ import annotations  # Keep fixture annotations stable on Python 3.12.

import hashlib  # Bind synthetic evidence reports and state canaries to exact bytes.
import json  # Create machine-valid manifest, evidence, and probe-plan fixtures.
import subprocess  # Query fixture Git identity without a shell command string.
import sys  # Use the accepted candidate interpreter for bounded subprocess probes.
import tempfile  # Keep every decision, lock, transaction, activity, and Registry below one root.
import unittest  # Run the pilot fault matrix with the existing regression suite.
from pathlib import Path  # Express exact fixture and transaction paths.
from unittest.mock import patch  # Inject failures before activation and Registry publication.

from jsonschema import Draft202012Validator, FormatChecker  # Validate every durable V5 event.

from skill_lifecycle.contracts import build_artifact_identity, compute_artifact_id, compute_tree_sha256
from skill_lifecycle.inventory import governance_result
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, sha256_file
from skill_lifecycle.pilot import activate_pilot, approve_pilot, read_decisions, rollback_pilot, verify_pilot
from skill_lifecycle.shadow import committed_tree_entries
from support import create_git_skill, create_skill
from test_contracts import load_schemas


REMOTE = "https://example.invalid/oil-tone.git"  # A local fixture remote never requires network access.
EVIDENCE_ID = "evidence-11111111-1111-4111-8111-111111111111"
APPROVAL_ID = "decision-11111111-1111-4111-8111-111111111111"
REVOCATION_ID = "decision-22222222-2222-4222-8222-222222222222"
TRANSACTION_ID = "transaction-33333333-3333-4333-8333-333333333333"


# --- Hash one fixture file in the lowercase V5 representation ---
def lower_sha256(path: Path) -> str:
    """Return the V5 lowercase form while the v4 helper retains its uppercase contract."""
    return sha256_file(path).lower()


# --- Build one complete synthetic artifact and PASS provenance record ---
def artifact_evidence(root: Path, repository: Path) -> tuple[Path, Path, str]:
    """Publish exact Phase B-style inputs for the clean committed fixture repository."""
    commit = subprocess_git(repository, "rev-parse", "HEAD")
    tree = committed_tree_entries(repository)
    identity = build_artifact_identity("GIT", REMOTE, commit, ".", compute_tree_sha256(tree))
    artifact_id = compute_artifact_id(identity)
    manifest = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_ARTIFACT_MANIFEST",
        "artifactID": artifact_id,
        "skillName": "oil-tone",
        "identity": identity,
        "treeEntries": tree,
    }
    shadow = root / "shadow"
    report_path = shadow / "shadow-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text('{"fixture":"phase-d"}\n', encoding="utf-8")
    evidence = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_EVIDENCE",
        "evidenceID": EVIDENCE_ID,
        "artifactID": artifact_id,
        "skillName": "oil-tone",
        "kind": "PROVENANCE",
        "tool": "phase-d-fixture",
        "toolVersion": "1",
        "policyVersion": "v5-phase-b-shadow-v1",
        "generatedAt": "2026-08-07T00:00:00Z",
        "hostID": "fixture-host",
        "probeStatus": "PASS",
        "findingCounts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 1, "unknown": 0},
        "reportSHA256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "reportPath": "shadow-report.json",
        "diagnostics": ["Synthetic provenance passed."],
    }
    manifest_path = shadow / "artifacts" / artifact_id.removeprefix("sha256:") / "manifest.json"
    evidence_path = shadow / "evidence" / artifact_id.removeprefix("sha256:") / f"{EVIDENCE_ID}.json"
    manifest_path.parent.mkdir(parents=True)
    evidence_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return manifest_path, evidence_path, artifact_id


# --- Keep Git fixture commands explicit and shell-free ---
def subprocess_git(repository: Path, *arguments: str) -> str:
    """Return stdout from one successful local Git identity query."""
    completed = subprocess.run(["git", "-C", str(repository), *arguments], text=True, capture_output=True, check=False)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()

class PhaseDPilotTests(unittest.TestCase):
    """Exercise approval, collision, interruption, verification, exact restoration, and retry."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the offline V5 Schema registry once for durable-event validation."""
        cls.schemas, cls.schema_registry = load_schemas()

    # --- Prepare one host whose formal four-file state is already healthy and frozen ---
    def fixture(self, root: Path, *, apply_approval: bool = True) -> dict:
        """Return all exact request inputs while keeping the pilot source outside activity."""
        host_root = root / "host"
        host = HostLayout(
            host_root / ".agents/skills",
            host_root / "data",
            host_root / "state",
            host_root / "cache",
        )  # The USER-scope assertion must exercise the same path shape as the frozen Ubuntu runbook.
        create_skill(host.activity_root / "canary", "canary")
        governance_result(host, True)
        host.baseline_path.write_text('{"frozen":true}\n', encoding="utf-8")
        repository = create_git_skill(root / "publisher", "oil-tone", REMOTE)
        manifest_path, evidence_path, artifact_id = artifact_evidence(root, repository)
        approval = {
            "manifestPath": manifest_path,
            "evidencePath": evidence_path,
            "hostID": "fixture-host",
            "decisionID": APPROVAL_ID,
            "requestedBy": "fixture-user",
            "requestedAt": "2026-08-07T00:00:00Z",
            "decidedBy": "fixture-user",
            "decidedAt": "2026-08-07T00:01:00Z",
            "expiresAt": "2026-08-07T02:00:00Z",
            "reason": "Authorize one disposable Phase D fixture pilot.",
        }
        if apply_approval:
            approve_pilot(host, approval, True)
        activation = {
            "manifestPath": manifest_path,
            "evidencePath": evidence_path,
            "repositoryPath": repository,
            "decisionID": APPROVAL_ID,
            "transactionID": TRANSACTION_ID,
            "startedAt": "2026-08-07T00:02:00Z",
            "evaluatedAt": "2026-08-07T00:03:00Z",
            "executedBy": "fixture-agent",
            "expectedRegistrySHA256": lower_sha256(host.registry_path),
            "expectedBaselineSHA256": lower_sha256(host.baseline_path),
        }
        rollback = {
            "transactionID": TRANSACTION_ID,
            "decisionID": REVOCATION_ID,
            "decidedBy": "fixture-user",
            "decidedAt": "2026-08-07T00:10:00Z",
            "reason": "Complete the temporary pilot and return to inactive state.",
        }
        return {
            "host": host,
            "repository": repository,
            "manifestPath": manifest_path,
            "evidencePath": evidence_path,
            "artifactID": artifact_id,
            "approval": approval,
            "activation": activation,
            "rollback": rollback,
        }

    # --- Prove preview writes nothing and applied approval matches both Schemas ---
    def test_approval_preview_then_apply_publishes_decision_and_active_lock(self) -> None:
        """Keep preview zero-write, then retain one artifact/evidence-bound approval and lock."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary), apply_approval=False)
            host = fixture["host"]
            preview = approve_pilot(host, fixture["approval"], False)
            v5_exists_after_preview = host.v5_root.exists()
            applied = approve_pilot(host, fixture["approval"], True)
            retried = approve_pilot(host, fixture["approval"], True)
            decision = read_decisions(host)[0]
            lock = json.loads(host.capability_lock_path.read_text(encoding="utf-8"))
            lock_history = list(host.capability_lock_history_root.glob("capability-lock-r*.json"))
        self.assertEqual(preview["mutations"], 0)
        self.assertFalse(v5_exists_after_preview)
        self.assertEqual(applied["action"], "PILOT_APPROVED")
        self.assertEqual(retried["mutations"], 0)
        self.assert_document_valid("approval-decision.schema.json", decision)
        self.assert_document_valid("capability-lock.schema.json", lock)
        self.assertEqual(len(lock_history), 1)
        self.assertEqual(lock["entries"][0]["desiredActivity"], "ACTIVE")

    # --- Prove the complete green path ends inactive with byte-identical formal state ---
    def test_activate_verify_rollback_restores_exact_state_and_retry_is_idempotent(self) -> None:
        """Activate once, run positive/negative probes, roll back, and accept an exact retry."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root)
            host = fixture["host"]
            before = {name: path.read_bytes() for name, path in formal_paths(host).items()}
            activation_preview = activate_pilot(host, fixture["activation"], False)
            activated = activate_pilot(host, fixture["activation"], True)
            plan = write_probe_plan(root, fixture["artifactID"], passes=True)
            verification = verify_pilot(host, TRANSACTION_ID, plan, True)
            retained_plan = json.loads((host.transaction_root / TRANSACTION_ID / "probe-plan.json").read_text(encoding="utf-8"))
            retained_evidence = json.loads((host.transaction_root / TRANSACTION_ID / "probe-evidence.json").read_text(encoding="utf-8"))
            retained_plan_sha256 = lower_sha256(host.transaction_root / TRANSACTION_ID / "probe-plan.json")
            verification_retry = verify_pilot(host, TRANSACTION_ID, plan, True)
            rollback_preview = rollback_pilot(host, fixture["rollback"], False)
            rolled_back = rollback_pilot(host, fixture["rollback"], True)
            retry = rollback_pilot(host, fixture["rollback"], True)
            after = {name: path.read_bytes() for name, path in formal_paths(host).items()}
            lock = json.loads(host.capability_lock_path.read_text(encoding="utf-8"))
            lock_revisions = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(host.capability_lock_history_root.glob("capability-lock-r*.json"))
            ]
            transactions = [
                read_transaction(host, "transaction-start.json"),
                read_transaction(host, "transaction-activated.json"),
                read_transaction(host, "transaction-verified.json"),
                read_transaction(host, "transaction-rollback.json"),
            ]
            decisions = read_decisions(host)
        self.assertEqual(activation_preview["mutations"], 0)
        self.assertEqual(activated["registrySummary"]["status"]["PASS"], 2)
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification_retry["action"], "PILOT_VERIFY_ALREADY_COMPLETE")
        self.assertEqual(verification_retry["mutations"], 0)
        self.assertEqual(retained_evidence["planSHA256"], retained_plan_sha256)
        self.assert_document_valid("pilot-probe-plan.schema.json", retained_plan)
        self.assert_document_valid("pilot-probe-evidence.schema.json", retained_evidence)
        self.assertEqual(rollback_preview["mutations"], 0)
        self.assertEqual(rolled_back["action"], "PILOT_ROLLED_BACK")
        self.assertEqual(retry["action"], "PILOT_ROLLBACK_ALREADY_COMPLETE")
        self.assertEqual(before, after)
        self.assertFalse((host.activity_root / "oil-tone").exists())
        self.assertEqual(lock["entries"][0]["desiredActivity"], "INACTIVE")
        self.assertEqual([item["entries"][0]["desiredActivity"] for item in lock_revisions], ["ACTIVE", "INACTIVE"])
        for lock_revision in lock_revisions:
            self.assert_document_valid("capability-lock.schema.json", lock_revision)
        self.assertEqual([item["decision"] for item in decisions], ["APPROVED", "REVOKED"])
        for transaction in transactions:
            self.assert_document_valid("transaction.schema.json", transaction)

    # --- Block stale or mismatched approval before a transaction directory exists ---
    def test_stale_or_mismatched_approval_creates_no_transaction(self) -> None:
        """Reject changed decision identity and post-expiry evaluation with zero activation writes."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.fixture(Path(temporary))
            host = fixture["host"]
            mismatched = {**fixture["activation"], "decisionID": REVOCATION_ID}
            expired = {**fixture["activation"], "evaluatedAt": "2026-08-07T03:00:00Z"}
            with self.assertRaises(LifecycleBlocked):
                activate_pilot(host, mismatched, False)
            with self.assertRaises(LifecycleBlocked):
                activate_pilot(host, expired, False)
            transaction_exists = host.transaction_root.exists()
        self.assertFalse(transaction_exists)

    # --- Refuse both physical and link activity collisions before transaction publication ---
    def test_activity_collisions_preserve_existing_entries(self) -> None:
        """Leave a physical or symbolic-link same-name entry unchanged when activation is requested."""
        for link_collision in (False, True):
            with self.subTest(link_collision=link_collision), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = self.fixture(root)
                host = fixture["host"]
                activity = host.activity_root / "oil-tone"
                if link_collision:
                    existing = create_skill(root / "existing", "existing")
                    try:
                        activity.symlink_to(existing, target_is_directory=True)
                    except OSError as error:
                        self.skipTest(f"Host cannot create an unprivileged symbolic link: {error}")
                    before = str(activity.resolve())
                else:
                    create_skill(activity, "existing")
                    before = (activity / "SKILL.md").read_bytes()
                with self.assertRaises(LifecycleBlocked):
                    activate_pilot(host, fixture["activation"], False)
                after = str(activity.resolve()) if link_collision else (activity / "SKILL.md").read_bytes()
                self.assertEqual(after, before)
                self.assertFalse(host.transaction_root.exists())

    # --- Recover explicit interruption before and after activity creation ---
    def test_interruption_boundaries_restore_preimages_and_canary(self) -> None:
        """Use the durable start event to recover both no-link and link-before-Registry failures."""
        injections = ("before-link", "after-link")
        for injection in injections:
            with self.subTest(injection=injection), tempfile.TemporaryDirectory() as temporary:
                fixture = self.fixture(Path(temporary))
                host = fixture["host"]
                before = {name: path.read_bytes() for name, path in formal_paths(host).items()}
                if injection == "before-link":
                    context = patch("skill_lifecycle.pilot.os.symlink", side_effect=OSError("injected before link"))
                else:
                    context = patch("skill_lifecycle.pilot.publish_registry_views", side_effect=OSError("injected before Registry"))
                with context, self.assertRaises(OSError):
                    activate_pilot(host, fixture["activation"], True)
                start_exists = (host.transaction_root / TRANSACTION_ID / "transaction-start.json").is_file()
                rollback_pilot(host, fixture["rollback"], True)
                after = {name: path.read_bytes() for name, path in formal_paths(host).items()}
                self.assertTrue(start_exists)
                self.assertEqual(after, before)
                self.assertTrue((host.activity_root / "canary/SKILL.md").is_file())
                self.assertFalse((host.activity_root / "oil-tone").exists())

    # --- Retain a failed probe and still restore exact state ---
    def test_probe_failure_is_recorded_before_explicit_rollback(self) -> None:
        """Publish BLOCKED probe evidence, then return to the prior activity and Registry bytes."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root)
            host = fixture["host"]
            before = {name: path.read_bytes() for name, path in formal_paths(host).items()}
            activate_pilot(host, fixture["activation"], True)
            plan = write_probe_plan(root, fixture["artifactID"], passes=False)
            verification = verify_pilot(host, TRANSACTION_ID, plan, True)
            evidence_path = host.transaction_root / TRANSACTION_ID / "probe-evidence.json"
            retained_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            rollback_pilot(host, fixture["rollback"], True)
            after = {name: path.read_bytes() for name, path in formal_paths(host).items()}
        self.assertEqual(verification["status"], "BLOCKED")
        self.assertEqual(retained_evidence["status"], "BLOCKED")
        self.assert_document_valid("pilot-probe-evidence.schema.json", retained_evidence)
        self.assertEqual(after, before)

    # --- Validate one durable document through the offline Schema registry ---
    def assert_document_valid(self, schema_name: str, document: dict) -> None:
        """Fail with exact Schema diagnostics when a pilot record drifts from Phase A."""
        validator = Draft202012Validator(
            self.schemas[schema_name],
            registry=self.schema_registry,
            format_checker=FormatChecker(),
        )
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))


# --- Return the four formal files governed by the pilot transaction ---
def formal_paths(host) -> dict[str, Path]:
    """Give tests a stable byte-for-byte before/after map."""
    return {
        "registry": host.registry_path,
        "yaml": host.registry_yaml_path,
        "capability": host.capability_report_path,
        "governance": host.governance_report_path,
    }


# --- Publish a small generic no-shell probe plan ---
def write_probe_plan(root: Path, artifact_id: str, *, passes: bool) -> Path:
    """Create positive and expected-negative commands, or one deliberate expectation mismatch."""
    expected_text = "positive" if passes else "missing"
    plan = {
        "schemaVersion": 1,
        "documentType": "PILOT_PROBE_PLAN",
        "artifactID": artifact_id,
        "skillName": "oil-tone",
        "timeoutSeconds": 30,
        "probes": [
            {
                "name": "positive",
                "command": ["${PYTHON}", "-c", "print('positive')"],
                "stdin": None,
                "expectedExitCode": 0,
                "stdoutContains": [expected_text],
            },
            {
                "name": "expected-negative",
                "command": [sys.executable, "-c", "import sys; print('negative'); sys.exit(1)"],
                "stdin": None,
                "expectedExitCode": 1,
                "stdoutContains": ["negative"],
            },
        ],
    }
    path = root / "probe-plan.json"
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


# --- Read one transaction event for Schema validation ---
def read_transaction(host, filename: str) -> dict:
    """Return one immutable event from the selected fixture transaction."""
    path = host.transaction_root / TRANSACTION_ID / filename
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
