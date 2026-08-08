"""Prove daily Guardian scans stay observational and approvals bind exact source updates."""

from __future__ import annotations  # Keep fixture annotations stable on Python 3.12.

import json  # Build explicit policy documents and inspect generated evidence.
import sys  # Declare the exact test interpreter instead of depending on a bare Python alias.
import tempfile  # Keep every Registry, report, repository, and approval below a disposable root.
import unittest  # Run Guardian acceptance with the dependency-light standard library.
from pathlib import Path  # Preserve exact local paths in Registry and report evidence.

from jsonschema import Draft202012Validator, FormatChecker  # Prove published Guardian evidence matches its public contract.

from skill_lifecycle.cli import parser  # Prove the nested public command surface stays reachable.
from skill_lifecycle.guardian import approve_guardian_update, publish_guardian_policy, scan_guardian
from skill_lifecycle.inventory import write_registry  # Build the canonical observed-state fixture.
from skill_lifecycle.operations import update_skill  # Prove approval gates the existing transaction.
from skill_lifecycle.paths import LifecycleBlocked  # Assert literal safety stops.
from support import create_git_skill, git, layout, link_directory  # Reuse cross-platform Skill fixtures.


# --- Create one managed source with a newer remote commit ---
def guardian_fixture(root: Path):
    """Return an isolated host, publisher, managed source, and exact remote candidate."""
    origin = root / "origin.git"  # The bare repository stands in for a network update channel.
    git("init", "--bare", str(origin))
    publisher = create_git_skill(root / "publisher", "guarded", str(origin))
    git("push", "-u", "origin", "main", cwd=publisher)
    managed = root / "managed"  # The active clone remains at the reviewed first commit.
    git("clone", str(origin), str(managed))
    git("checkout", "main", cwd=managed)

    host = layout(root / "host")
    host.activity_root.mkdir(parents=True)
    link_directory(host, managed, host.activity_root / "guarded")
    write_registry(host)

    skill_file = publisher / "SKILL.md"  # Publish one candidate only after Registry captures current.
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nCandidate\n", encoding="utf-8")
    git("add", "--", "SKILL.md", cwd=publisher)
    git("commit", "-m", "candidate", cwd=publisher)
    candidate = git("rev-parse", "HEAD", cwd=publisher)
    git("push", "origin", "main", cwd=publisher)
    return host, managed, candidate


# --- Build one explicit monitoring policy ---
def guardian_policy() -> dict:
    """Return a safe policy that can notify but can never authorize unattended updates."""
    return {
        "schemaVersion": 1,
        "documentType": "SKILL_GUARDIAN_POLICY",
        "policyVersion": "fixture-v1",
        "skills": [
            {
                "name": "guarded",
                "enabled": True,
                "riskTier": "HIGH",
                "updatePolicy": "REQUIRE_APPROVAL",
                "dependencies": [{"name": "python", "command": sys.executable, "arguments": ["--version"]}],
                "compatibilityProbe": None,
            }
        ],
    }


