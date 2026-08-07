"""Exercise manager promotion through one exact plan and disposable Linux roots."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from skill_lifecycle.manager_promotion import execute_manager_promotion, preview_manager_promotion
from skill_lifecycle.paths import LifecycleBlocked
from support import git, layout


STATE_NAMES = (
    "skills-registry.json",
    "skills-registry.yaml",
    "skill-capability-report.md",
    "skill-governance-report.md",
    "skill-stability-baseline.json",
)


def sha256(path: Path) -> str:
    """Return uppercase host-evidence SHA256 for one fixture file."""
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def tree_snapshot(root: Path) -> dict[str, tuple[str, str]]:
    """Capture every physical file and link without following links."""
    snapshot: dict[str, tuple[str, str]] = {}
    for directory, child_directories, child_files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(child_directories):
            path = parent / name
            if path.is_symlink():
                snapshot[str(path.relative_to(root))] = ("LINK", os.readlink(path))
                child_directories.remove(name)
        for name in child_files:
            path = parent / name
            if path.is_symlink():
                snapshot[str(path.relative_to(root))] = ("LINK", os.readlink(path))
            else:
                snapshot[str(path.relative_to(root))] = ("FILE", sha256(path))
    return snapshot


class ManagerPromotionTests(unittest.TestCase):
    """Build a complete but minimal promotion host beneath one temporary sandbox."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.host = layout(self.root / "host")
        self.repository = self.root / "repository"
        self.repository.mkdir()
        git("init", "-b", "main", cwd=self.repository)
        git("config", "user.name", "Fixture", cwd=self.repository)
        git("config", "user.email", "fixture@localhost", cwd=self.repository)
        (self.repository / "SKILL.md").write_text(
            "---\nname: skill-lifecycle-manager\ndescription: old fixture\n---\n",
            encoding="utf-8",
        )
        git("add", "--", "SKILL.md", cwd=self.repository)
        git("commit", "-m", "old manager", cwd=self.repository)
        self.old_commit = git("rev-parse", "HEAD", cwd=self.repository)
        (self.repository / "SKILL.md").write_text(
            "---\nname: skill-lifecycle-manager\ndescription: new fixture\n---\n",
            encoding="utf-8",
        )
        git("add", "--", "SKILL.md", cwd=self.repository)
        git("commit", "-m", "new manager", cwd=self.repository)
        self.new_commit = git("rev-parse", "HEAD", cwd=self.repository)
        self.carrier = self.root / "manager.bundle"
        git("bundle", "create", str(self.carrier), "--all", cwd=self.repository)

        self.formal_source = self.root / "formal-source"
        git("clone", str(self.repository), str(self.formal_source), cwd=self.root)
        git("checkout", "--detach", self.old_commit, cwd=self.formal_source)
        self.host.activity_root.mkdir(parents=True)
        self.activity = self.host.activity_root / "skill-lifecycle-manager"
        self.activity.symlink_to(self.formal_source, target_is_directory=True)

        self.host.state_root.mkdir(parents=True)
        state_bytes = {
            "skills-registry.json": json.dumps(
                {
                    "schemaVersion": 1,
                    "summary": {"inventory": {"physicalEntries": 1}},
                    "skills": [{"name": "skill-lifecycle-manager"}],
                },
                indent=2,
            ).encode(),
            "skills-registry.yaml": b"registry: old\n",
            "skill-capability-report.md": b"# old capability\n",
            "skill-governance-report.md": b"# old governance\n",
            "skill-stability-baseline.json": json.dumps(
                {"schemaVersion": 1, "manager": {"commit": self.old_commit}}, indent=2
            ).encode(),
        }
        for name, payload in state_bytes.items():
            (self.host.state_root / name).write_bytes(payload)

        self.uv_path = self.root / "bin/uv"
        self.uv_path.parent.mkdir(parents=True)
        self.uv_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.uv_path.chmod(0o755)
        self.tool_dir = self.root / "uv-tools"
        self.tool_bin = self.root / "tool-bin"
        self.tool_bin.mkdir()
        self.formal_cli = self.tool_bin / "skill"
        self.formal_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.formal_cli.chmod(0o755)
        self.receipt = self.tool_dir / "skill-lifecycle-manager/uv-receipt.toml"
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text(
            f'[[tool.requirements]]\nname = "skill-lifecycle-manager"\neditable = "{self.formal_source}"\n',
            encoding="utf-8",
        )

        transaction_id = f"transaction-{uuid.uuid4()}"
        self.recovery_root = self.root / "recovery" / transaction_id
        state_hashes = {name: sha256(self.host.state_root / name) for name in STATE_NAMES}
        self.plan = {
            "schemaVersion": 1,
            "documentType": "MANAGER_PROMOTION_PLAN",
            "mode": "REHEARSAL",
            "transactionID": transaction_id,
            "sandboxRoot": str(self.root),
            "oldCommit": self.old_commit,
            "newCommit": self.new_commit,
            "newManagerVersion": "5.0.0",
            "candidateSource": str(self.repository),
            "carrierPath": str(self.carrier),
            "carrierSHA256": sha256(self.carrier),
            "formalSource": str(self.formal_source),
            "activityEntry": str(self.activity),
            "formalCLI": str(self.formal_cli),
            "uvPath": str(self.uv_path),
            "uvToolDir": str(self.tool_dir),
            "uvToolBinDir": str(self.tool_bin),
            "uvReceipt": str(self.receipt),
            "recoveryRoot": str(self.recovery_root),
            "expectedInventoryCount": 1,
            "stateSHA256": state_hashes,
            "authorizedBy": "fixture-authority",
            "authorizedAt": "2026-08-07T10:00:00Z",
        }
        self.plan_path = self.root / "promotion-plan.json"
        self.plan_path.write_text(json.dumps(self.plan, indent=2) + "\n", encoding="utf-8")
        self.old_state_hashes = dict(state_hashes)
        self.old_receipt_sha256 = sha256(self.receipt)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_upgrade_preview_proves_exact_identity_without_writes(self) -> None:
        before = tree_snapshot(self.root)

        result = preview_manager_promotion(self.plan_path, self.host)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["action"], "MANAGER_PROMOTION_PREVIEW")
        self.assertEqual(result["oldCommit"], self.old_commit)
        self.assertEqual(result["newCommit"], self.new_commit)
        self.assertEqual(result["managerVersion"], "5.0.0")
        self.assertEqual(result["mutations"], 0)
        self.assertEqual(tree_snapshot(self.root), before)

    def test_formal_cli_upgrade_previews_the_exact_plan(self) -> None:
        formal_plan = {**self.plan, "mode": "FORMAL", "sandboxRoot": None}
        formal_plan_path = self.root / "formal-plan.json"
        formal_plan_path.write_text(json.dumps(formal_plan, indent=2) + "\n", encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "skill_lifecycle",
                "--activity-root",
                str(self.host.activity_root),
                "--data-root",
                str(self.host.data_root),
                "--state-root",
                str(self.host.state_root),
                "--cache-root",
                str(self.host.cache_root),
                "manager-upgrade",
                "--plan",
                str(formal_plan_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["action"], "MANAGER_PROMOTION_PREVIEW")
        self.assertEqual(result["mode"], "FORMAL")
        self.assertEqual(result["mutations"], 0)

    def test_bootstrap_requires_an_explicit_install_or_upgrade_mode(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [str(repository / "bootstrap.sh")],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "UV_PATH": str(self.uv_path)},
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Usage: bootstrap.sh install", completed.stderr)
        self.assertIn("bootstrap.sh upgrade --plan", completed.stderr)

    def test_rehearsal_path_escape_blocks_before_mutation(self) -> None:
        escaped_plan = {
            **self.plan,
            "recoveryRoot": str(self.root.parent / f"escaped-{uuid.uuid4()}"),
        }
        escaped_plan_path = self.root / "escaped-plan.json"
        escaped_plan_path.write_text(json.dumps(escaped_plan, indent=2) + "\n", encoding="utf-8")
        before = tree_snapshot(self.root)

        with self.assertRaises(LifecycleBlocked):
            preview_manager_promotion(escaped_plan_path, self.host)

        self.assertEqual(tree_snapshot(self.root), before)


class RealManagerPromotionTests(unittest.TestCase):
    """Promote the actual old manager package inside disposable uv and XDG roots."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.host = layout(self.root / "host")
        current_repository = Path(__file__).resolve().parents[1]
        self.candidate_source = self.root / "candidate-source"
        git("clone", str(current_repository), str(self.candidate_source), cwd=self.root)
        self.new_commit = git("rev-parse", "HEAD", cwd=self.candidate_source)
        self.old_commit = "564215ba6c82927fc8ba2a9fc8943a6adef2e3ee"
        self.carrier = self.root / "manager.bundle"
        git("bundle", "create", str(self.carrier), "--all", cwd=self.candidate_source)

        self.formal_source = self.root / "formal-source"
        git("clone", str(self.candidate_source), str(self.formal_source), cwd=self.root)
        git("checkout", "--detach", self.old_commit, cwd=self.formal_source)
        self.host.activity_root.mkdir(parents=True)
        self.activity = self.host.activity_root / "skill-lifecycle-manager"
        self.activity.symlink_to(self.formal_source, target_is_directory=True)

        self.uv_path = Path("/home/a/.local/bin/uv")
        self.tool_dir = self.root / "uv-tools"
        self.tool_bin = self.root / "tool-bin"
        self.uv_environment = {
            **os.environ,
            "UV_TOOL_DIR": str(self.tool_dir),
            "UV_TOOL_BIN_DIR": str(self.tool_bin),
        }
        self._run(
            [str(self.uv_path), "tool", "install", "--offline", "--force", "--editable", str(self.formal_source)],
            env=self.uv_environment,
        )
        self.formal_cli = self.tool_bin / "skill"
        self.receipt = self.tool_dir / "skill-lifecycle-manager/uv-receipt.toml"
        roots = [
            "--activity-root",
            str(self.host.activity_root),
            "--data-root",
            str(self.host.data_root),
            "--state-root",
            str(self.host.state_root),
            "--cache-root",
            str(self.host.cache_root),
        ]
        for command in (["registry", "--apply"], ["report", "--apply"], ["governance", "--apply"]):
            self._run([str(self.formal_cli), *roots, *command], env=self.uv_environment)
        self._run(
            [
                str(self.formal_cli),
                *roots,
                "backup",
                "--path",
                str(self.formal_source),
                "--path",
                str(self.host.activity_root),
                "--apply",
            ],
            env=self.uv_environment,
        )
        self._run([str(self.formal_cli), *roots, "stabilize", "--apply"], env=self.uv_environment)

        transaction_id = f"transaction-{uuid.uuid4()}"
        self.recovery_root = self.root / "recovery" / transaction_id
        state_hashes = {name: sha256(self.host.state_root / name) for name in STATE_NAMES}
        self.plan = {
            "schemaVersion": 1,
            "documentType": "MANAGER_PROMOTION_PLAN",
            "mode": "REHEARSAL",
            "transactionID": transaction_id,
            "sandboxRoot": str(self.root),
            "oldCommit": self.old_commit,
            "newCommit": self.new_commit,
            "newManagerVersion": "5.0.0",
            "candidateSource": str(self.candidate_source),
            "carrierPath": str(self.carrier),
            "carrierSHA256": sha256(self.carrier),
            "formalSource": str(self.formal_source),
            "activityEntry": str(self.activity),
            "formalCLI": str(self.formal_cli),
            "uvPath": str(self.uv_path),
            "uvToolDir": str(self.tool_dir),
            "uvToolBinDir": str(self.tool_bin),
            "uvReceipt": str(self.receipt),
            "recoveryRoot": str(self.recovery_root),
            "expectedInventoryCount": 1,
            "stateSHA256": state_hashes,
            "authorizedBy": "fixture-authority",
            "authorizedAt": "2026-08-07T10:00:00Z",
        }
        self.plan_path = self.root / "promotion-plan.json"
        self.plan_path.write_text(json.dumps(self.plan, indent=2) + "\n", encoding="utf-8")
        self.old_state_hashes = dict(state_hashes)
        self.old_receipt_sha256 = sha256(self.receipt)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
        self.assertEqual(completed.returncode, 0, f"{command}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
        return completed

    def assert_old_state_restored(self, result: dict[str, object]) -> None:
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.formal_source), self.old_commit)
        self.assertEqual(git("status", "--porcelain=v1", cwd=self.formal_source), "")
        self.assertTrue(self.activity.is_symlink())
        self.assertEqual(self.activity.resolve(strict=True), self.formal_source)
        self.assertEqual(sha256(self.receipt), self.old_receipt_sha256)
        for name, expected in self.old_state_hashes.items():
            self.assertEqual(sha256(self.host.state_root / name), expected, name)
        roots = [
            "--activity-root",
            str(self.host.activity_root),
            "--data-root",
            str(self.host.data_root),
            "--state-root",
            str(self.host.state_root),
            "--cache-root",
            str(self.host.cache_root),
        ]
        health = json.loads(self._run([str(self.formal_cli), *roots, "health"], env=self.uv_environment).stdout)
        self.assertEqual(health["status"], "PASS")
        self.assertEqual(health["mutations"], 0)
        self.assertEqual(result["health"], health)

    def test_complete_offline_upgrade_publishes_new_identity_and_health(self) -> None:
        result = execute_manager_promotion(self.plan_path, self.host, apply=True)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["action"], "MANAGER_PROMOTED")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.formal_source), self.new_commit)
        identity = json.loads(self._run([str(self.formal_cli), "--version"], env=self.uv_environment).stdout)
        self.assertEqual(identity["managerVersion"], "5.0.0")
        self.assertEqual(identity["sourceCommit"], self.new_commit)
        self.assertEqual(result["health"]["status"], "PASS")
        self.assertEqual(result["health"]["mutations"], 0)
        baseline = json.loads(self.host.baseline_path.read_text(encoding="utf-8"))
        self.assertEqual(baseline["manager"]["commit"], self.new_commit)
        self.assertTrue(Path(result["archivedBaselinePath"]).is_file())

    def test_completed_upgrade_retry_is_zero_write(self) -> None:
        first = execute_manager_promotion(self.plan_path, self.host, apply=True)
        before = tree_snapshot(self.root)

        second = execute_manager_promotion(self.plan_path, self.host, apply=True)

        self.assertEqual(first["action"], "MANAGER_PROMOTED")
        self.assertEqual(second["status"], "PASS")
        self.assertEqual(second["action"], "MANAGER_PROMOTION_ALREADY_COMPLETE")
        self.assertEqual(second["mutations"], 0)
        self.assertEqual(tree_snapshot(self.root), before)

    def test_failure_before_source_publication_restores_exact_preimages(self) -> None:
        result = execute_manager_promotion(
            self.plan_path,
            self.host,
            apply=True,
            failure_point="before-source-publication",
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["action"], "MANAGER_PROMOTION_ROLLED_BACK")
        self.assertEqual(result["failurePoint"], "before-source-publication")
        self.assert_old_state_restored(result)

    def test_failure_after_cli_publication_restores_source_tool_and_preimages(self) -> None:
        result = execute_manager_promotion(
            self.plan_path,
            self.host,
            apply=True,
            failure_point="after-cli-publication",
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["action"], "MANAGER_PROMOTION_ROLLED_BACK")
        self.assertEqual(result["failurePoint"], "after-cli-publication")
        self.assert_old_state_restored(result)
        self.assertTrue((self.recovery_root / "failed-new-source").is_dir())

    def test_failure_after_registry_regeneration_restores_all_generated_views(self) -> None:
        result = execute_manager_promotion(
            self.plan_path,
            self.host,
            apply=True,
            failure_point="after-registry-regeneration",
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["action"], "MANAGER_PROMOTION_ROLLED_BACK")
        self.assertEqual(result["failurePoint"], "after-registry-regeneration")
        self.assert_old_state_restored(result)

    def test_failure_after_baseline_archival_restores_baseline_and_retains_history(self) -> None:
        result = execute_manager_promotion(
            self.plan_path,
            self.host,
            apply=True,
            failure_point="after-baseline-archival",
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["action"], "MANAGER_PROMOTION_ROLLED_BACK")
        self.assertEqual(result["failurePoint"], "after-baseline-archival")
        self.assert_old_state_restored(result)
        history = list((self.host.state_root / "baseline-history").glob("*.json"))
        self.assertEqual(len(history), 1)
        self.assertEqual(sha256(history[0]), self.old_state_hashes["skill-stability-baseline.json"])


if __name__ == "__main__":
    unittest.main()
