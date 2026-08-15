"""
Command-line trigger for the Windows and Linux Skill lifecycle product.

The parser translates one explicit user trigger into one lifecycle command. Inventory, transactions,
verification, state changes, and recovery logic stay in their business modules, while this entrypoint
returns the same structured JSON feedback to humans and automation.
"""

from __future__ import annotations  # Keep annotations available on Python 3.12.

import argparse  # Convert shell arguments into one explicit command request.
import json  # Render deterministic machine-readable feedback.
import sys  # Render BLOCKED diagnostics and report the running interpreter.
from pathlib import Path  # Preserve POSIX paths from the CLI boundary.
from typing import Any  # Describe the structured result passed to the renderer.

from skill_lifecycle.freshness import check_updates  # Compare configured PACKAGE releases without writes or fetch.
from skill_lifecycle.guardian import approve_guardian_update, publish_guardian_policy, scan_guardian, schedule_guardian  # Run policy, daily scan, approval, and scheduling commands.
from skill_lifecycle.inventory import governance_result, registry_result, report_result, scan_skills, write_registry  # Read and publish inventory evidence.
from skill_lifecycle.manager_identity import manager_identity  # Report exact package and source identity without writes.
from skill_lifecycle.manager_promotion import execute_manager_promotion, read_promotion_plan  # Run one exact offline self-promotion plan.
from skill_lifecycle.operations import backup_preview, create_backup, inspect_install, install_skill, restore_backup, update_skill  # Execute explicit lifecycle transactions.
from skill_lifecycle.package_transaction import configure_package_transaction
from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Apply one host layout and shared stop gate.
from skill_lifecycle.platforms import UnsupportedPlatform, current_platform
from skill_lifecycle.pilot import activate_pilot, approve_pilot, rollback_pilot, verify_pilot  # Run the reviewed Phase D decision-to-rollback chain.
from skill_lifecycle.plugin_inventory import scan_plugins  # Observe Codex plugins and marketplaces without writes.
from skill_lifecycle.shadow import preview_shadow, write_shadow  # Compare pinned sources in an isolated output tree.
from skill_lifecycle.stability import health, stabilize  # Freeze and compare stable-use evidence.
from skill_lifecycle.verification import verify_target  # Collect bounded Static/Runtime/Behavior evidence.