class GuardianContractTests(unittest.TestCase):
    """Keep Guardian desired state and evidence beneath one dedicated state subtree."""

    def test_host_layout_exposes_guardian_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            host = layout(Path(temporary))
        self.assertEqual(host.guardian_policy_path, host.state_root / "guardian" / "policy.json")
        self.assertEqual(host.guardian_latest_json_path, host.state_root / "guardian" / "latest.json")
        self.assertEqual(host.guardian_latest_markdown_path, host.state_root / "guardian" / "latest.md")
        self.assertEqual(host.guardian_history_root, host.state_root / "guardian" / "reports")
        self.assertEqual(host.guardian_approval_root, host.state_root / "guardian" / "approvals")

    def test_policy_matches_public_schema_and_cli_exposes_all_guardian_actions(self) -> None:
        schema_root = Path(__file__).resolve().parents[1] / "schemas"
        policy_schema = json.loads((schema_root / "guardian-policy.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(policy_schema, format_checker=FormatChecker()).iter_errors(guardian_policy()))
        actions = [
            parser().parse_args(["guardian", "policy", "--file", "policy.json"]).guardian_command,
            parser().parse_args(["guardian", "scan"]).guardian_command,
            parser().parse_args(["guardian", "approve", "--report", "report.json", "--name", "guarded", "--decision-id", "approval-11111111-1111-4111-8111-111111111111", "--requested-by", "user", "--requested-at", "2026-08-08T01:00:00Z", "--decided-by", "user", "--decided-at", "2026-08-08T01:01:00Z", "--expires-at", "2026-08-09T01:01:00Z", "--reason", "reviewed"]).guardian_command,
            parser().parse_args(["guardian", "schedule"]).guardian_command,
        ]
        self.assertEqual(errors, [])
        self.assertEqual(actions, ["policy", "scan", "approve", "schedule"])


class GuardianScanTests(unittest.TestCase):
    """Require daily checks to report evidence without changing managed Skill state."""

    def test_policy_preview_is_zero_write_and_apply_publishes_one_canonical_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            source = root / "policy.json"
            source.write_text(json.dumps(guardian_policy()), encoding="utf-8")
            preview = publish_guardian_policy(host, source, False)
            self.assertFalse(host.guardian_policy_path.exists())
            applied = publish_guardian_policy(host, source, True)
        self.assertEqual(preview["mutations"], 0)
        self.assertEqual(applied["mutations"], 1)

    def test_scan_reports_update_and_unknown_compatibility_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, managed, candidate = guardian_fixture(root)
            source = root / "policy.json"
            source.write_text(json.dumps(guardian_policy()), encoding="utf-8")
            publish_guardian_policy(host, source, True)
            current = git("rev-parse", "HEAD", cwd=managed)
            git_before = (managed / ".git" / "FETCH_HEAD").read_bytes() if (managed / ".git" / "FETCH_HEAD").exists() else None

            preview = scan_guardian(host, apply=False, observed_at="2026-08-08T01:02:03Z")
            git_after = (managed / ".git" / "FETCH_HEAD").read_bytes() if (managed / ".git" / "FETCH_HEAD").exists() else None

            self.assertFalse(host.guardian_latest_json_path.exists())
            applied = scan_guardian(host, apply=True, observed_at="2026-08-08T01:02:03Z")
            repeated = scan_guardian(host, apply=False, observed_at="2026-08-09T01:02:03Z")

            report_schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "guardian-report.schema.json").read_text(encoding="utf-8"))
            report_errors = list(Draft202012Validator(report_schema, format_checker=FormatChecker()).iter_errors(applied["report"]))

        row = preview["report"]["skills"][0]
        self.assertEqual(row["current"], current)
        self.assertEqual(row["candidate"], candidate)
        self.assertEqual(row["updateStatus"], "UPDATE_AVAILABLE")
        self.assertEqual(row["compatibilityStatus"], "UNKNOWN")
        self.assertEqual(row["dependencyChangeStatus"], "UNKNOWN")
        self.assertEqual(repeated["report"]["skills"][0]["dependencyChangeStatus"], "UNCHANGED")
        self.assertEqual(row["action"], "MANUAL_REVIEW")
        self.assertEqual(preview["mutations"], 0)
        self.assertEqual(applied["mutations"], 4)
        self.assertEqual(git_before, git_after)
        self.assertEqual(report_errors, [])


class GuardianApprovalTests(unittest.TestCase):
    """Require one immutable approval to match every mutable update fact."""

    def test_source_update_requires_exact_unexpired_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, managed, candidate = guardian_fixture(root)
            source = root / "policy.json"
            source.write_text(json.dumps(guardian_policy()), encoding="utf-8")
            publish_guardian_policy(host, source, True)
            scan = scan_guardian(host, apply=True, observed_at="2026-08-08T01:02:03Z")

            with self.assertRaisesRegex(LifecycleBlocked, "approval"):
                update_skill(host, "guarded", True)

            approval = approve_guardian_update(
                host,
                report_path=Path(scan["jsonPath"]),
                name="guarded",
                decision_id="approval-11111111-1111-4111-8111-111111111111",
                requested_by="fixture-user",
                requested_at="2026-08-08T01:05:00Z",
                decided_by="fixture-user",
                decided_at="2026-08-08T01:06:00Z",
                expires_at="2026-08-09T01:06:00Z",
                reason="Reviewed candidate evidence.",
                apply=True,
            )
            result = update_skill(
                host,
                "guarded",
                True,
                approval_path=Path(approval["approvalPath"]),
                evaluated_at="2026-08-08T02:00:00Z",
            )
            updated = git("rev-parse", "HEAD", cwd=managed)

            approval_schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "update-approval.schema.json").read_text(encoding="utf-8"))
            approval_errors = list(Draft202012Validator(approval_schema, format_checker=FormatChecker()).iter_errors(approval["approval"]))

        self.assertEqual(result["action"], "UPDATED")
        self.assertEqual(updated, candidate)
        self.assertEqual(approval_errors, [])

    def test_expired_approval_is_blocked_before_fetch_or_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, managed, _ = guardian_fixture(root)
            source = root / "policy.json"
            source.write_text(json.dumps(guardian_policy()), encoding="utf-8")
            publish_guardian_policy(host, source, True)
            scan = scan_guardian(host, apply=True, observed_at="2026-08-08T01:02:03Z")
            approval = approve_guardian_update(
                host,
                report_path=Path(scan["jsonPath"]),
                name="guarded",
                decision_id="approval-22222222-2222-4222-8222-222222222222",
                requested_by="fixture-user",
                requested_at="2026-08-08T01:05:00Z",
                decided_by="fixture-user",
                decided_at="2026-08-08T01:06:00Z",
                expires_at="2026-08-08T01:30:00Z",
                reason="Short review window.",
                apply=True,
            )
            before = git("rev-parse", "HEAD", cwd=managed)
            with self.assertRaisesRegex(LifecycleBlocked, "expired"):
                update_skill(
                    host,
                    "guarded",
                    True,
                    approval_path=Path(approval["approvalPath"]),
                    evaluated_at="2026-08-08T02:00:00Z",
                )
            after = git("rev-parse", "HEAD", cwd=managed)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
