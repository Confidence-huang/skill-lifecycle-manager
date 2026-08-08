"""Preview and execute one exact offline lifecycle-manager self-promotion."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from skill_lifecycle.manager_identity import manager_identity
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_bytes, atomic_json, sha256_file
from skill_lifecycle.shadow import read_json_object


FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
UPPER_SHA256 = re.compile(r"^[0-9A-F]{64}$")
TRANSACTION_ID = re.compile(r"^transaction-[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
STATE_PATHS = {
    "skills-registry.json": "registry_path",
    "skills-registry.yaml": "registry_yaml_path",
    "skill-capability-report.md": "capability_report_path",
    "skill-governance-report.md": "governance_report_path",
    "skill-stability-baseline.json": "baseline_path",
}
FAILURE_POINTS = {
    "before-source-publication",
    "after-cli-publication",
    "after-registry-regeneration",
    "after-baseline-archival",
}
PLAN_KEYS = {
    "schemaVersion",
    "documentType",
    "mode",
    "transactionID",
    "sandboxRoot",
    "oldCommit",
    "newCommit",
    "newManagerVersion",
    "candidateSource",
    "carrierPath",
    "carrierSHA256",
    "formalSource",
    "activityEntry",
    "formalCLI",
    "uvPath",
    "uvToolDir",
    "uvToolBinDir",
    "uvReceipt",
    "recoveryRoot",
    "expectedInventoryCount",
    "stateSHA256",
    "authorizedBy",
    "authorizedAt",
}


def _git(repository: Path | None, *arguments: str) -> str:
    """Return one required local Git fact through an argument array."""
    command = ["git"]
    if repository is not None:
        command.extend(["-C", str(repository)])
    command.extend(arguments)
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise LifecycleBlocked(f"Manager promotion Git check failed: {detail}")
    return completed.stdout.strip()


def _absolute_path(value: Any, label: str, *, must_exist: bool = True) -> Path:
    """Resolve one explicit absolute host path without accepting shell-relative identity."""
    if not isinstance(value, str) or not value:
        raise LifecycleBlocked(f"Promotion plan {label} must be a non-empty path.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LifecycleBlocked(f"Promotion plan {label} must be absolute: {path}")
    resolved = path.resolve(strict=must_exist)
    return resolved


def _absolute_entry(value: Any, label: str) -> Path:
    """Resolve an entry's parent while preserving the leaf symbolic-link identity."""
    if not isinstance(value, str) or not value:
        raise LifecycleBlocked(f"Promotion plan {label} must be a non-empty path.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LifecycleBlocked(f"Promotion plan {label} must be absolute: {path}")
    return path.parent.resolve(strict=True) / path.name


def _require_rehearsal_paths(plan: dict[str, Any], host: HostLayout) -> None:
    """Keep every rehearsal mutation beneath one disposable owner root."""
    if plan["mode"] != "REHEARSAL":
        if plan["sandboxRoot"] is not None:
            raise LifecycleBlocked("FORMAL promotion cannot declare a rehearsal sandbox.")
        return
    sandbox = _absolute_path(plan["sandboxRoot"], "sandboxRoot")
    mutable = [
        _absolute_path(plan["formalSource"], "formalSource"),
        _absolute_entry(plan["activityEntry"], "activityEntry"),
        _absolute_path(plan["formalCLI"], "formalCLI"),
        _absolute_path(plan["uvToolDir"], "uvToolDir", must_exist=False),
        _absolute_path(plan["uvToolBinDir"], "uvToolBinDir", must_exist=False),
        _absolute_path(plan["uvReceipt"], "uvReceipt"),
        _absolute_path(plan["recoveryRoot"], "recoveryRoot", must_exist=False),
        host.activity_root.resolve(strict=True),
        host.state_root.resolve(strict=True),
    ]
    escaped = [str(path) for path in mutable if path != sandbox and sandbox not in path.parents]
    if escaped:
        raise LifecycleBlocked(f"REHEARSAL paths escape sandboxRoot: {escaped}")


def _validate_plan_shape(plan: dict[str, Any]) -> None:
    """Enforce the runtime subset of the promotion Schema without a new dependency."""
    if set(plan) != PLAN_KEYS:
        difference = sorted(set(plan).symmetric_difference(PLAN_KEYS))
        raise LifecycleBlocked(f"Promotion plan fields do not match the contract: {difference}")
    if plan["schemaVersion"] != 1 or plan["documentType"] != "MANAGER_PROMOTION_PLAN":
        raise LifecycleBlocked("Promotion plan identity is unsupported.")
    if plan["mode"] not in {"FORMAL", "REHEARSAL"}:
        raise LifecycleBlocked(f"Promotion plan mode is unsupported: {plan['mode']}")
    if not isinstance(plan["transactionID"], str) or not TRANSACTION_ID.fullmatch(plan["transactionID"]):
        raise LifecycleBlocked("Promotion transactionID does not match the V5 contract.")
    for field in ("oldCommit", "newCommit"):
        if not isinstance(plan[field], str) or not FULL_COMMIT.fullmatch(plan[field]):
            raise LifecycleBlocked(f"Promotion plan {field} must be one full lowercase commit.")
    if plan["oldCommit"] == plan["newCommit"]:
        raise LifecycleBlocked("Promotion old and new commits must differ.")
    if plan["newManagerVersion"] != "5.1.0":
        raise LifecycleBlocked("Promotion successor version must be exactly 5.1.0.")
    if not isinstance(plan["expectedInventoryCount"], int) or isinstance(plan["expectedInventoryCount"], bool) or plan["expectedInventoryCount"] < 1:
        raise LifecycleBlocked("Promotion expectedInventoryCount must be a positive integer.")
    if not isinstance(plan["authorizedBy"], str) or not plan["authorizedBy"].strip():
        raise LifecycleBlocked("Promotion authorizedBy is required.")
    if not isinstance(plan["authorizedAt"], str) or not plan["authorizedAt"].endswith("Z"):
        raise LifecycleBlocked("Promotion authorizedAt must be an explicit UTC timestamp.")
    state_hashes = plan["stateSHA256"]
    if not isinstance(state_hashes, dict) or set(state_hashes) != set(STATE_PATHS):
        raise LifecycleBlocked("Promotion stateSHA256 must pin exactly five preimages.")
    if any(not isinstance(value, str) or not UPPER_SHA256.fullmatch(value) for value in state_hashes.values()):
        raise LifecycleBlocked("Promotion stateSHA256 values must be uppercase SHA256.")


def _receipt_source(receipt_path: Path) -> Path:
    """Return the one editable manager source recorded by the uv receipt."""
    receipt = tomllib.loads(receipt_path.read_text(encoding="utf-8"))
    requirements = receipt.get("tool", {}).get("requirements", [])
    matches = [item for item in requirements if item.get("name") == "skill-lifecycle-manager" and item.get("editable")]
    if len(matches) != 1:
        raise LifecycleBlocked("uv receipt does not contain one editable skill-lifecycle-manager source.")
    return Path(matches[0]["editable"]).expanduser().resolve(strict=True)


def _inventory_count(registry_path: Path) -> int:
    """Read the canonical physical-entry count pinned by the promotion plan."""
    registry, _ = read_json_object(registry_path)
    try:
        count = registry["summary"]["inventory"]["physicalEntries"]
    except (KeyError, TypeError) as error:
        raise LifecycleBlocked("Registry is missing summary.inventory.physicalEntries.") from error
    if not isinstance(count, int) or isinstance(count, bool):
        raise LifecycleBlocked("Registry physicalEntries is not an integer.")
    return count


def read_promotion_plan(plan_path: Path) -> dict[str, Any]:
    """Read one unique-key JSON plan and enforce its complete runtime shape."""
    path = _absolute_path(str(plan_path), "planPath")
    plan, _ = read_json_object(path)
    _validate_plan_shape(plan)
    return plan


def preview_manager_promotion(plan_path: Path, host: HostLayout) -> dict[str, Any]:
    """Prove exact source, carrier, tool, receipt, and state identity without writes."""
    plan = read_promotion_plan(plan_path)
    _require_rehearsal_paths(plan, host)
    formal_source = _absolute_path(plan["formalSource"], "formalSource")
    candidate_source = _absolute_path(plan["candidateSource"], "candidateSource")
    carrier = _absolute_path(plan["carrierPath"], "carrierPath")
    activity = _absolute_entry(plan["activityEntry"], "activityEntry")
    formal_cli = _absolute_path(plan["formalCLI"], "formalCLI")
    uv_path = _absolute_path(plan["uvPath"], "uvPath")
    receipt = _absolute_path(plan["uvReceipt"], "uvReceipt")
    recovery = _absolute_path(plan["recoveryRoot"], "recoveryRoot", must_exist=False)

    if recovery.exists() or recovery.is_symlink():
        raise LifecycleBlocked(f"Promotion recoveryRoot already exists: {recovery}")
    if _git(formal_source, "rev-parse", "HEAD") != plan["oldCommit"]:
        raise LifecycleBlocked("Formal source commit does not match oldCommit.")
    if _git(formal_source, "status", "--porcelain=v1"):
        raise LifecycleBlocked("Formal manager source is dirty.")
    if _git(candidate_source, "rev-parse", "HEAD") != plan["newCommit"]:
        raise LifecycleBlocked("Candidate source commit does not match newCommit.")
    if _git(candidate_source, "status", "--porcelain=v1"):
        raise LifecycleBlocked("Candidate manager source is dirty.")
    ancestry = subprocess.run(
        ["git", "-C", str(candidate_source), "merge-base", "--is-ancestor", plan["oldCommit"], plan["newCommit"]],
        capture_output=True,
        check=False,
    )
    if ancestry.returncode:
        raise LifecycleBlocked("Candidate commit is not a fast-forward descendant of oldCommit.")
    if sha256_file(carrier) != plan["carrierSHA256"]:
        raise LifecycleBlocked("Promotion carrier failed SHA256 verification.")
    bundle_heads = _git(None, "bundle", "list-heads", str(carrier)).splitlines()
    if not any(line.split(maxsplit=1)[0] == plan["newCommit"] for line in bundle_heads if line.strip()):
        raise LifecycleBlocked("Promotion carrier does not publish newCommit.")
    if not activity.is_symlink() or activity.resolve(strict=True) != formal_source:
        raise LifecycleBlocked("Manager activity entry does not resolve to formalSource.")
    if not os.access(uv_path, os.X_OK) or not os.access(formal_cli, os.X_OK):
        raise LifecycleBlocked("Promotion uvPath and formalCLI must be executable.")
    if _receipt_source(receipt) != formal_source:
        raise LifecycleBlocked("uv receipt editable source does not match formalSource.")
    for name, attribute in STATE_PATHS.items():
        state_path = getattr(host, attribute)
        if not state_path.is_file() or sha256_file(state_path) != plan["stateSHA256"][name]:
            raise LifecycleBlocked(f"Promotion preimage hash mismatch: {state_path}")
    baseline, _ = read_json_object(host.baseline_path)
    if baseline.get("manager", {}).get("commit") != plan["oldCommit"]:
        raise LifecycleBlocked("Baseline manager commit does not match oldCommit.")
    if _inventory_count(host.registry_path) != plan["expectedInventoryCount"]:
        raise LifecycleBlocked("Registry physical entry count does not match the promotion plan.")
    successor_identity = manager_identity(candidate_source)
    if successor_identity["managerVersion"] != plan["newManagerVersion"]:
        raise LifecycleBlocked("Candidate package version does not match newManagerVersion.")
    return {
        "status": "PASS",
        "action": "MANAGER_PROMOTION_PREVIEW",
        "mode": plan["mode"],
        "transactionID": plan["transactionID"],
        "oldCommit": plan["oldCommit"],
        "newCommit": plan["newCommit"],
        "managerVersion": successor_identity["managerVersion"],
        "candidateIdentitySHA256": successor_identity["identitySHA256"],
        "carrierSHA256": plan["carrierSHA256"],
        "expectedInventoryCount": plan["expectedInventoryCount"],
        "mutations": 0,
    }


def _run(command: list[str], *, environment: dict[str, str] | None = None) -> str:
    """Run one required promotion command and retain its complete diagnostic on failure."""
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise LifecycleBlocked(f"Manager promotion command failed ({command[0]}): {detail}")
    return completed.stdout


def _json_command(command: list[str], *, environment: dict[str, str] | None = None) -> dict[str, Any]:
    """Run one manager command and require a JSON object result."""
    output = _run(command, environment=environment)
    try:
        result = json.loads(output)
    except json.JSONDecodeError as error:
        raise LifecycleBlocked(f"Manager promotion command returned invalid JSON: {command}") from error
    if not isinstance(result, dict):
        raise LifecycleBlocked(f"Manager promotion command did not return an object: {command}")
    return result


def _manager_command(plan: dict[str, Any], host: HostLayout, *arguments: str) -> list[str]:
    """Build one installed-manager command with explicit lifecycle roots."""
    return [
        plan["formalCLI"],
        "--activity-root",
        str(host.activity_root),
        "--data-root",
        str(host.data_root),
        "--state-root",
        str(host.state_root),
        "--cache-root",
        str(host.cache_root),
        *arguments,
    ]


def _tool_environment(plan: dict[str, Any]) -> dict[str, str]:
    """Pin uv tool publication to the plan's exact user-tool roots and offline mode."""
    return {
        **os.environ,
        "UV_TOOL_DIR": plan["uvToolDir"],
        "UV_TOOL_BIN_DIR": plan["uvToolBinDir"],
        "UV_OFFLINE": "1",
    }


def _copy_preimages(plan: dict[str, Any], host: HostLayout, preimages: Path) -> None:
    """Copy the receipt and five authorized state files before source publication."""
    preimages.mkdir(parents=True)
    shutil.copy2(plan["uvReceipt"], preimages / "uv-receipt.toml")
    state_preimages = preimages / "state"
    state_preimages.mkdir()
    for name, attribute in STATE_PATHS.items():
        source = getattr(host, attribute)
        shutil.copy2(source, state_preimages / name)
        if sha256_file(state_preimages / name) != plan["stateSHA256"][name]:
            raise LifecycleBlocked(f"Promotion preimage copy failed verification: {source}")


def _transaction_record(plan: dict[str, Any], status: str, steps: list[dict[str, str]]) -> dict[str, Any]:
    """Build the durable manager-specific promotion evidence document."""
    return {
        "schemaVersion": 1,
        "documentType": "MANAGER_PROMOTION_TRANSACTION",
        "transactionID": plan["transactionID"],
        "mode": plan["mode"],
        "oldCommit": plan["oldCommit"],
        "newCommit": plan["newCommit"],
        "carrierSHA256": plan["carrierSHA256"],
        "authorizedBy": plan["authorizedBy"],
        "authorizedAt": plan["authorizedAt"],
        "status": status,
        "steps": steps,
    }


def _completed_retry(plan: dict[str, Any], host: HostLayout) -> dict[str, Any] | None:
    """Accept an exact terminal retry only after rechecking promoted identity and health."""
    transaction_path = Path(plan["recoveryRoot"]) / "manager-promotion.json"
    if not transaction_path.is_file():
        return None
    transaction, _ = read_json_object(transaction_path)
    if transaction.get("transactionID") != plan["transactionID"] or transaction.get("newCommit") != plan["newCommit"]:
        raise LifecycleBlocked(f"Promotion recoveryRoot contains another transaction: {transaction_path}")
    if transaction.get("status") != "PROMOTED":
        raise LifecycleBlocked(f"Promotion transaction is not safely retryable: {transaction.get('status')}")
    formal_source = Path(plan["formalSource"])
    if _git(formal_source, "rev-parse", "HEAD") != plan["newCommit"] or _git(formal_source, "status", "--porcelain=v1"):
        raise LifecycleBlocked("Completed promotion retry found source drift.")
    activity = Path(plan["activityEntry"])
    if not activity.is_symlink() or activity.resolve(strict=True) != formal_source:
        raise LifecycleBlocked("Completed promotion retry found activity drift.")
    if _receipt_source(Path(plan["uvReceipt"])) != formal_source:
        raise LifecycleBlocked("Completed promotion retry found uv receipt drift.")
    environment = _tool_environment(plan)
    identity = _json_command([plan["formalCLI"], "--version"], environment=environment)
    if identity.get("sourceCommit") != plan["newCommit"] or identity.get("managerVersion") != plan["newManagerVersion"]:
        raise LifecycleBlocked("Completed promotion retry found installed identity drift.")
    health_result = _json_command(_manager_command(plan, host, "health"), environment=environment)
    if health_result.get("status") != "PASS" or health_result.get("mutations") != 0:
        raise LifecycleBlocked("Completed promotion retry found health drift.")
    if _inventory_count(host.registry_path) != plan["expectedInventoryCount"]:
        raise LifecycleBlocked("Completed promotion retry found inventory-count drift.")
    return {
        "status": "PASS",
        "action": "MANAGER_PROMOTION_ALREADY_COMPLETE",
        "transactionID": plan["transactionID"],
        "oldCommit": plan["oldCommit"],
        "newCommit": plan["newCommit"],
        "managerVersion": plan["newManagerVersion"],
        "installedIdentity": identity,
        "health": health_result,
        "recoveryRoot": plan["recoveryRoot"],
        "transactionPath": str(transaction_path),
        "mutations": 0,
    }


def _inject_failure(selected: str | None, current: str) -> None:
    """Raise one deterministic rehearsal-only interruption at the named promotion gate."""
    if selected == current:
        raise LifecycleBlocked(f"Injected manager promotion failure: {current}")


def _rollback_manager_promotion(
    plan: dict[str, Any],
    host: HostLayout,
    recovery: Path,
    steps: list[dict[str, str]],
    error: BaseException,
    failure_point: str | None,
) -> dict[str, Any]:
    """Restore exact old source, tool receipt, state bytes, activity, and health."""
    transaction_path = recovery / "manager-promotion.json"
    preimages = recovery / "preimages"
    formal_source = Path(plan["formalSource"])
    old_source = recovery / "old-source"
    failed_source = recovery / "failed-new-source"
    source_was_published = old_source.exists()
    try:
        if source_was_published:
            if failed_source.exists() or failed_source.is_symlink():
                raise LifecycleBlocked(f"Failed-source evidence path already exists: {failed_source}")
            if formal_source.exists() or formal_source.is_symlink():
                formal_source.rename(failed_source)
            old_source.rename(formal_source)

        environment = _tool_environment(plan)
        if source_was_published:
            _run(
                [plan["uvPath"], "tool", "install", "--offline", "--force", "--editable", str(formal_source)],
                environment=environment,
            )
        receipt_preimage = preimages / "uv-receipt.toml"
        atomic_bytes(Path(plan["uvReceipt"]), receipt_preimage.read_bytes())
        if sha256_file(Path(plan["uvReceipt"])) != sha256_file(receipt_preimage):
            raise LifecycleBlocked("Rollback uv receipt failed exact preimage verification.")

        for name, attribute in STATE_PATHS.items():
            destination = getattr(host, attribute)
            source = preimages / "state" / name
            atomic_bytes(destination, source.read_bytes())
            if sha256_file(destination) != plan["stateSHA256"][name]:
                raise LifecycleBlocked(f"Rollback state preimage mismatch: {destination}")

        if _git(formal_source, "rev-parse", "HEAD") != plan["oldCommit"]:
            raise LifecycleBlocked("Rollback did not restore the old manager commit.")
        if _git(formal_source, "status", "--porcelain=v1"):
            raise LifecycleBlocked("Rollback restored a dirty manager source.")
        activity = Path(plan["activityEntry"])
        if not activity.is_symlink() or activity.resolve(strict=True) != formal_source:
            raise LifecycleBlocked("Rollback did not restore manager activity resolution.")
        if _receipt_source(Path(plan["uvReceipt"])) != formal_source:
            raise LifecycleBlocked("Rollback receipt does not resolve to formalSource.")
        if _inventory_count(host.registry_path) != plan["expectedInventoryCount"]:
            raise LifecycleBlocked("Rollback did not restore the old inventory count.")
        health_result = _json_command(_manager_command(plan, host, "health"), environment=environment)
        if health_result.get("status") != "PASS" or health_result.get("mutations") != 0:
            raise LifecycleBlocked("Rollback old-manager health did not pass with zero mutations.")
        steps.append({"name": "rollback", "status": "PASS", "detail": "Restored exact old manager preimages and health."})
        atomic_json(transaction_path, _transaction_record(plan, "ROLLED_BACK", steps))
        return {
            "status": "BLOCKED",
            "action": "MANAGER_PROMOTION_ROLLED_BACK",
            "transactionID": plan["transactionID"],
            "oldCommit": plan["oldCommit"],
            "newCommit": plan["newCommit"],
            "failurePoint": failure_point,
            "error": str(error),
            "health": health_result,
            "recoveryRoot": str(recovery),
            "transactionPath": str(transaction_path),
            "mutations": len(steps),
        }
    except BaseException as rollback_error:
        steps.append({"name": "rollback", "status": "BLOCKED", "detail": str(rollback_error)[:2048]})
        try:
            atomic_json(transaction_path, _transaction_record(plan, "ROLLBACK_BLOCKED", steps))
        except OSError:
            pass
        raise LifecycleBlocked(f"Promotion failed ({error}); rollback blocked ({rollback_error}).") from rollback_error


def execute_manager_promotion(
    plan_path: Path,
    host: HostLayout,
    apply: bool,
    failure_point: str | None = None,
) -> dict[str, Any]:
    """Apply one exact offline promotion; preview remains the default public behavior."""
    if not apply:
        return preview_manager_promotion(plan_path, host)

    plan = read_promotion_plan(plan_path)
    if failure_point is not None and (failure_point not in FAILURE_POINTS or plan["mode"] != "REHEARSAL"):
        raise LifecycleBlocked("Failure injection requires one supported point and a REHEARSAL plan.")
    completed = _completed_retry(plan, host)
    if completed is not None:
        return completed

    preview = preview_manager_promotion(plan_path, host)
    recovery = Path(plan["recoveryRoot"])
    recovery.parent.mkdir(parents=True, exist_ok=True)
    recovery.mkdir()
    transaction_path = recovery / "manager-promotion.json"
    steps: list[dict[str, str]] = []
    atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))
    preimages = recovery / "preimages"
    _copy_preimages(plan, host, preimages)
    steps.append({"name": "capture-preimages", "status": "PASS"})
    atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))

    try:
        staged_source = recovery / "staged-source"
        _run(["git", "clone", "--no-checkout", "--", plan["carrierPath"], str(staged_source)])
        _run(["git", "-C", str(staged_source), "checkout", "--detach", plan["newCommit"]])
        if _git(staged_source, "status", "--porcelain=v1"):
            raise LifecycleBlocked("Staged promotion source is dirty.")
        steps.append({"name": "stage-source", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))
        _inject_failure(failure_point, "before-source-publication")

        formal_source = Path(plan["formalSource"])
        old_source = recovery / "old-source"
        formal_source.rename(old_source)
        staged_source.rename(formal_source)
        if not Path(plan["activityEntry"]).is_symlink() or Path(plan["activityEntry"]).resolve(strict=True) != formal_source:
            raise LifecycleBlocked("Activity entry did not preserve the canonical formal source path.")
        steps.append({"name": "publish-source", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))

        environment = _tool_environment(plan)
        _run(
            [plan["uvPath"], "tool", "install", "--offline", "--force", "--editable", str(formal_source)],
            environment=environment,
        )
        installed_identity = _json_command([plan["formalCLI"], "--version"], environment=environment)
        if installed_identity.get("sourceCommit") != plan["newCommit"] or installed_identity.get("managerVersion") != plan["newManagerVersion"]:
            raise LifecycleBlocked("Installed manager identity does not match the promotion plan.")
        if _receipt_source(Path(plan["uvReceipt"])) != formal_source:
            raise LifecycleBlocked("Published uv receipt does not resolve to the promoted formal source.")
        steps.append({"name": "publish-cli", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))
        _inject_failure(failure_point, "after-cli-publication")

        for command in ("registry", "report", "governance"):
            result = _json_command(_manager_command(plan, host, command, "--apply"), environment=environment)
            if result.get("status") != "PASS":
                raise LifecycleBlocked(f"Promoted manager {command} publication did not pass.")
        if _inventory_count(host.registry_path) != plan["expectedInventoryCount"]:
            raise LifecycleBlocked("Promoted Registry physical entry count changed unexpectedly.")
        steps.append({"name": "publish-generated-state", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))
        _inject_failure(failure_point, "after-registry-regeneration")

        stabilization = _json_command(
            _manager_command(plan, host, "stabilize", "--apply", "--archive-existing"),
            environment=environment,
        )
        if stabilization.get("status") != "PASS" or not stabilization.get("archivedBaselinePath"):
            raise LifecycleBlocked("Promoted manager did not archive and replace the stable baseline.")
        steps.append({"name": "archive-and-rebaseline", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "IN_PROGRESS", steps))
        _inject_failure(failure_point, "after-baseline-archival")

        health_result = _json_command(_manager_command(plan, host, "health"), environment=environment)
        if health_result.get("status") != "PASS" or health_result.get("mutations") != 0:
            raise LifecycleBlocked("Promoted manager health did not pass with zero mutations.")
        steps.append({"name": "accept", "status": "PASS"})
        atomic_json(transaction_path, _transaction_record(plan, "PROMOTED", steps))
        return {
            **preview,
            "action": "MANAGER_PROMOTED",
            "installedIdentity": installed_identity,
            "archivedBaselinePath": stabilization["archivedBaselinePath"],
            "health": health_result,
            "recoveryRoot": str(recovery),
            "transactionPath": str(transaction_path),
            "mutations": len(steps) + 3,
        }
    except BaseException as error:
        steps.append({"name": "promotion-failure", "status": "BLOCKED", "detail": str(error)[:2048]})
        return _rollback_manager_promotion(plan, host, recovery, steps, error, failure_point)
