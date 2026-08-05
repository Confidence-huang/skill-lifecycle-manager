"""
Immutable stable-use baselines and read-only health comparison.

Stabilize gathers committed manager identity, Registry/report hashes, physical inventory, source Git
states, activity-link identity, and a complete recovery manifest. Health rebuilds those facts without
writing or fetching and reports each comparison separately so drift is never hidden behind one score.
"""

from __future__ import annotations  # Keep type annotations stable on Python 3.12.

import hashlib  # Fingerprint each source worktree status without conflating it with commit identity.
import json  # Read canonical Registry, project profiles, manifests, and frozen baselines.
import os  # Record the literal activity symbolic-link target.
import shutil  # Preserve an explicitly superseded baseline byte-for-byte in history.
import subprocess  # Read local Git state without a shell or remote fetch.
from datetime import datetime, timezone  # Timestamp immutable evidence and history names.
from pathlib import Path  # Resolve manager, project, Registry, and backup identities.
from typing import Any  # Describe structured baseline and health documents.

from skill_lifecycle.inventory import inventory_fingerprint, scan_skills  # Rebuild live physical identity.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_json, sha256_file  # Share safe persistence.


def git_output(repository: Path, *arguments: str) -> str | None:
    """Read one local Git fact and return None when the repository cannot prove it."""
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def manager_repository() -> Path:
    """Resolve the Git repository that owns the installed Python package."""
    package_root = Path(__file__).resolve().parents[2]  # Editable uv tools resolve back into src/.
    top_level = git_output(package_root, "rev-parse", "--show-toplevel")
    if not top_level:
        raise LifecycleBlocked(f"Installed manager is not inside a Git repository: {package_root}")
    return Path(top_level).resolve()


def source_states(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Capture each unique managed source's local commit and dirty fingerprint."""
    states: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in registry.get("skills", []):
        repository_text = record.get("sourceRepository")
        if not repository_text or repository_text in seen:
            continue
        seen.add(repository_text)
        repository = Path(repository_text)
        status = git_output(repository, "status", "--porcelain=v1")
        states.append(
            {
                "path": str(repository.resolve()),
                "commit": git_output(repository, "rev-parse", "HEAD"),
                "status": status,
                "statusSHA256": hashlib.sha256((status or "").encode("utf-8")).hexdigest().upper(),
            }
        )
    return sorted(states, key=lambda item: item["path"])


def newest_complete_backup(layout: HostLayout) -> dict[str, Any]:
    """Resolve the newest readable version-1 backup manifest as recovery evidence."""
    backup_root = layout.data_root / "backups"
    candidates = sorted(backup_root.glob("*/backup-manifest.json"), reverse=True) if backup_root.is_dir() else []
    for manifest_path in candidates:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("schemaVersion") == 1:
            return {"manifestPath": str(manifest_path), "manifestSHA256": sha256_file(manifest_path), "fileCount": len(manifest.get("files", [])), "linkCount": len(manifest.get("links", []))}
    raise LifecycleBlocked("No complete version-1 capability backup is available.")


def collect_baseline(layout: HostLayout) -> dict[str, Any]:
    """Build complete stable-use evidence without writing it."""
    required_files = [layout.registry_path, layout.registry_yaml_path, layout.capability_report_path, layout.governance_report_path]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise LifecycleBlocked(f"Stable evidence files are missing: {missing}")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
    live = scan_skills(Path(root) for root in registry.get("roots", []))
    manager = manager_repository()
    manager_status = git_output(manager, "status", "--porcelain=v1")
    if manager_status:
        raise LifecycleBlocked(f"Manager source is dirty: {manager}")
    activity = layout.activity_root / "skill-lifecycle-manager"
    if not activity.is_symlink():
        raise LifecycleBlocked(f"Manager activity is not a symbolic link: {activity}")
    activity_target = activity.resolve(strict=True)
    if activity_target != manager:
        raise LifecycleBlocked(f"Manager activity target does not match installed source: {activity_target}")
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_STABLE_USE",
        "platform": "linux",
        "manager": {
            "repository": str(manager),
            "commit": git_output(manager, "rev-parse", "HEAD"),
            "status": manager_status or "",
            "activityPath": str(activity),
            "activityTarget": os.readlink(activity),
            "activityResolvedTarget": str(activity_target),
            "runtime": "Python 3.12 + uv",
        },
        "registry": {
            "path": str(layout.registry_path),
            "sha256": sha256_file(layout.registry_path),
            "yamlPath": str(layout.registry_yaml_path),
            "yamlSHA256": sha256_file(layout.registry_yaml_path),
            "capabilityReportPath": str(layout.capability_report_path),
            "capabilityReportSHA256": sha256_file(layout.capability_report_path),
            "governanceReportPath": str(layout.governance_report_path),
            "governanceReportSHA256": sha256_file(layout.governance_report_path),
            "inventoryFingerprint": inventory_fingerprint(live["skills"]),
            "summary": live["summary"],
        },
        "sources": source_states(registry),
        "backup": newest_complete_backup(layout),
        "boundaries": {
            "automaticInstall": False,
            "automaticUpdate": False,
            "automaticDelete": False,
            "automaticRepair": False,
            "automaticGrading": False,
            "automaticRouting": False,
            "upstreamFreshness": "UNKNOWN_NOT_FETCHED",
        },
    }