def parser() -> argparse.ArgumentParser:
    """Describe every command and make each mutating boundary visible as --apply."""
    root = argparse.ArgumentParser(prog="skill", description="Python 3.12 Windows/Linux Skill lifecycle CLI")
    root.add_argument("--version", action="store_true", help="Report structured manager version and source identity")
    root.add_argument("--activity-root", type=Path, help="Override ~/.agents/skills")
    root.add_argument("--data-root", type=Path, help="Override XDG data storage")
    root.add_argument("--state-root", type=Path, help="Override XDG state storage")
    root.add_argument("--cache-root", type=Path, help="Override XDG transaction cache")
    commands = root.add_subparsers(dest="command")

    scan = commands.add_parser("scan", help="Read live Skill identity without writing state")
    scan.add_argument("--root", action="append", type=Path, help="Explicit activity root; repeat as needed")

    registry = commands.add_parser("registry", help="Preview or generate the canonical Registry")
    registry.add_argument("--apply", action="store_true")
    report = commands.add_parser("report", help="Preview or generate the inventory report")
    report.add_argument("--apply", action="store_true")
    governance = commands.add_parser("governance", help="Preview or generate evidence governance")
    governance.add_argument("--apply", action="store_true")

    verify = commands.add_parser("verify", help="Preview or run one Skill's declared probes")
    verify_target_group = verify.add_mutually_exclusive_group(required=True)
    verify_target_group.add_argument("--name", help="Resolve one exact Registry name")
    verify_target_group.add_argument("--target-skill", type=Path, help="Verify an exact physical Skill root")
    verify.add_argument("--apply", action="store_true")

    install = commands.add_parser("install", help="Preview or install one package/Git Skill transactionally")
    install.add_argument("source", nargs="?", help="Local directory or Git URL")
    install.add_argument("--source", dest="source_option", help="PowerShell-era compatible source spelling")
    install.add_argument("--mode", choices=("auto", "package", "source", "hybrid"), default="auto")
    install.add_argument("--skill-path", help="Skill path relative to a multi-Skill source")
    install.add_argument("--apply", action="store_true")

    update = commands.add_parser("update", help="Preview or apply one native Skill/PACKAGE transaction")
    update.add_argument("--name", required=True)
    update.add_argument("--approval", type=Path, help="Exact Guardian approval required by --apply")
    update.add_argument("--evaluated-at", help="Timezone-aware approval evaluation time required by --apply")
    update.add_argument("--apply", action="store_true")

    package_configure = commands.add_parser("package-configure", help="Preview or adopt one reviewed PACKAGE driver contract")
    package_configure.add_argument("--name", required=True)
    package_configure.add_argument("--contract", type=Path, required=True)
    package_configure.add_argument("--apply", action="store_true")

    updates = commands.add_parser("updates", help="Check configured PACKAGE release freshness without writes")
    updates_target = updates.add_mutually_exclusive_group(required=True)
    updates_target.add_argument("--name", help="Check one exact Registry name")
    updates_target.add_argument("--all", dest="all_skills", action="store_true", help="Check every configured PACKAGE")

    plugins = commands.add_parser("plugins", help="Read Codex plugin and marketplace evidence without writes")
    plugins.add_argument("--available", action="store_true", help="Include uninstalled marketplace entries")
    plugins.add_argument("--codex-command", default="codex", help="Exact Codex CLI path or executable name")

    guardian = commands.add_parser("guardian", help="Configure and run the read-only daily lifecycle guardian")
    guardian_commands = guardian.add_subparsers(dest="guardian_command", required=True)
    guardian_policy = guardian_commands.add_parser("policy", help="Preview or publish desired monitoring policy")
    guardian_policy.add_argument("--file", type=Path, required=True)
    guardian_policy.add_argument("--apply", action="store_true")
    guardian_scan = guardian_commands.add_parser("scan", help="Scan every Registry record and optionally publish reports")
    guardian_scan.add_argument("--policy", type=Path, help="Preview against an explicit policy instead of canonical policy")
    guardian_scan.add_argument("--observed-at", help="Explicit timezone-aware evidence time for deterministic runs")
    guardian_scan.add_argument("--apply", action="store_true")
    guardian_approve = guardian_commands.add_parser("approve", help="Preview or publish one exact human update approval")
    guardian_approve.add_argument("--report", type=Path, required=True)
    guardian_approve.add_argument("--name", required=True)
    guardian_approve.add_argument("--decision-id", required=True)
    guardian_approve.add_argument("--requested-by", required=True)
    guardian_approve.add_argument("--requested-at", required=True)
    guardian_approve.add_argument("--decided-by", required=True)
    guardian_approve.add_argument("--decided-at", required=True)
    guardian_approve.add_argument("--expires-at", required=True)
    guardian_approve.add_argument("--reason", required=True)
    guardian_approve.add_argument("--apply", action="store_true")
    guardian_schedule = guardian_commands.add_parser("schedule", help="Preview or install a scan-only daily user schedule")
    guardian_schedule.add_argument("--time", default="03:00", help="Local daily time in HH:MM form")
    guardian_schedule.add_argument("--apply", action="store_true")

    backup = commands.add_parser("backup", help="Preview or create a link-aware backup")
    backup.add_argument("--path", action="append", type=Path, required=True, help="Explicit root; repeat as needed")
    backup.add_argument("--apply", action="store_true")
    restore = commands.add_parser("restore", help="Preview or restore physical files into an empty destination")
    restore.add_argument("--backup-path", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--apply", action="store_true")

    stable = commands.add_parser("stabilize", help="Preview or freeze the verified host-local baseline")
    stable.add_argument("--apply", action="store_true")
    stable.add_argument("--archive-existing", action="store_true", help="Preserve and replace an existing baseline explicitly")
    shadow = commands.add_parser("shadow", help="Generate V5 documents below the isolated shadow root")
    shadow.add_argument("--registry-path", type=Path, required=True, help="Frozen Registry v1 input")
    shadow.add_argument("--source-set", type=Path, required=True, help="Explicit pinned source-set JSON")
    shadow.add_argument("--output-root", type=Path, required=True, help="New child below data-root/shadows")
    shadow.add_argument("--apply", action="store_true", help="Publish only the isolated shadow output")

    approve = commands.add_parser("pilot-approve", help="Preview or publish one artifact-bound approval and ACTIVE lock")
    approve.add_argument("--manifest", type=Path, required=True)
    approve.add_argument("--evidence", type=Path, required=True)
    approve.add_argument("--host-id", required=True)
    approve.add_argument("--decision-id", required=True)
    approve.add_argument("--requested-by", required=True)
    approve.add_argument("--requested-at", required=True)
    approve.add_argument("--decided-by", required=True)
    approve.add_argument("--decided-at", required=True)
    approve.add_argument("--expires-at", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--apply", action="store_true")

    activate = commands.add_parser("pilot-activate", help="Preview or apply one approved temporary activation")
    activate.add_argument("--manifest", type=Path, required=True)
    activate.add_argument("--evidence", type=Path, required=True)
    activate.add_argument("--repository", type=Path, required=True)
    activate.add_argument("--decision-id", required=True)
    activate.add_argument("--transaction-id", required=True)
    activate.add_argument("--started-at", required=True)
    activate.add_argument("--evaluated-at", required=True)
    activate.add_argument("--executed-by", required=True)
    activate.add_argument("--expected-registry-sha256", required=True)
    activate.add_argument("--expected-baseline-sha256", required=True)
    activate.add_argument("--apply", action="store_true")

    pilot_verify = commands.add_parser("pilot-verify", help="Preview or execute one transaction-bound probe plan")
    pilot_verify.add_argument("--transaction-id", required=True)
    pilot_verify.add_argument("--probe-plan", type=Path, required=True)
    pilot_verify.add_argument("--apply", action="store_true")

    rollback = commands.add_parser("pilot-rollback", help="Preview or roll back one durable pilot transaction")
    rollback.add_argument("--transaction-id", required=True)
    rollback.add_argument("--decision-id", required=True, help="New superseding revocation decision ID")
    rollback.add_argument("--decided-by", required=True)
    rollback.add_argument("--decided-at", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--apply", action="store_true")

    manager_upgrade = commands.add_parser("manager-upgrade", help="Preview or apply one exact offline manager promotion")
    manager_upgrade.add_argument("--plan", type=Path, required=True, help="Schema-valid FORMAL promotion plan")
    manager_upgrade.add_argument("--apply", action="store_true")

    manager_rehearse = commands.add_parser("manager-rehearse", help="Inject one failure inside a disposable promotion sandbox")
    manager_rehearse.add_argument("--plan", type=Path, required=True, help="Schema-valid REHEARSAL promotion plan")
    manager_rehearse.add_argument(
        "--failure-point",
        required=True,
        choices=(
            "before-source-publication",
            "after-cli-publication",
            "after-registry-regeneration",
            "after-baseline-archival",
        ),
    )
    manager_rehearse.add_argument("--apply", action="store_true")

    health_parser = commands.add_parser("health", help="Compare frozen local evidence without writes or fetch")
    health_parser.add_argument("--project-root", type=Path)
    return root


def layout(arguments: argparse.Namespace) -> HostLayout:
    """Apply explicit root overrides without changing environment variables or creating paths."""
    default = HostLayout.default()
    return HostLayout(
        activity_root=(arguments.activity_root or default.activity_root).expanduser(),
        data_root=(arguments.data_root or default.data_root).expanduser(),
        state_root=(arguments.state_root or default.state_root).expanduser(),
        cache_root=(arguments.cache_root or default.cache_root).expanduser(),
        platform=default.platform,
    )


def target_from_name(host: HostLayout, name: str) -> Path:
    """Resolve one exact Registry record to its physical Skill root."""
    if not host.registry_path.is_file():
        raise LifecycleBlocked(f"Registry is missing: {host.registry_path}")
    registry = json.loads(host.registry_path.read_text(encoding="utf-8"))
    records = [record for record in registry.get("skills", []) if record.get("name") == name]
    if len(records) != 1:
        raise LifecycleBlocked(f"Expected one Registry record named {name}, found {len(records)}.")
    return Path(records[0]["physicalPath"])


def execute(arguments: argparse.Namespace, host: HostLayout) -> dict[str, Any]:
    """Dispatch one parsed trigger to one business command and return its feedback."""
    linux_only = {
        "pilot-approve",
        "pilot-activate",
        "pilot-verify",
        "pilot-rollback",
        "manager-upgrade",
        "manager-rehearse",
    }
    if host.platform.name == "windows" and arguments.command in linux_only:
        raise LifecycleBlocked(
            f"{arguments.command} is Linux-only until a Windows-native recovery rehearsal is verified."
        )
    if arguments.command == "scan":
        roots = arguments.root or [host.activity_root]
        return {"status": "PASS", "action": "SCANNED", "inventory": scan_skills(roots), "mutations": 0}
    if arguments.command == "registry":
        return write_registry(host) if arguments.apply else registry_result(host)
    if arguments.command == "report":
        return report_result(host, arguments.apply)
    if arguments.command == "governance":
        return governance_result(host, arguments.apply)
    if arguments.command == "verify":
        target = arguments.target_skill or target_from_name(host, arguments.name)
        return verify_target(host, target, arguments.apply)
    if arguments.command == "install":
        source = arguments.source_option or arguments.source
        if not source:
            raise LifecycleBlocked("Install requires a source path or Git URL.")
        return install_skill(host, source, arguments.mode, arguments.skill_path) if arguments.apply else inspect_install(host, source, arguments.mode, arguments.skill_path)
    if arguments.command == "update":
        return update_skill(host, arguments.name, arguments.apply, arguments.approval, arguments.evaluated_at)
    if arguments.command == "package-configure":
        return configure_package_transaction(host, arguments.name, arguments.contract, arguments.apply)
    if arguments.command == "updates":
        return check_updates(host, arguments.name)
    if arguments.command == "plugins":
        return scan_plugins(arguments.codex_command, arguments.available)
    if arguments.command == "guardian":
        if arguments.guardian_command == "policy":
            return publish_guardian_policy(host, arguments.file, arguments.apply)
        if arguments.guardian_command == "scan":
            return scan_guardian(host, arguments.policy, arguments.apply, arguments.observed_at)
        if arguments.guardian_command == "schedule":
            return schedule_guardian(host, arguments.time, arguments.apply)
        return approve_guardian_update(
            host,
            report_path=arguments.report,
            name=arguments.name,
            decision_id=arguments.decision_id,
            requested_by=arguments.requested_by,
            requested_at=arguments.requested_at,
            decided_by=arguments.decided_by,
            decided_at=arguments.decided_at,
            expires_at=arguments.expires_at,
            reason=arguments.reason,
            apply=arguments.apply,
        )
    if arguments.command == "backup":
        return create_backup(host, arguments.path) if arguments.apply else backup_preview(host, arguments.path)
    if arguments.command == "restore":
        return restore_backup(arguments.backup_path, arguments.destination, arguments.apply)
    if arguments.command == "stabilize":
        return stabilize(host, arguments.apply, arguments.archive_existing)
    if arguments.command == "shadow":
        shadow_arguments = (host, arguments.registry_path, arguments.source_set, arguments.output_root)
        return write_shadow(*shadow_arguments) if arguments.apply else preview_shadow(*shadow_arguments)
    if arguments.command == "pilot-approve":
        request = {
            "manifestPath": arguments.manifest,
            "evidencePath": arguments.evidence,
            "hostID": arguments.host_id,
            "decisionID": arguments.decision_id,
            "requestedBy": arguments.requested_by,
            "requestedAt": arguments.requested_at,
            "decidedBy": arguments.decided_by,
            "decidedAt": arguments.decided_at,
            "expiresAt": arguments.expires_at,
            "reason": arguments.reason,
        }
        return approve_pilot(host, request, arguments.apply)
    if arguments.command == "pilot-activate":
        request = {
            "manifestPath": arguments.manifest,
            "evidencePath": arguments.evidence,
            "repositoryPath": arguments.repository,
            "decisionID": arguments.decision_id,
            "transactionID": arguments.transaction_id,
            "startedAt": arguments.started_at,
            "evaluatedAt": arguments.evaluated_at,
            "executedBy": arguments.executed_by,
            "expectedRegistrySHA256": arguments.expected_registry_sha256,
            "expectedBaselineSHA256": arguments.expected_baseline_sha256,
        }
        return activate_pilot(host, request, arguments.apply)
    if arguments.command == "pilot-verify":
        return verify_pilot(host, arguments.transaction_id, arguments.probe_plan, arguments.apply)
    if arguments.command == "pilot-rollback":
        request = {
            "transactionID": arguments.transaction_id,
            "decisionID": arguments.decision_id,
            "decidedBy": arguments.decided_by,
            "decidedAt": arguments.decided_at,
            "reason": arguments.reason,
        }
        return rollback_pilot(host, request, arguments.apply)
    if arguments.command == "manager-upgrade":
        plan = read_promotion_plan(arguments.plan)
        if plan["mode"] != "FORMAL":
            raise LifecycleBlocked("manager-upgrade requires a FORMAL promotion plan.")
        return execute_manager_promotion(arguments.plan, host, arguments.apply)
    if arguments.command == "manager-rehearse":
        plan = read_promotion_plan(arguments.plan)
        if plan["mode"] != "REHEARSAL":
            raise LifecycleBlocked("manager-rehearse requires a REHEARSAL promotion plan.")
        return execute_manager_promotion(
            arguments.plan,
            host,
            arguments.apply,
            arguments.failure_point if arguments.apply else None,
        )
    return health(host, arguments.project_root)


def main(arguments: list[str] | None = None) -> int:
    """Execute one command and return a shell-friendly PASS/UNKNOWN or BLOCKED exit code."""
    try:
        current_platform()
    except UnsupportedPlatform as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}), file=sys.stderr)
        return 1
    command_parser = parser()
    parsed = command_parser.parse_args(arguments)
    if parsed.version:
        if parsed.command is not None:
            command_parser.error("--version cannot be combined with a command")
        try:
            result = manager_identity()
        except (LifecycleBlocked, OSError, ValueError) as error:
            print(json.dumps({"status": "BLOCKED", "error": str(error)}), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if parsed.command is None:
        command_parser.error("a command or --version is required")
    try:
        result = execute(parsed, layout(parsed))
    except (LifecycleBlocked, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "BLOCKED" else 0
