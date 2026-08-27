"""
Transactional install, update, backup, and restore operations for Windows and Linux Skill assets.

Every mutation follows the same visible sequence: inspect the explicit request, prove the target and
collision boundary, change only transaction-owned paths, publish Registry evidence last, and return
the exact effect. Preview paths perform the same inspection without creating live state.
"""

from __future__ import annotations  # Keep annotations stable on Python 3.12.

import json  # Read canonical Registry and completed backup manifests.
import os  # Walk physical trees without following directory links.
import re  # Prevent frontmatter names from becoming unsafe path segments.
import shutil  # Preserve physical package files and executable metadata.
import subprocess  # Run Git through argument arrays rather than shell command strings.
import tempfile  # Isolate install and update candidates under the transaction cache.
from datetime import datetime, timezone  # Name backups uniquely in UTC.
from pathlib import Path  # Enforce POSIX containment and empty-destination rules.
from typing import Any, Iterable  # Describe command feedback and explicit path collections.

from skill_lifecycle.inventory import read_package_record, read_skill, write_registry  # Validate entries, PACKAGE provenance, and final Registry evidence.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_json, sha256_file  # Enforce shared stop gates.
from skill_lifecycle.platforms import current_platform


def run_git(path: Path | None, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one Git command with bounded captured feedback and no shell interpolation."""
    command = ["git"]  # The executable is resolved through the current reviewed PATH.
    if path is not None:
        command.extend(["-C", str(path)])  # Keep repository identity explicit for every operation.
    command.extend(arguments)
    return subprocess.run(command, text=True, capture_output=True, check=False)


def find_candidate(root: Path, skill_path: str | None) -> Path:
    """Resolve exactly one eligible Skill inside a staged source tree."""
    owner = root.resolve(strict=True)
    if skill_path:
        candidate = (owner / skill_path).resolve(strict=True)
        if candidate != owner and owner not in candidate.parents:
            raise LifecycleBlocked("Skill path escapes the staged source root.")
        if not (candidate / "SKILL.md").is_file():
            raise LifecycleBlocked(f"Skill entry is missing: {candidate / 'SKILL.md'}")
        return candidate
    candidates = sorted(path.parent for path in owner.rglob("SKILL.md"))
    if len(candidates) != 1:
        raise LifecycleBlocked(f"Expected one Skill entry, found {len(candidates)}; provide --skill-path.")
    return candidates[0]


def inspect_install(layout: HostLayout, source: str, mode: str, skill_path: str | None) -> dict[str, Any]:
    """Stage and classify an install request without touching activity, source, or Registry state."""
    with tempfile.TemporaryDirectory(prefix="skill-lifecycle-inspect-") as temporary:
        staged = Path(temporary) / "source"
        local_source = Path(source).expanduser()
        if local_source.exists():
            shutil.copytree(local_source, staged, symlinks=True)  # Preserve Git and link evidence in inspection.
        else:
            completed = run_git(None, "clone", "--", source, str(staged))
            if completed.returncode:
                raise LifecycleBlocked(f"Git clone failed: {completed.stderr.strip()}")
        candidate = find_candidate(staged, skill_path)
        name, _, issues = read_skill(candidate / "SKILL.md")
        if issues and any("frontmatter" in issue.lower() for issue in issues):
            raise LifecycleBlocked(f"Candidate Skill metadata is invalid: {issues}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise LifecycleBlocked(f"Unsafe Skill name: {name}")
        detected = "source" if (staged / ".git").is_dir() else "package"
        selected = detected if mode == "auto" else mode.lower()
        if selected not in {"package", "source", "hybrid"}:
            raise LifecycleBlocked(f"Unsupported install mode: {mode}")
        if selected == "package":
            _, _, package_issues = read_package_record(candidate)  # Preview validates the same provenance applied installation will preserve.
            if package_issues:
                raise LifecycleBlocked(f"Candidate PACKAGE provenance is invalid: {package_issues}")
        activity = layout.activity_root / name
        owner = layout.activity_root if selected == "package" else layout.data_root / "sources"
        destination = activity if selected == "package" else owner / name
        if layout.platform.link_exists(destination):
            raise LifecycleBlocked(f"Destination already exists: {destination}")
        if activity != destination and layout.platform.link_exists(activity):
            raise LifecycleBlocked(f"Activity entry already exists: {activity}")
        relative_skill = candidate.relative_to(staged.resolve(strict=True))
        return {
            "status": "PASS",
            "action": "INSTALL_PREVIEW",
            "name": name,
            "mode": selected.upper(),
            "destination": str(destination),
            "activityPath": str(activity),
            "relativeSkillPath": str(relative_skill),
            "mutations": 0,
        }


def install_skill(layout: HostLayout, source: str, mode: str = "auto", skill_path: str | None = None) -> dict[str, Any]:
    """Install one package or Git source and roll back only transaction-created live paths."""
    preview = inspect_install(layout, source, mode, skill_path)  # Prove identity and collisions before writes.
    selected = preview["mode"].lower()
    owner = Path(preview["destination"]).parent
    destination = Path(preview["destination"])
    activity = Path(preview["activityPath"])
    created_activity: Path | None = None
    created_destination: Path | None = None
    layout.cache_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="install-", dir=layout.cache_root) as temporary:
        staged = Path(temporary) / "source"
        local_source = Path(source).expanduser()
        if local_source.exists():
            shutil.copytree(local_source, staged, symlinks=True)
        else:
            completed = run_git(None, "clone", "--", source, str(staged))
            if completed.returncode:
                raise LifecycleBlocked(f"Git clone failed: {completed.stderr.strip()}")
        candidate = find_candidate(staged, skill_path)
        relative_skill = candidate.relative_to(staged.resolve(strict=True))
        candidate_updates = None  # SOURCE/HYBRID entries never consume PACKAGE-only provenance.
        if selected == "package":
            candidate_package, _, package_issues = read_package_record(candidate)  # Preserve only a validated optional update channel.
            if package_issues:
                raise LifecycleBlocked(f"Candidate PACKAGE provenance is invalid: {package_issues}")
            candidate_updates = candidate_package.get("updates") if candidate_package else None
        try:
            owner.mkdir(parents=True, exist_ok=True)  # This transaction owns its mode-specific destination.
            if selected == "package":
                shutil.copytree(candidate, destination, symlinks=True)
                installed_skill = destination
                created_destination = destination  # PACKAGE activation is the one physical entity.
                remote_result = run_git(candidate, "remote", "get-url", "origin")  # Git-backed packages retain publisher evidence.
                commit_result = run_git(candidate, "rev-parse", "HEAD")  # A full commit pins the copied source snapshot when available.
                lifecycle_record = {
                    "schemaVersion": 1,
                    "lifecycleMode": "PACKAGE",
                    "origin": source,
                    "remote": remote_result.stdout.strip() if remote_result.returncode == 0 else None,
                    "commit": commit_result.stdout.strip() if commit_result.returncode == 0 else None,
                    "selectedSkillPath": str(relative_skill),
                    "installedAt": datetime.now(timezone.utc).isoformat(),
                }
                if candidate_updates:
                    lifecycle_record["updates"] = candidate_updates  # Reviewed release metadata survives PACKAGE copying.
                atomic_json(installed_skill / ".skill-lifecycle.json", lifecycle_record)  # Publish provenance before verification and Registry.
            else:
                shutil.move(str(staged), str(destination))
                installed_skill = destination / relative_skill
                created_destination = destination
                layout.activity_root.mkdir(parents=True, exist_ok=True)
                layout.platform.create_directory_link(installed_skill, activity)
                created_activity = activity

            from skill_lifecycle.verification import verify_target  # Delay import to keep command modules acyclic.

            verification = verify_target(layout, installed_skill, apply=True, install_only=True)
            if verification["status"] != "PASS":
                raise LifecycleBlocked(f"Install verification blocked: {verification.get('reportPath')}")
            registry = write_registry(layout, [layout.activity_root])  # Publish only after activation and probes pass.
        except BaseException:  # Interruption-style failures still clean only paths created above.
            if created_activity and layout.platform.is_directory_link(created_activity):
                layout.platform.remove_directory_link(created_activity)
            if created_destination and created_destination.exists():
                shutil.rmtree(created_destination)  # Preserve every pre-existing neighboring Skill.
            if layout.activity_root.is_dir() and not any(layout.activity_root.iterdir()):
                layout.activity_root.rmdir()
            if owner.is_dir() and not any(owner.iterdir()):
                owner.rmdir()
            raise

    commit = None
    if selected in {"source", "hybrid"}:
        completed = run_git(destination, "rev-parse", "HEAD")
        commit = completed.stdout.strip() if completed.returncode == 0 else None
    return {
        "status": "PASS",
        "action": "INSTALLED",
        "name": preview["name"],
        "mode": preview["mode"],
        "destination": str(destination),
        "activityPath": str(activity),
        "activityTarget": str(installed_skill),
        "commit": commit,
        "registryPath": registry["registryPath"],
        "mutations": registry["mutations"] + (1 if selected == "package" else 2),
    }


def registry_record(layout: HostLayout, name: str) -> dict[str, Any]:
    """Resolve one unambiguous lifecycle record from the canonical Registry."""
    if not layout.registry_path.is_file():
        raise LifecycleBlocked(f"Registry is missing: {layout.registry_path}")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
    records = [record for record in registry.get("skills", []) if record.get("name") == name]
    if len(records) != 1:
        raise LifecycleBlocked(f"Expected one Registry record named {name}, found {len(records)}.")
    return records[0]


def update_skill(
    layout: HostLayout,
    name: str,
    apply: bool,
    approval_path: Path | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Route one Registry entity through its native Skill or PACKAGE transaction."""
    record = registry_record(layout, name)
    if record.get("lifecycleMode") == "PACKAGE":
        from skill_lifecycle.package_transaction import update_package

        return update_package(layout, record, apply, approval_path, evaluated_at)
    if record.get("lifecycleMode") not in {"SOURCE", "HYBRID"} or not record.get("sourceRepository"):
        raise LifecycleBlocked(
            f"Lifecycle update is supported, but {name} has no source or PACKAGE transaction contract."
        )
    repository = Path(record["sourceRepository"]).resolve(strict=True)
    if run_git(repository, "status", "--porcelain=v1").stdout.strip():
        raise LifecycleBlocked(f"Source repository is dirty: {repository}")
    remote = record.get("remote")
    branch = record.get("branch")
    current = run_git(repository, "rev-parse", "HEAD").stdout.strip()
    if not remote or not branch:
        raise LifecycleBlocked(f"Source repository lacks origin or branch evidence: {repository}")
    remote_result = run_git(repository, "ls-remote", "--heads", "origin", branch)
    if remote_result.returncode or not remote_result.stdout.strip():
        raise LifecycleBlocked(f"Cannot resolve origin/{branch}: {remote_result.stderr.strip()}")
    candidate = remote_result.stdout.split()[0]
    preview = {"status": "PASS", "action": "UPDATE_PREVIEW", "name": name, "current": current, "candidate": candidate, "mutations": 0}
    if not apply or candidate == current:
        return preview
    if name == "skill-lifecycle-manager":
        raise LifecycleBlocked(
            "Manager self-update is preview-only in the generic update command; "
            "use the reviewed host-specific manager promotion workflow."
        )

    from skill_lifecycle.guardian import require_guardian_approval  # Delay import so scanning can reuse Git without a module cycle.

    require_guardian_approval(
        layout,
        approval_path,
        name,
        current,
        candidate,
        evaluated_at,
    )  # Human authority is proved before fetch creates even local candidate objects.

    fetched = run_git(repository, "fetch", "--no-tags", "origin", branch)
    if fetched.returncode:
        raise LifecycleBlocked(f"Git fetch failed: {fetched.stderr.strip()}")
    ancestry = run_git(repository, "merge-base", "--is-ancestor", current, candidate)
    if ancestry.returncode:
        raise LifecycleBlocked("Candidate is not a fast-forward descendant of the current commit.")
    layout.cache_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="update-", dir=layout.cache_root) as temporary:
        worktree = Path(temporary) / "candidate"
        added = run_git(repository, "worktree", "add", "--detach", str(worktree), candidate)
        if added.returncode:
            raise LifecycleBlocked(f"Detached candidate worktree failed: {added.stderr.strip()}")
        try:
            relative_skill = Path(record["physicalPath"]).resolve().relative_to(repository)
            skill_path = None if str(relative_skill) == "." else str(relative_skill)
            find_candidate(worktree, skill_path)  # Validate the same entry inside a multi-Skill candidate.
        finally:
            run_git(repository, "worktree", "remove", "--force", str(worktree))
    fast_forward = run_git(repository, "merge", "--ff-only", candidate)
    if fast_forward.returncode:
        raise LifecycleBlocked(f"Fast-forward failed: {fast_forward.stderr.strip()}")
    try:
        registry = write_registry(layout, [layout.activity_root])  # Registry publication remains the final mutation.
    except BaseException as error:
        rollback = run_git(repository, "reset", "--hard", current)  # The preflight clean commit is the exact rollback point.
        if rollback.returncode:
            detail = rollback.stderr.strip() or rollback.stdout.strip()
            raise LifecycleBlocked(f"Registry publication failed and update rollback failed: {detail}") from error
        raise
    return {**preview, "action": "UPDATED", "current": candidate, "registryPath": registry["registryPath"], "mutations": registry["mutations"] + 1}


