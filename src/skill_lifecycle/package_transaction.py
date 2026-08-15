"""Transactional lifecycle for copied PACKAGE adapters with a managed Linux uv tool.

The external interface stays deliberately small: preview one Registry record, or apply the same
resolved plan after an exact Guardian approval.  The implementation owns release resolution, path
containment, snapshots, uv invocation, verification, Registry publication, and reverse restoration.
Only the evidence-backed ``uv-tool-git`` adapter exists in V5.4.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skill_lifecycle.freshness import check_record
from skill_lifecycle.guardian import require_guardian_approval
from skill_lifecycle.inventory import governance_result, validate_updates
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_json


COMMAND_TIMEOUT_SECONDS = 30
INSTALL_TIMEOUT_SECONDS = 180


def utc_now() -> str:
    """Return one canonical UTC event timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_command(arguments: list[str], *, timeout: int = COMMAND_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    """Run one literal argument array with bounded, captured output and no shell."""
    try:
        return subprocess.run(arguments, text=True, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LifecycleBlocked(f"PACKAGE command failed before completion: {error}") from error


def command_output(arguments: list[str]) -> str:
    """Return one successful command's trimmed output or a precise fail-closed diagnostic."""
    completed = run_command(arguments)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise LifecycleBlocked(f"PACKAGE discovery command failed: {detail}")
    value = completed.stdout.strip()
    if not value:
        raise LifecycleBlocked("PACKAGE discovery command returned an empty path.")
    return value


def managed_owner(layout: HostLayout) -> Path:
    """Return the common owner that contains every configured lifecycle root."""
    roots = [layout.activity_root, layout.data_root, layout.state_root, layout.cache_root]
    common = Path(os.path.commonpath([str(path.expanduser().resolve()) for path in roots]))
    if common == Path(common.anchor):
        raise LifecycleBlocked("PACKAGE lifecycle roots do not share a bounded non-root owner.")
    return common


def managed_path(layout: HostLayout, value: str, label: str) -> Path:
    """Accept one absolute non-root path below the lifecycle host owner without following links."""
    requested = Path(value).expanduser()
    if not requested.is_absolute():
        raise LifecycleBlocked(f"PACKAGE {label} must be an absolute path: {requested}")
    if requested.is_symlink():
        raise LifecycleBlocked(f"PACKAGE {label} root must not be a symbolic link: {requested}")
    resolved = requested.resolve(strict=False)
    owner = managed_owner(layout)
    if resolved == owner or owner not in resolved.parents:
        raise LifecycleBlocked(f"PACKAGE {label} escapes the managed host owner {owner}: {resolved}")
    return resolved


def preview_package_update(layout: HostLayout, record: dict[str, Any]) -> dict[str, Any]:
    """Return one complete zero-write plan for an exact ``uv-tool-git`` PACKAGE release."""
    if layout.platform.name != "linux":
        raise LifecycleBlocked("PACKAGE uv-tool-git transactions are Linux-only.")
    if record.get("lifecycleMode") != "PACKAGE":
        raise LifecycleBlocked(f"PACKAGE transaction requires a PACKAGE Registry record: {record.get('name')}")
    updates = record.get("updates")
    transaction = updates.get("packageTransaction") if isinstance(updates, dict) else None
    if not transaction:
        raise LifecycleBlocked(
            f"PACKAGE transaction is supported, but {record.get('name')} has no validated packageTransaction driver."
        )
    if transaction.get("driver") != "uv-tool-git":
        raise LifecycleBlocked(f"PACKAGE transaction driver is unsupported: {transaction.get('driver')}")
    baseline_commit = updates.get("baselineCommit")
    if not isinstance(baseline_commit, str):
        raise LifecycleBlocked("PACKAGE rollback identity requires an exact baselineCommit.")

    freshness = check_record(record)
    candidate_version = freshness.get("latestVersion")
    candidate_tag = freshness.get("candidateTag")
    candidate_commit = freshness.get("candidateCommit")
    if freshness.get("updateStatus") == "UNKNOWN" or not all((candidate_version, candidate_tag, candidate_commit)):
        raise LifecycleBlocked(f"PACKAGE candidate could not be resolved exactly: {freshness.get('issue')}")

    uv_text = shutil.which("uv")
    if not uv_text:
        raise LifecycleBlocked("PACKAGE uv-tool-git driver requires the uv executable.")
    uv = Path(uv_text).resolve(strict=True)
    tool_root = managed_path(layout, command_output([str(uv), "tool", "dir"]), "uv tool root")
    bin_root = managed_path(layout, command_output([str(uv), "tool", "dir", "--bin"]), "uv bin root")
    package_root = Path(record["physicalPath"]).resolve(strict=True)
    if package_root.is_symlink() or package_root != Path(record["physicalPath"]).absolute():
        raise LifecycleBlocked(f"PACKAGE physical root must be one direct directory: {record['physicalPath']}")
    if managed_owner(layout) not in package_root.parents:
        raise LifecycleBlocked(f"PACKAGE physical root escapes the managed host owner: {package_root}")

    distribution = transaction["distribution"]
    executable_name = transaction["executable"]
    package_tool = tool_root / distribution
    package_executable = bin_root / executable_name
    install_source = f"git+{updates['repository']}@{candidate_commit}"
    install_command = [
        str(uv),
        "tool",
        "install",
        distribution,
        "--force",
        "--from",
        install_source,
    ]
    affected_paths = [
        package_root,
        package_root / ".skill-lifecycle.json",
        package_tool,
        package_executable,
        tool_root / ".gitignore",
        tool_root / ".lock",
        layout.registry_path,
        layout.registry_yaml_path,
        layout.capability_report_path,
        layout.governance_report_path,
    ]
    risks = ["EXECUTABLE_INSTALL", "DEPENDENCY_GRAPH_CHANGE"]
    if freshness.get("cliStatus") == "NOT_INSTALLED":
        risks.append("CURRENT_EXECUTABLE_ABSENT")
    return {
        "status": "PASS",
        "action": "PACKAGE_UPDATE_PREVIEW",
        "type": "PACKAGE",
        "package": record["name"],
        "currentVersion": freshness["currentVersion"],
        "currentVersionSource": freshness["currentVersionSource"],
        "currentCommit": baseline_commit,
        "candidateVersion": candidate_version,
        "candidateTag": candidate_tag,
        "candidateCommit": candidate_commit,
        "updateStatus": freshness["updateStatus"],
        "source": updates["repository"],
        "installMethod": "uv-tool-git",
        "uvExecutable": str(uv),
        "toolRoot": str(tool_root),
        "binRoot": str(bin_root),
        "affectedPaths": [str(path) for path in affected_paths],
        "dependenciesAffected": True,
        "configAffected": [str(package_root / ".skill-lifecycle.json")],
        "commands": [
            [str(uv), "tool", "dir"],
            [str(uv), "tool", "dir", "--bin"],
            install_command,
            [str(package_executable), *transaction["versionArguments"]],
            [str(package_executable), *transaction["helpArguments"]],
            *[[str(package_executable), *arguments] for arguments in transaction["smokeArguments"]],
        ],
        "rollbackStrategy": "RESTORE_SNAPSHOT",
        "riskLevel": "HIGH" if risks else "LOW",
        "riskFlags": risks,
        "runtimeState": freshness["cliStatus"],
        "mutations": 0,
    }


def node_digest(path: Path) -> str | None:
    """Hash one physical node tree without following symbolic links."""
    if not path.exists() and not path.is_symlink():
        return None
    digest = hashlib.sha256()

    def add(node: Path, relative: str) -> None:
        metadata = node.lstat()
        digest.update(f"{relative}\0{stat.S_IFMT(metadata.st_mode):o}\0{stat.S_IMODE(metadata.st_mode):o}\0".encode())
        if node.is_symlink():
            digest.update(os.readlink(node).encode())
        elif node.is_file():
            with node.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
        elif node.is_dir():
            for child in sorted(node.iterdir(), key=lambda item: item.name):
                add(child, f"{relative}/{child.name}")

    add(path, ".")
    return digest.hexdigest().upper()


def copy_node(source: Path, destination: Path) -> None:
    """Copy one exact physical node to a transaction-owned preimage."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)


def remove_node(path: Path) -> None:
    """Remove one exact transaction-declared node without following links."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def snapshot_paths(transaction_path: Path, paths: list[Path], metadata: dict[str, Any]) -> dict[str, Any]:
    """Freeze every declared preimage and publish a restore manifest."""
    preimages = transaction_path / "preimages"
    entries: list[dict[str, Any]] = []
    for index, path in enumerate(paths):
        exists = path.exists() or path.is_symlink()
        snapshot = preimages / f"{index:02d}"
        digest = node_digest(path)
        if exists:
            copy_node(path, snapshot)
        entries.append(
            {
                "path": str(path),
                "existed": exists,
                "kind": "symlink" if path.is_symlink() else "directory" if path.is_dir() else "file" if path.is_file() else "missing",
                "sha256": digest,
                "preimage": str(snapshot.relative_to(transaction_path)) if exists else None,
            }
        )
    manifest = {**metadata, "snapshotLocation": str(preimages), "restoreManifest": entries}
    atomic_json(transaction_path / "snapshot-manifest.json", manifest)
    for entry in entries:
        if entry["existed"] and node_digest(transaction_path / entry["preimage"]) != entry["sha256"]:
            raise LifecycleBlocked(f"PACKAGE snapshot verification failed: {entry['path']}")
        if node_digest(Path(entry["path"])) != entry["sha256"]:
            raise LifecycleBlocked(f"PACKAGE live state changed while snapshotting: {entry['path']}")
    return manifest


def restore_snapshot(transaction_path: Path, manifest: dict[str, Any]) -> None:
    """Restore declared nodes in reverse order and prove every resulting preimage hash."""
    entries = manifest["restoreManifest"]
    for entry in reversed(entries):
        target = Path(entry["path"])
        remove_node(target)
        if entry["existed"]:
            copy_node(transaction_path / entry["preimage"], target)
    failures = [entry["path"] for entry in entries if node_digest(Path(entry["path"])) != entry["sha256"]]
    if failures:
        raise LifecycleBlocked(f"PACKAGE rollback verification failed for: {', '.join(failures)}")


def publish_event(transaction_path: Path, state: str, transaction: dict[str, Any], **details: Any) -> None:
    """Append one immutable state event and refresh the final transaction view."""
    sequence = len(list(transaction_path.glob("event-*.json"))) + 1
    event = {"sequence": sequence, "state": state, "at": utc_now(), **details}
    atomic_json(transaction_path / f"event-{sequence:02d}-{state.lower().replace('_', '-')}.json", event)
    transaction["actions"].append(event)
    transaction["finalState"] = state
    transaction["endedAt"] = event["at"] if state in {"COMMITTED", "ROLLED_BACK", "FAILED", "BLOCKED"} else None
    atomic_json(transaction_path / "transaction.json", transaction)


def snapshot_targets(layout: HostLayout, preview: dict[str, Any], record: dict[str, Any]) -> list[Path]:
    """Return non-overlapping live nodes whose exact restoration covers this adapter."""
    package_root = Path(record["physicalPath"])
    transaction = record["updates"]["packageTransaction"]
    return [
        package_root,
        Path(preview["toolRoot"]) / transaction["distribution"],
        Path(preview["binRoot"]) / transaction["executable"],
        Path(preview["toolRoot"]) / ".gitignore",
        Path(preview["toolRoot"]) / ".lock",
        layout.registry_path,
        layout.registry_yaml_path,
        layout.capability_report_path,
        layout.governance_report_path,
    ]


def verify_package(layout: HostLayout, preview: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Prove executable, exact version, receipt identity, smoke checks, and Registry identity."""
    contract = record["updates"]["packageTransaction"]
    executable = Path(preview["binRoot"]) / contract["executable"]
    tool_path = Path(preview["toolRoot"]) / contract["distribution"]
    if not tool_path.is_dir() or not (executable.exists() or executable.is_symlink()):
        raise LifecycleBlocked("PACKAGE verification could not find the managed tool and executable.")
    resolved_executable = executable.resolve(strict=True)
    if tool_path.resolve() not in resolved_executable.parents:
        raise LifecycleBlocked("PACKAGE executable does not resolve inside the managed uv tool directory.")
    version_result = run_command([str(executable), *contract["versionArguments"]])
    version_text = f"{version_result.stdout}\n{version_result.stderr}"
    if version_result.returncode or preview["candidateVersion"] not in version_text:
        raise LifecycleBlocked("PACKAGE executable version verification did not match the exact candidate.")
    checks: list[dict[str, Any]] = []
    for arguments in [contract["helpArguments"], *contract["smokeArguments"]]:
        result = run_command([str(executable), *arguments])
        checks.append({"arguments": arguments, "exitCode": result.returncode})
        if result.returncode:
            raise LifecycleBlocked(f"PACKAGE smoke verification failed for arguments: {arguments}")
    receipts = sorted(tool_path.glob("*receipt*"))
    if not receipts:
        raise LifecycleBlocked("PACKAGE verification found no uv receipt metadata.")
    receipt_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in receipts)
    if preview["candidateCommit"] not in receipt_text or contract["distribution"] not in receipt_text:
        raise LifecycleBlocked("PACKAGE uv receipt does not bind the exact candidate commit and distribution.")
    lifecycle = json.loads((Path(record["physicalPath"]) / ".skill-lifecycle.json").read_text(encoding="utf-8"))
    updates = lifecycle.get("updates", {})
    if updates.get("baselineVersion") != preview["candidateVersion"] or updates.get("baselineCommit") != preview["candidateCommit"]:
        raise LifecycleBlocked("PACKAGE lifecycle metadata does not match the applied candidate.")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8")) if layout.registry_path.is_file() else {}
    matches = [item for item in registry.get("skills", []) if item.get("name") == record["name"]]
    if len(matches) != 1 or matches[0].get("updates", {}).get("baselineCommit") != preview["candidateCommit"]:
        raise LifecycleBlocked("PACKAGE Registry evidence does not match the applied candidate.")
    return {"version": preview["candidateVersion"], "commit": preview["candidateCommit"], "checks": checks, "receiptPaths": [str(path) for path in receipts]}


def acquire_lock(layout: HostLayout, name: str, transaction_id: str) -> Path:
    """Acquire one global PACKAGE lock because uv tool metadata is shared across packages."""
    layout.package_lock_root.mkdir(parents=True, exist_ok=True)
    lock = layout.package_lock_root / "active.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise LifecycleBlocked(f"PACKAGE transaction is already active or requires recovery: {lock}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"transactionID": transaction_id, "package": name, "createdAt": utc_now()}, stream)
        stream.write("\n")
    return lock


def update_package(
    layout: HostLayout,
    record: dict[str, Any],
    apply: bool,
    approval_path: Path | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Preview or execute one exact, journaled, rollback-capable uv-tool PACKAGE update."""
    preview = preview_package_update(layout, record)
    if not apply:
        return preview
    if preview["updateStatus"] != "UPDATE_AVAILABLE":
        raise LifecycleBlocked(
            f"PACKAGE apply requires UPDATE_AVAILABLE, observed {preview['updateStatus']} for {record['name']}."
        )
    require_guardian_approval(
        layout,
        approval_path,
        record["name"],
        preview["currentVersion"],
        preview["candidateVersion"],
        evaluated_at,
        current_commit=preview["currentCommit"],
        candidate_commit=preview["candidateCommit"],
    )
    transaction_id = f"transaction-{uuid.uuid4()}"
    lock = acquire_lock(layout, record["name"], transaction_id)
    transaction_path = layout.package_transaction_root / transaction_id
    try:
        transaction_path.mkdir(parents=True, exist_ok=False)
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    transaction = {
        "schemaVersion": 1,
        "transactionID": transaction_id,
        "type": "PACKAGE",
        "package": record["name"],
        "source": preview["source"],
        "oldVersion": preview["currentVersion"],
        "oldCommit": preview["currentCommit"],
        "candidateVersion": preview["candidateVersion"],
        "candidateCommit": preview["candidateCommit"],
        "startedAt": utc_now(),
        "endedAt": None,
        "snapshot": None,
        "verification": None,
        "rollbackAvailable": False,
        "actions": [],
        "finalState": "PREVIEWED",
    }
    manifest: dict[str, Any] | None = None
    mutated = False
    retain_lock = False
    try:
        publish_event(transaction_path, "PREVIEWED", transaction, preview=preview)
        publish_event(transaction_path, "APPROVED", transaction, approvalPath=str(approval_path))
        manifest = snapshot_paths(
            transaction_path,
            snapshot_targets(layout, preview, record),
            {
                "transactionID": transaction_id,
                "packageName": record["name"],
                "oldVersion": preview["currentVersion"],
                "candidateVersion": preview["candidateVersion"],
                "timestamp": utc_now(),
            },
        )
        transaction["snapshot"] = str(transaction_path / "snapshot-manifest.json")
        transaction["rollbackAvailable"] = True
        publish_event(transaction_path, "SNAPSHOTTED", transaction, snapshot=transaction["snapshot"])
        publish_event(transaction_path, "APPLYING", transaction, command=preview["commands"][2])
        mutated = True
        installed = run_command(preview["commands"][2], timeout=INSTALL_TIMEOUT_SECONDS)
        if installed.returncode:
            detail = installed.stderr.strip() or installed.stdout.strip() or f"exit {installed.returncode}"
            raise LifecycleBlocked(f"PACKAGE apply failed: {detail}")
        lifecycle_path = Path(record["physicalPath"]) / ".skill-lifecycle.json"
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        lifecycle["updates"]["baselineVersion"] = preview["candidateVersion"]
        lifecycle["updates"]["baselineCommit"] = preview["candidateCommit"]
        lifecycle["lastPackageTransaction"] = transaction_id
        atomic_json(lifecycle_path, lifecycle)
        publish_event(transaction_path, "VERIFYING", transaction)
        governance_result(layout, True)
        verification = verify_package(layout, preview, record)
        transaction["verification"] = verification
        publish_event(transaction_path, "COMMITTED", transaction, verification=verification)
        return {
            "status": "PASS",
            "action": "PACKAGE_UPDATED",
            "name": record["name"],
            "currentVersion": preview["currentVersion"],
            "candidateVersion": preview["candidateVersion"],
            "candidateCommit": preview["candidateCommit"],
            "finalState": "COMMITTED",
            "transactionPath": str(transaction_path / "transaction.json"),
            "mutations": 1,
        }
    except BaseException as error:
        if not mutated or manifest is None:
            publish_event(transaction_path, "BLOCKED", transaction, error=str(error))
            raise LifecycleBlocked(f"PACKAGE transaction blocked before mutation: {error}; evidence: {transaction_path}") from error
        publish_event(transaction_path, "ROLLING_BACK", transaction, error=str(error))
        try:
            restore_snapshot(transaction_path, manifest)
            publish_event(transaction_path, "ROLLED_BACK", transaction, error=str(error), restoreVerified=True)
        except BaseException as rollback_error:
            retain_lock = True
            publish_event(transaction_path, "FAILED", transaction, error=str(error), rollbackError=str(rollback_error))
            raise LifecycleBlocked(
                f"PACKAGE update failed and rollback could not be proved; lock retained at {lock}: {rollback_error}"
            ) from error
        raise LifecycleBlocked(f"PACKAGE update failed; rollback verified: {error}; evidence: {transaction_path}") from error
    finally:
        if not retain_lock and lock.exists():
            lock.unlink()


def read_package_contract(path: Path, name: str) -> dict[str, Any]:
    """Read one exact user-reviewed adapter contract without accepting hidden fields."""
    if not path.is_file():
        raise LifecycleBlocked(f"PACKAGE transaction contract is missing: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        "schemaVersion",
        "documentType",
        "package",
        "baselineCommit",
        "driver",
        "distribution",
        "executable",
        "versionArguments",
        "helpArguments",
        "smokeArguments",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise LifecycleBlocked(f"PACKAGE transaction contract fields must be exactly {sorted(fields)}.")
    if document.get("schemaVersion") != 1 or document.get("documentType") != "PACKAGE_TRANSACTION_CONTRACT":
        raise LifecycleBlocked("PACKAGE transaction contract identity is unsupported.")
    if document.get("package") != name:
        raise LifecycleBlocked("PACKAGE transaction contract package does not match the Registry selection.")
    return document


def verify_baseline_tag(repository: str, prefix: str, version: str, expected_commit: str) -> None:
    """Prove the supplied baseline commit is the exact direct or peeled stable-tag target."""
    tag = f"{prefix}{version}"
    completed = run_command(
        ["git", "ls-remote", "--tags", repository, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise LifecycleBlocked(f"PACKAGE baseline tag resolution failed: {detail}")
    identities: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2:
            identities[fields[1]] = fields[0]
    resolved = identities.get(f"refs/tags/{tag}^{{}}") or identities.get(f"refs/tags/{tag}")
    if resolved != expected_commit:
        raise LifecycleBlocked(
            f"PACKAGE baseline commit does not match exact tag {tag}: expected {expected_commit}, resolved {resolved}."
        )


def configure_package_transaction(
    layout: HostLayout,
    name: str,
    contract_path: Path,
    apply: bool,
) -> dict[str, Any]:
    """Transactionally adopt one reviewed driver contract for a legacy PACKAGE adapter."""
    from skill_lifecycle.operations import registry_record

    if layout.platform.name != "linux":
        raise LifecycleBlocked("PACKAGE uv-tool-git configuration is Linux-only.")
    record = registry_record(layout, name)
    if record.get("lifecycleMode") != "PACKAGE" or not isinstance(record.get("updates"), dict):
        raise LifecycleBlocked(f"PACKAGE configuration requires one configured legacy PACKAGE: {name}")
    contract = read_package_contract(contract_path, name)
    updates = dict(record["updates"])
    updates["baselineCommit"] = contract["baselineCommit"]
    updates["packageTransaction"] = {
        field: contract[field]
        for field in ("driver", "distribution", "executable", "versionArguments", "helpArguments", "smokeArguments")
    }
    normalized, issues = validate_updates(updates)
    if issues or normalized is None:
        raise LifecycleBlocked(f"PACKAGE transaction contract is invalid: {issues}")
    verify_baseline_tag(
        normalized["repository"],
        normalized["tagPrefix"],
        normalized["baselineVersion"],
        normalized["baselineCommit"],
    )
    lifecycle_path = Path(record["physicalPath"]) / ".skill-lifecycle.json"
    preview = {
        "status": "PASS",
        "action": "PACKAGE_CONFIG_PREVIEW",
        "type": "PACKAGE",
        "package": name,
        "contractPath": str(contract_path.resolve()),
        "metadataPath": str(lifecycle_path),
        "baselineVersion": normalized["baselineVersion"],
        "baselineCommit": normalized["baselineCommit"],
        "driver": normalized["packageTransaction"]["driver"],
        "mutations": 0,
    }
    if not apply:
        return preview
    transaction_id = f"transaction-{uuid.uuid4()}"
    lock = acquire_lock(layout, name, transaction_id)
    transaction_path = layout.package_transaction_root / transaction_id
    try:
        transaction_path.mkdir(parents=True, exist_ok=False)
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    transaction = {
        "schemaVersion": 1,
        "transactionID": transaction_id,
        "type": "PACKAGE_CONFIG",
        "package": name,
        "source": normalized["repository"],
        "oldVersion": normalized["baselineVersion"],
        "oldCommit": record["updates"].get("baselineCommit"),
        "candidateVersion": normalized["baselineVersion"],
        "candidateCommit": normalized["baselineCommit"],
        "startedAt": utc_now(),
        "endedAt": None,
        "snapshot": None,
        "verification": None,
        "rollbackAvailable": False,
        "actions": [],
        "finalState": "PREVIEWED",
    }
    manifest: dict[str, Any] | None = None
    mutated = False
    retain_lock = False
    try:
        publish_event(transaction_path, "PREVIEWED", transaction, preview=preview)
        targets = [
            Path(record["physicalPath"]),
            layout.registry_path,
            layout.registry_yaml_path,
            layout.capability_report_path,
            layout.governance_report_path,
        ]
        manifest = snapshot_paths(
            transaction_path,
            targets,
            {
                "transactionID": transaction_id,
                "packageName": name,
                "oldVersion": normalized["baselineVersion"],
                "candidateVersion": normalized["baselineVersion"],
                "timestamp": utc_now(),
            },
        )
        transaction["snapshot"] = str(transaction_path / "snapshot-manifest.json")
        transaction["rollbackAvailable"] = True
        publish_event(transaction_path, "SNAPSHOTTED", transaction, snapshot=transaction["snapshot"])
        mutated = True
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        lifecycle["updates"] = normalized
        lifecycle["lastPackageConfigurationTransaction"] = transaction_id
        atomic_json(lifecycle_path, lifecycle)
        governance_result(layout, True)
        registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
        matches = [item for item in registry.get("skills", []) if item.get("name") == name]
        if len(matches) != 1 or matches[0].get("updates") != normalized:
            raise LifecycleBlocked("PACKAGE configuration Registry verification failed.")
        verification = {"baselineTagVerified": True, "registryVerified": True, "contract": normalized["packageTransaction"]}
        transaction["verification"] = verification
        publish_event(transaction_path, "COMMITTED", transaction, verification=verification)
        return {
            **preview,
            "action": "PACKAGE_CONFIGURED",
            "finalState": "COMMITTED",
            "transactionPath": str(transaction_path / "transaction.json"),
            "mutations": 1,
        }
    except BaseException as error:
        if mutated and manifest is not None:
            publish_event(transaction_path, "ROLLING_BACK", transaction, error=str(error))
            try:
                restore_snapshot(transaction_path, manifest)
                publish_event(transaction_path, "ROLLED_BACK", transaction, error=str(error), restoreVerified=True)
            except BaseException as rollback_error:
                retain_lock = True
                publish_event(transaction_path, "FAILED", transaction, error=str(error), rollbackError=str(rollback_error))
                raise LifecycleBlocked(f"PACKAGE configuration rollback failed; lock retained at {lock}: {rollback_error}") from error
        else:
            publish_event(transaction_path, "BLOCKED", transaction, error=str(error))
        raise LifecycleBlocked(f"PACKAGE configuration failed: {error}; evidence: {transaction_path}") from error
    finally:
        if not retain_lock and lock.exists():
            lock.unlink()
