"""Prove Linux uv-tool PACKAGE preview, transaction, and rollback through the public update seam."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill_lifecycle.inventory import write_registry
from skill_lifecycle.operations import update_skill
from skill_lifecycle.package_transaction import configure_package_transaction, node_digest, preview_package_update, update_package
from support import create_skill, git, layout, write_lifecycle_record


def package_fixture(root: Path):
    """Create one copied adapter PACKAGE, exact release tags, and an isolated host."""
    host = layout(root / "host")
    package = create_skill(host.activity_root / "spec-kit", "spec-kit")
    upstream = root / "upstream"
    upstream.mkdir()
    git("init", "-b", "main", cwd=upstream)
    git("config", "user.name", "Fixture", cwd=upstream)
    git("config", "user.email", "fixture@example.invalid", cwd=upstream)
    (upstream / "pyproject.toml").write_text('[project]\nname="specify-cli"\nversion="0.13.0"\n', encoding="utf-8")
    git("add", "--", "pyproject.toml", cwd=upstream)
    git("commit", "-m", "v0.13.0", cwd=upstream)
    current_commit = git("rev-parse", "HEAD", cwd=upstream)
    git("tag", "-a", "v0.13.0", "-m", "v0.13.0", cwd=upstream)
    (upstream / "pyproject.toml").write_text('[project]\nname="specify-cli"\nversion="0.16.4"\n', encoding="utf-8")
    git("add", "--", "pyproject.toml", cwd=upstream)
    git("commit", "-m", "v0.16.4", cwd=upstream)
    candidate_commit = git("rev-parse", "HEAD", cwd=upstream)
    git("tag", "-a", "v0.16.4", "-m", "v0.16.4", cwd=upstream)
    write_lifecycle_record(
        package,
        {
            "schemaVersion": 1,
            "lifecycleMode": "PACKAGE",
            "origin": "/reviewed/spec-kit-adapter",
            "remote": None,
            "commit": None,
            "selectedSkillPath": ".",
            "installedAt": "2026-08-05T00:00:00Z",
            "updates": {
                "strategy": "git-tags",
                "repository": str(upstream),
                "tagPrefix": "v",
                "baselineVersion": "0.13.0",
                "baselineCommit": current_commit,
                "cli": {"command": "specify", "arguments": ["version"]},
                "packageTransaction": {
                    "driver": "uv-tool-git",
                    "distribution": "specify-cli",
                    "executable": "specify",
                    "versionArguments": ["version"],
                    "helpArguments": ["--help"],
                    "smokeArguments": [["integration", "--help"]],
                },
            },
        },
    )
    write_registry(host)
    record = json.loads(host.registry_path.read_text(encoding="utf-8"))["skills"][0]
    return host, package, record, current_commit, candidate_commit


def fake_uv(root: Path) -> tuple[Path, Path, Path]:
    """Create one argument-array uv boundary that reports isolated tool/bin roots."""
    tool_root = root / "host/data/uv-tools"
    bin_root = root / "host/data/uv-bin"
    tool_root.mkdir(parents=True)
    bin_root.mkdir(parents=True)
    executable = root / "fake-uv"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "tool_root = pathlib.Path(os.environ['FAKE_UV_TOOL_ROOT'])\n"
        "bin_root = pathlib.Path(os.environ['FAKE_UV_BIN_ROOT'])\n"
        "if args == ['tool', 'dir']:\n"
        "    print(tool_root)\n"
        "elif args == ['tool', 'dir', '--bin']:\n"
        "    print(bin_root)\n"
        "elif args[:3] == ['tool', 'install', 'specify-cli']:\n"
        "    source = args[args.index('--from') + 1]\n"
        "    package = tool_root / 'specify-cli'\n"
        "    package.mkdir(parents=True, exist_ok=True)\n"
        "    (package / 'bin').mkdir(exist_ok=True)\n"
        "    version = os.environ.get('FAKE_UV_VERSION', '0.16.4')\n"
        "    fail = os.environ.get('FAKE_UV_FAIL', '')\n"
        "    cli = package / 'bin/specify'\n"
        f"    cli.write_text('#!{sys.executable}\\nimport os, sys\\nargs=sys.argv[1:]\\nfail=os.environ.get(\\\"FAKE_UV_FAIL\\\", \\\"\\\")\\nif args == [\\\"version\\\"] and fail == \\\"verify\\\": raise SystemExit(81)\\nif args == [\\\"version\\\"]: print(\\\"Specify CLI Version \\\" + os.environ.get(\\\"FAKE_UV_VERSION\\\", \\\"0.16.4\\\"))\\nelif args == [\\\"--help\\\"] or args == [\\\"integration\\\", \\\"--help\\\"]: print(\\\"help ok\\\")\\nelse: raise SystemExit(82)\\n', encoding='utf-8')\n"
        "    cli.chmod(0o755)\n"
        "    receipt = {'source': source, 'distribution': 'specify-cli', 'version': version}\n"
        "    (package / 'uv-receipt.toml').write_text(json.dumps(receipt), encoding='utf-8')\n"
        "    bin_root.mkdir(parents=True, exist_ok=True)\n"
        "    shim = bin_root / 'specify'\n"
        "    if shim.exists() or shim.is_symlink(): shim.unlink()\n"
        "    shim.symlink_to(cli)\n"
        "    if fail == 'apply': raise SystemExit(80)\n"
        "else:\n"
        "    raise SystemExit(70)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, tool_root, bin_root


def seed_old_tool(tool_root: Path, bin_root: Path, commit: str) -> tuple[Path, Path]:
    """Create an exact old uv-tool tree and executable link for rollback assertions."""
    package = tool_root / "specify-cli"
    cli = package / "bin/specify"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text(f"#!{sys.executable}\nprint('Specify CLI Version 0.13.0')\n", encoding="utf-8")
    cli.chmod(0o755)
    (package / "uv-receipt.toml").write_text(
        json.dumps({"source": f"git+fixture@{commit}", "distribution": "specify-cli", "version": "0.13.0"}),
        encoding="utf-8",
    )
    shim = bin_root / "specify"
    shim.symlink_to(cli)
    return package, shim


class PackageTransactionPreviewTests(unittest.TestCase):
    """Require a complete, exact, zero-write preview before PACKAGE mutation."""

    @unittest.skipUnless(sys.platform.startswith("linux"), "PACKAGE apply is Linux-native in V5.4.")
    def test_preview_lists_exact_identity_paths_commands_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, package, record, current_commit, candidate_commit = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            registry_before = host.registry_path.read_bytes()
            with patch.dict(os.environ, {"FAKE_UV_TOOL_ROOT": str(tool_root), "FAKE_UV_BIN_ROOT": str(bin_root)}):
                with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                    preview = preview_package_update(host, record)

            self.assertEqual(host.registry_path.read_bytes(), registry_before)
            self.assertEqual(preview["type"], "PACKAGE")
            self.assertEqual(preview["package"], "spec-kit")
            self.assertEqual(preview["currentVersion"], "0.13.0")
            self.assertEqual(preview["currentCommit"], current_commit)
            self.assertEqual(preview["candidateVersion"], "0.16.4")
            self.assertEqual(preview["candidateCommit"], candidate_commit)
            self.assertEqual(preview["installMethod"], "uv-tool-git")
            self.assertIn(str(package / ".skill-lifecycle.json"), preview["affectedPaths"])
            self.assertIn(str(tool_root / "specify-cli"), preview["affectedPaths"])
            self.assertIn(str(bin_root / "specify"), preview["affectedPaths"])
            self.assertIn(candidate_commit, preview["commands"][2][-1])
            self.assertEqual(preview["rollbackStrategy"], "RESTORE_SNAPSHOT")
            self.assertEqual(preview["mutations"], 0)


class PackageTransactionApplyTests(unittest.TestCase):
    """Exercise the complete observable PACKAGE update path through one real filesystem fixture."""

    @unittest.skipUnless(sys.platform.startswith("linux"), "PACKAGE apply is Linux-native in V5.4.")
    def test_absent_uv_tool_installs_exact_candidate_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, package, record, _, candidate_commit = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            environment = {
                "FAKE_UV_TOOL_ROOT": str(tool_root),
                "FAKE_UV_BIN_ROOT": str(bin_root),
                "FAKE_UV_VERSION": "0.16.4",
            }
            with patch.dict(os.environ, environment):
                with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                    with patch("skill_lifecycle.package_transaction.require_guardian_approval", return_value={"lifecycleMode": "PACKAGE"}):
                        result = update_package(host, record, True, Path("approval.json"), "2026-08-08T02:00:00Z")

            lifecycle = json.loads((package / ".skill-lifecycle.json").read_text(encoding="utf-8"))
            registry = json.loads(host.registry_path.read_text(encoding="utf-8"))
            transaction = json.loads(Path(result["transactionPath"]).read_text(encoding="utf-8"))

        self.assertEqual(result["action"], "PACKAGE_UPDATED")
        self.assertEqual(result["finalState"], "COMMITTED")
        self.assertEqual(result["candidateVersion"], "0.16.4")
        self.assertEqual(result["candidateCommit"], candidate_commit)
        self.assertEqual(lifecycle["updates"]["baselineVersion"], "0.16.4")
        self.assertEqual(lifecycle["updates"]["baselineCommit"], candidate_commit)
        self.assertEqual(registry["skills"][0]["updates"]["baselineVersion"], "0.16.4")
        self.assertEqual(transaction["finalState"], "COMMITTED")
        self.assertTrue(transaction["rollbackAvailable"])

    def run_failure(self, failure: str) -> tuple[dict, dict, str, str, Path]:
        """Apply one injected failure and return restored lifecycle/transaction evidence."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        host, package, record, current_commit, _ = package_fixture(root)
        uv, tool_root, bin_root = fake_uv(root)
        old_tool, old_shim = seed_old_tool(tool_root, bin_root, current_commit)
        tool_digest = node_digest(old_tool)
        shim_digest = node_digest(old_shim)
        registry_digest = node_digest(host.registry_path)
        environment = {
            "FAKE_UV_TOOL_ROOT": str(tool_root),
            "FAKE_UV_BIN_ROOT": str(bin_root),
            "FAKE_UV_VERSION": "0.16.4",
            "FAKE_UV_FAIL": failure,
        }
        with patch.dict(os.environ, environment):
            with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                with patch("skill_lifecycle.package_transaction.require_guardian_approval", return_value={"lifecycleMode": "PACKAGE"}):
                    with self.assertRaisesRegex(Exception, "rollback verified"):
                        update_package(host, record, True, Path("approval.json"), "2026-08-08T02:00:00Z")
        transaction_dir = next(host.package_transaction_root.iterdir())
        transaction = json.loads((transaction_dir / "transaction.json").read_text(encoding="utf-8"))
        lifecycle = json.loads((package / ".skill-lifecycle.json").read_text(encoding="utf-8"))
        self.assertEqual(node_digest(old_tool), tool_digest)
        self.assertEqual(node_digest(old_shim), shim_digest)
        self.assertEqual(node_digest(host.registry_path), registry_digest)
        self.assertEqual(lifecycle["updates"]["baselineVersion"], "0.13.0")
        self.assertEqual(lifecycle["updates"]["baselineCommit"], current_commit)
        self.assertEqual(transaction["finalState"], "ROLLED_BACK")
        self.assertTrue(transaction["rollbackAvailable"])
        self.assertFalse((host.package_lock_root / "active.lock").exists())
        return lifecycle, transaction, tool_digest, shim_digest, transaction_dir

    def test_apply_failure_restores_old_tool_adapter_registry_and_link(self) -> None:
        self.run_failure("apply")

    def test_verify_failure_restores_old_tool_adapter_registry_and_link(self) -> None:
        self.run_failure("verify")

    def test_snapshot_failure_blocks_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, _, record, _, _ = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            environment = {"FAKE_UV_TOOL_ROOT": str(tool_root), "FAKE_UV_BIN_ROOT": str(bin_root)}
            with patch.dict(os.environ, environment):
                with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                    with patch("skill_lifecycle.package_transaction.require_guardian_approval", return_value={}):
                        with patch("skill_lifecycle.package_transaction.snapshot_paths", side_effect=OSError("snapshot denied")):
                            with self.assertRaisesRegex(Exception, "blocked before mutation"):
                                update_package(host, record, True, Path("approval.json"), "2026-08-08T02:00:00Z")
            transaction = json.loads(next(host.package_transaction_root.glob("*/transaction.json")).read_text(encoding="utf-8"))
            self.assertEqual(transaction["finalState"], "BLOCKED")
            self.assertFalse((tool_root / "specify-cli").exists())

    def test_uncertain_candidate_blocks_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, _, record, _, _ = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            uncertain = {"updateStatus": "UNKNOWN", "issue": "tag did not peel to a commit"}
            with patch.dict(os.environ, {"FAKE_UV_TOOL_ROOT": str(tool_root), "FAKE_UV_BIN_ROOT": str(bin_root)}):
                with patch("skill_lifecycle.package_transaction.shutil.which", return_value=str(uv)):
                    with patch("skill_lifecycle.package_transaction.check_record", return_value=uncertain):
                        with self.assertRaisesRegex(Exception, "could not be resolved exactly"):
                            preview_package_update(host, record)

    def test_public_update_command_routes_package_to_native_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, _, _, _, _ = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            with patch.dict(os.environ, {"FAKE_UV_TOOL_ROOT": str(tool_root), "FAKE_UV_BIN_ROOT": str(bin_root)}):
                with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                    preview = update_skill(host, "spec-kit", False)
            self.assertEqual(preview["type"], "PACKAGE")
            self.assertEqual(preview["action"], "PACKAGE_UPDATE_PREVIEW")

    def test_missing_rollback_driver_blocks_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, _, record, _, _ = package_fixture(root)
            record["updates"]["packageTransaction"]["driver"] = "unknown-driver"
            with self.assertRaisesRegex(Exception, "driver is unsupported"):
                preview_package_update(host, record)

    def test_existing_package_lock_blocks_duplicate_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, _, record, _, _ = package_fixture(root)
            uv, tool_root, bin_root = fake_uv(root)
            host.package_lock_root.mkdir(parents=True)
            (host.package_lock_root / "active.lock").write_text("active\n", encoding="utf-8")
            with patch.dict(os.environ, {"FAKE_UV_TOOL_ROOT": str(tool_root), "FAKE_UV_BIN_ROOT": str(bin_root)}):
                with patch("skill_lifecycle.package_transaction.shutil.which", side_effect=lambda command: str(uv) if command == "uv" else None):
                    with patch("skill_lifecycle.package_transaction.require_guardian_approval", return_value={}):
                        with self.assertRaisesRegex(Exception, "already active"):
                            update_package(host, record, True, Path("approval.json"), "2026-08-08T02:00:00Z")
            self.assertFalse(host.package_transaction_root.exists())