def backup_preview(layout: HostLayout, paths: Iterable[Path]) -> dict[str, Any]:
    """Validate explicit backup roots and count physical files and links without writing."""
    backup_root = layout.data_root / "backups"
    sources = [Path(path).expanduser() for path in paths]
    resolved_backup_root = backup_root.resolve()
    file_count = 0
    link_count = 0
    for source in sources:
        if not layout.platform.link_exists(source):
            raise LifecycleBlocked(f"Backup source is missing: {source}")
        if not layout.platform.is_directory_link(source) and not source.is_dir():
            raise LifecycleBlocked(f"Backup source must be a directory or symbolic link: {source}")
        if not layout.platform.is_directory_link(source) and resolved_backup_root.is_relative_to(source.resolve()):
            raise LifecycleBlocked(f"Backup source contains the backup destination and would recurse: {source}")
        if layout.platform.is_directory_link(source):
            link_count += 1
            continue
        for directory, child_directories, child_files in os.walk(source, followlinks=False):
            directory_path = Path(directory)
            linked_directories = [
                name for name in child_directories
                if layout.platform.is_directory_link(directory_path / name)
            ]
            link_count += len(linked_directories)
            child_directories[:] = [name for name in child_directories if name not in linked_directories]
            for child in child_files:
                if (directory_path / child).is_symlink():
                    link_count += 1
                else:
                    file_count += 1
    return {"status": "PASS", "action": "BACKUP_PREVIEW", "roots": [str(source) for source in sources], "fileCount": file_count, "linkCount": link_count, "mutations": 0}