def stabilize(layout: HostLayout, apply: bool, archive_existing: bool) -> dict[str, Any]:
    """Preview or publish one explicit immutable host-local baseline."""
    baseline = collect_baseline(layout)
    if not apply:
        return {"status": "PASS", "action": "STABILIZE_PREVIEW", "baselinePath": str(layout.baseline_path), "baseline": baseline, "mutations": 0}
    archived_path = None
    if layout.baseline_path.exists():
        if not archive_existing:
            raise LifecycleBlocked(f"Baseline already exists: {layout.baseline_path}; use --archive-existing for an explicit preserved rebaseline.")
        history = layout.state_root / "baseline-history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archived_path = history / f"skill-stability-baseline-pre-python-{stamp}.json"
        shutil.copy2(layout.baseline_path, archived_path)  # Preserve the prior bytes before replacement.
        if sha256_file(archived_path) != sha256_file(layout.baseline_path):
            raise LifecycleBlocked("Archived baseline failed byte-for-byte verification.")
    atomic_json(layout.baseline_path, baseline)
    return {"status": "PASS", "action": "STABILIZED", "baselinePath": str(layout.baseline_path), "archivedBaselinePath": str(archived_path) if archived_path else None, "mutations": 2 if archived_path else 1}


def check_project(project_root: Path | None, registry: dict[str, Any]) -> dict[str, Any]:
    """Validate the optional project's continuity file and declared Skill working set."""
    if project_root is None:
        return {"status": "NOT_CONFIGURED", "declared": 0, "present": 0, "issues": []}
    root = Path(project_root).expanduser().resolve(strict=True)
    issues: list[str] = []
    if not (root / "PROJECT_LOG.md").is_file():
        issues.append("PROJECT_LOG.md is missing.")
    profile_path = root / "project-skill-profile.json"
    if not profile_path.is_file():
        issues.append("project-skill-profile.json is missing.")
        return {"status": "UNKNOWN", "declared": 0, "present": 0, "issues": issues}
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    declared = profile.get("skills", profile.get("workingSet", []))
    names = {record["name"] for record in registry.get("skills", [])}
    declared_names = [item if isinstance(item, str) else item.get("name") for item in declared]
    missing = [name for name in declared_names if name and name not in names]
    issues.extend(f"Declared Skill is missing: {name}" for name in missing)
    return {"status": "PASS" if not issues else "BLOCKED", "declared": len([name for name in declared_names if name]), "present": len([name for name in declared_names if name in names]), "issues": issues}


def health(layout: HostLayout, project_root: Path | None = None) -> dict[str, Any]:
    """Compare live local evidence with the frozen baseline without any write or fetch."""
    if not layout.baseline_path.is_file():
        raise LifecycleBlocked(f"Stability baseline is missing: {layout.baseline_path}")
    baseline = json.loads(layout.baseline_path.read_text(encoding="utf-8"))
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8")) if layout.registry_path.is_file() else {}
    roots = [Path(root) for root in registry.get("roots", [])]
    live = scan_skills(roots)
    manager = Path(baseline["manager"]["repository"])
    manager_activity = Path(baseline["manager"]["activityPath"])
    checks = {
        "platform": baseline.get("platform") == "linux",
        "managerCommit": git_output(manager, "rev-parse", "HEAD") == baseline["manager"].get("commit"),
        "managerClean": (git_output(manager, "status", "--porcelain=v1") or "") == "",
        "activitySymbolicLink": manager_activity.is_symlink() and str(manager_activity.resolve(strict=True)) == baseline["manager"].get("activityResolvedTarget"),
        "registrySHA256": layout.registry_path.is_file() and sha256_file(layout.registry_path) == baseline["registry"].get("sha256"),
        "yamlSHA256": layout.registry_yaml_path.is_file() and sha256_file(layout.registry_yaml_path) == baseline["registry"].get("yamlSHA256"),
        "capabilityReportSHA256": layout.capability_report_path.is_file() and sha256_file(layout.capability_report_path) == baseline["registry"].get("capabilityReportSHA256"),
        "governanceReportSHA256": layout.governance_report_path.is_file() and sha256_file(layout.governance_report_path) == baseline["registry"].get("governanceReportSHA256"),
        "inventoryFingerprint": inventory_fingerprint(live["skills"]) == baseline["registry"].get("inventoryFingerprint"),
        "brokenLinks": live["summary"].get("brokenLinks") == 0,
    }
    baseline_sources = {item["path"]: item for item in baseline.get("sources", [])}
    current_sources = {item["path"]: item for item in source_states(registry)}
    checks["localSourceState"] = current_sources == baseline_sources
    backup = baseline.get("backup", {})
    backup_path = Path(backup.get("manifestPath", ""))
    checks["recoveryManifest"] = backup_path.is_file() and sha256_file(backup_path) == backup.get("manifestSHA256")
    project = check_project(project_root, registry)
    if project_root is not None:
        checks["projectWorkingSet"] = project["status"] == "PASS"
    return {
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "action": "HEALTH_CHECKED",
        "checks": checks,
        "live": live["summary"],
        "project": project,
        "runtimeBehavior": "NOT_RUN",
        "upstreamFreshness": "UNKNOWN_NOT_FETCHED",
        "mutations": 0,
    }