class PackageConfigurationTests(unittest.TestCase):
    """Adopt a legacy adapter through a logged manager command instead of hand-editing live metadata."""

    def test_reviewed_contract_is_verified_and_published_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host, package, _, current_commit, _ = package_fixture(root)
            lifecycle_path = package / ".skill-lifecycle.json"
            lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            lifecycle["updates"].pop("baselineCommit")
            lifecycle["updates"].pop("packageTransaction")
            lifecycle_path.write_text(json.dumps(lifecycle, indent=2) + "\n", encoding="utf-8")
            write_registry(host)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "documentType": "PACKAGE_TRANSACTION_CONTRACT",
                        "package": "spec-kit",
                        "baselineCommit": current_commit,
                        "driver": "uv-tool-git",
                        "distribution": "specify-cli",
                        "executable": "specify",
                        "versionArguments": ["version"],
                        "helpArguments": ["--help"],
                        "smokeArguments": [["integration", "--help"]],
                    }
                ),
                encoding="utf-8",
            )
            preview = configure_package_transaction(host, "spec-kit", contract, False)
            self.assertNotIn("packageTransaction", json.loads(lifecycle_path.read_text(encoding="utf-8"))["updates"])
            applied = configure_package_transaction(host, "spec-kit", contract, True)
            configured = json.loads(lifecycle_path.read_text(encoding="utf-8"))["updates"]

        self.assertEqual(preview["mutations"], 0)
        self.assertEqual(applied["finalState"], "COMMITTED")
        self.assertEqual(configured["baselineCommit"], current_commit)
        self.assertEqual(configured["packageTransaction"]["driver"], "uv-tool-git")


if __name__ == "__main__":
    unittest.main()