def create_backup(layout: HostLayout, paths: Iterable[Path]) -> dict[str, Any]:
    """Copy physical files once and record every symbolic link without following it."""
    preview = backup_preview(layout, paths)
    sources = [Path(path).expanduser() for path in paths]
    backup_root = layout.data_root / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_root / f"ai-capabilities-{stamp}"
    destination.mkdir()
    files: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []
    for index, source in enumerate(sources):
        slot = destination / f"root-{index:03d}-{source.name}"
        if layout.platform.is_directory_link(source):
            links.append({"source": str(source), "target": layout.platform.link_target(source), "backupRelative": str(slot.relative_to(destination))})
            continue
        slot.mkdir(parents=True)
        for directory, child_directories, child_files in os.walk(source, followlinks=False):
            directory_path = Path(directory)
            relative_directory = directory_path.relative_to(source)
            target_directory = slot / relative_directory
            target_directory.mkdir(parents=True, exist_ok=True)
            for child in list(child_directories):
                child_path = directory_path / child
                if layout.platform.is_directory_link(child_path):
                    links.append({"source": str(child_path), "target": layout.platform.link_target(child_path), "backupRelative": str((target_directory / child).relative_to(destination))})
                    child_directories.remove(child)
            for child in child_files:
                source_file = directory_path / child
                backup_file = target_directory / child
                if source_file.is_symlink():
                    links.append({"source": str(source_file), "target": os.readlink(source_file), "backupRelative": str(backup_file.relative_to(destination))})
                    continue
                shutil.copy2(source_file, backup_file)
                files.append({"source": str(source_file), "backupRelative": str(backup_file.relative_to(destination)), "sha256": sha256_file(backup_file), "mode": oct(backup_file.stat().st_mode & 0o777)})
    manifest = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(), "roots": preview["roots"], "files": files, "links": links}
    atomic_json(destination / "backup-manifest.json", manifest)  # Manifest publication proves completion.
    return {"status": "PASS", "action": "BACKED_UP", "backupPath": str(destination), "fileCount": len(files), "linkCount": len(links), "mutations": len(files) + 2}


