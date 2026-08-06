"""
Command-line trigger for the Linux-native Skill lifecycle product.

The parser translates one explicit user trigger into one lifecycle command. Inventory, transactions,
verification, state changes, and recovery logic stay in their business modules, while this entrypoint
returns the same structured JSON feedback to humans and automation.
"""

from __future__ import annotations  # Keep annotations available on Python 3.12.

import argparse  # Convert shell arguments into one explicit command request.
import json  # Render deterministic machine-readable feedback.
import sys  # Refuse non-Linux runtime and separate BLOCKED diagnostics.
from pathlib import Path  # Preserve POSIX paths from the CLI boundary.
from typing import Any  # Describe the structured result passed to the renderer.

from skill_lifecycle.freshness import check_updates  # Compare configured PACKAGE releases without writes or fetch.
from skill_lifecycle.inventory import governance_result, registry_result, report_result, scan_skills, write_registry  # Read and publish inventory evidence.
from skill_lifecycle.operations import backup_preview, create_backup, inspect_install, install_skill, restore_backup, update_skill  # Execute explicit lifecycle transactions.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Apply one host layout and shared stop gate.
from skill_lifecycle.shadow import preview_shadow, write_shadow  # Compare pinned sources in an isolated output tree.
from skill_lifecycle.stability import health, stabilize  # Freeze and compare stable-use evidence.
from skill_lifecycle.verification import verify_target  # Collect bounded Static/Runtime/Behavior evidence.


def parser() -> argparse.ArgumentParser:
    """Describe every command and make each mutating boundary visible as --apply."""
    root = argparse.ArgumentParser(prog="skill", description="Python 3.12 Linux-native Skill lifecycle CLI")
    root.add_argument("--activity-root", type=Path, help="Override ~/.agents/skills")
    root.add_argument("--data-root", type=Path, help="Override XDG data storage")
    root.add_argument("--state-root", type=Path, help="Override XDG state storage")
    root.add_argument("--cache-root", type=Path, help="Override XDG transaction cache")
    commands = root.add_subparsers(dest="command", required=True)

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

    update = commands.add_parser("update", help="Preview or apply one validated fast-forward update")
    update.add_argument("--name", required=True)
    update.add_argument("--apply", action="store_true")

    updates = commands.add_parser("updates", help="Check configured PACKAGE release freshness without writes")
    updates_target = updates.add_mutually_exclusive_group(required=True)
    updates_target.add_argument("--name", help="Check one exact Registry name")
    updates_target.add_argument("--all", dest="all_skills", action="store_true", help="Check every configured PACKAGE")

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
    health_parser = commands.add_parser("health", help="Compare frozen local evidence without writes or fetch")
    health_parser.add_argument("--project-root", type=Path)
    return root


def layout(arguments: argparse.Namespace) -> HostLayout:
    """Apply explicit root overrides without changing environment variables or creating paths."""
    default = HostLayout.linux_default()
    return HostLayout(
        activity_root=(arguments.activity_root or default.activity_root).expanduser(),
        data_root=(arguments.data_root or default.data_root).expanduser(),
        state_root=(arguments.state_root or default.state_root).expanduser(),
        cache_root=(arguments.cache_root or default.cache_root).expanduser(),
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
        return update_skill(host, arguments.name, arguments.apply)
    if arguments.command == "updates":
        return check_updates(host, arguments.name)
    if arguments.command == "backup":
        return create_backup(host, arguments.path) if arguments.apply else backup_preview(host, arguments.path)
    if arguments.command == "restore":
        return restore_backup(arguments.backup_path, arguments.destination, arguments.apply)
    if arguments.command == "stabilize":
        return stabilize(host, arguments.apply, arguments.archive_existing)
    if arguments.command == "shadow":
        shadow_arguments = (host, arguments.registry_path, arguments.source_set, arguments.output_root)
        return write_shadow(*shadow_arguments) if arguments.apply else preview_shadow(*shadow_arguments)
    return health(host, arguments.project_root)


def main(arguments: list[str] | None = None) -> int:
    """Execute one command and return a shell-friendly PASS/UNKNOWN or BLOCKED exit code."""
    if sys.platform != "linux":
        print(json.dumps({"status": "BLOCKED", "error": "Linux runtime required."}), file=sys.stderr)
        return 1  # This runtime intentionally has no Windows compatibility branch.
    parsed = parser().parse_args(arguments)
    try:
        result = execute(parsed, layout(parsed))
    except (LifecycleBlocked, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "BLOCKED" else 0