def validate_restore(backup_path: Path, destination: Path) -> tuple[Path, Path, dict[str, Any], list[tuple[dict[str, Any], Path, Path]]]:
    """Verify every backup hash and target path before creating the destination."""
    backup = Path(backup_path).expanduser().resolve(strict=True)
    manifest_path = backup / "backup-manifest.json"
    if not manifest_path.is_file():
        raise LifecycleBlocked(f"Backup manifest is missing: {manifest_path}")
    target = Path(destination).expanduser()
    if current_platform().is_directory_link(target):
        raise LifecycleBlocked(f"Restore destination must be a physical directory: {target}")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise LifecycleBlocked(f"Restore destination is not empty: {target}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1:
        raise LifecycleBlocked("Unsupported backup manifest schema.")
    verified: list[tuple[dict[str, Any], Path, Path]] = []
    for record in manifest.get("files", []):
        relative = Path(record["backupRelative"])
        if relative.is_absolute() or ".." in relative.parts:
            raise LifecycleBlocked(f"Backup manifest contains an unsafe relative path: {relative}")
        backup_file = (backup / relative).resolve(strict=True)
        if backup not in backup_file.parents or not backup_file.is_file():
            raise LifecycleBlocked(f"Backup file escapes or is missing: {backup_file}")
        if sha256_file(backup_file) != record["sha256"]:
            raise LifecycleBlocked(f"Backup file failed verification: {backup_file}")
        verified.append((record, backup_file, relative))
    return backup, target, manifest, verified


def restore_backup(backup_path: Path, destination: Path, apply: bool) -> dict[str, Any]:
    """Preview or restore verified physical files into one empty destination."""
    _, target, manifest, verified = validate_restore(backup_path, destination)
    if apply:
        target.mkdir(parents=True, exist_ok=True)
        for record, backup_file, relative in verified:
            restored_file = target / relative
            restored_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, restored_file)
            restored_file.chmod(int(record["mode"], 8))
    return {
        "status": "PASS",
        "action": "RESTORED" if apply else "RESTORE_PREVIEW",
        "destination": str(target),
        "fileCount": len(verified),
        "linksForReview": manifest.get("links", []),
        "mutations": len(verified) + 1 if apply else 0,
    }
