"""
Run one reviewed V5 capability pilot without replacing Registry v1 or the stable baseline.

The public flow is deliberately split into approval, activation, verification, and rollback. Each
command previews by default. Applied commands retain artifact-bound decisions, lock revisions,
immutable transaction events, exact Registry/report preimages, and bounded probe output.

Typical flow:
    approval = approve_pilot(host, request, apply=False)
    approval = approve_pilot(host, request, apply=True)
    activation = activate_pilot(host, request, apply=True)
    verification = verify_pilot(host, transaction_id, probe_plan, apply=True)
    rollback = rollback_pilot(host, request, apply=True)
"""

from __future__ import annotations  # Keep Python 3.12 annotations visible without runtime wrappers.

import hashlib  # Bind probe plans and exact state preimages to SHA256 evidence.
import json  # Read immutable manifests, evidence, journals, locks, and transaction events.
import os  # Create and inspect the one reviewed Linux activity symbolic link.
import re  # Reject identifiers that cannot satisfy the frozen V5 Schemas.
import shutil  # Copy exact preimages into a transaction-owned audit directory.
import subprocess  # Run Git identity checks and bounded verification probes without a shell.
import sys  # Expand the candidate interpreter in portable probe plans.
import tempfile  # Assemble durable transaction evidence before publishing its directory.
from pathlib import Path  # Keep every source, state, activity, and evidence path explicit.
from typing import Any  # Expose the JSON-compatible command contracts directly.

from skill_lifecycle.contracts import (
    ContractBlocked,
    compute_artifact_id,
    compute_tree_sha256,
    encode_json_line,
    parse_timestamp,
    require_current_approval,
)  # Reuse the frozen artifact and approval semantics instead of inventing pilot-only identity.
from skill_lifecycle.inventory import (
    capability_report,
    governance_report,
    read_skill,
    scan_skills,
)  # Generate all four observed-state views from one post-activation scan.
from skill_lifecycle.paths import (
    HostLayout,
    LifecycleBlocked,
    atomic_bytes,
    atomic_json,
    atomic_text,
    sha256_file,
)  # Share host roots, atomic publication, and the product stop gate.
from skill_lifecycle.shadow import committed_tree_entries, read_json_object  # Recheck the exact Git tree and strict JSON inputs.


POLICY_VERSION = "v5-phase-d-pilot-v1"  # One reviewed policy label binds decisions and lock revisions.
DECISION_ID = re.compile(r"^decision-[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
TRANSACTION_ID = re.compile(r"^transaction-[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
HOST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATE_FILES = {
    "skills-registry.json": "state/skills-registry.json",
    "skills-registry.yaml": "state/skills-registry.yaml",
    "skill-capability-report.md": "state/skill-capability-report.md",
    "skill-governance-report.md": "state/skill-governance-report.md",
}  # Only these four existing observed-state views may change during the temporary activation.


# --- Enforce Schema-compatible identifiers before publishing durable records ---
def require_match(value: Any, pattern: re.Pattern[str], label: str) -> str:
    """Return one bounded identifier only when it matches the frozen contract exactly."""
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise LifecycleBlocked(f"{label} does not match the V5 contract: {value}")
    return value


# --- Read append-only decisions without accepting malformed lines ---
def read_decisions(host: HostLayout) -> list[dict[str, Any]]:
    """Return the complete decision journal while preserving an absent journal as an empty history."""
    path = host.decision_journal_path
    if not path.exists():  # A first pilot legitimately starts without V5 state.
        return []
    decisions: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise LifecycleBlocked(f"Decision journal contains a blank record at line {number}.")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise LifecycleBlocked(f"Decision journal is invalid at line {number}: {error}") from error
        if not isinstance(record, dict):
            raise LifecycleBlocked(f"Decision journal record {number} is not an object.")
        decisions.append(record)
    return decisions


# --- Read the current host-local desired-state lock ---
def read_lock(host: HostLayout) -> dict[str, Any] | None:
    """Return the current lock document without creating the V5 state root."""
    if not host.capability_lock_path.exists():
        return None
    lock, _ = read_json_object(host.capability_lock_path)
    if lock.get("schemaVersion") != 1 or lock.get("documentType") != "AI_CAPABILITY_LOCK":
        raise LifecycleBlocked("Capability lock identity is unsupported.")
    if not isinstance(lock.get("revision"), int) or lock["revision"] < 1:
        raise LifecycleBlocked("Capability lock revision is invalid.")
    if not isinstance(lock.get("entries"), list):
        raise LifecycleBlocked("Capability lock entries must be an array.")
    return lock


# --- Retain every desired-state revision before moving the current lock pointer ---
def publish_lock(host: HostLayout, lock: dict[str, Any]) -> int:
    """Publish one immutable revision plus the current lock, accepting only an exact retry."""
    revision_path = host.capability_lock_history_root / f"capability-lock-r{lock['revision']:06d}.json"
    mutations = 0
    if revision_path.exists() or revision_path.is_symlink():
        if revision_path.is_symlink() or not revision_path.is_file():
            raise LifecycleBlocked(f"Capability lock revision path is unsafe: {revision_path}")
        existing, _ = read_json_object(revision_path)
        if existing != lock:
            raise LifecycleBlocked(f"Capability lock revision collision: {revision_path}")
    else:
        atomic_json(revision_path, lock)
        mutations += 1
    current = read_lock(host)
    if current != lock:
        atomic_json(host.capability_lock_path, lock)
        mutations += 1
    return mutations


# --- Validate immutable artifact and evidence inputs ---
def read_artifact_evidence(manifest_path: Path, evidence_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prove artifact identity, complete-tree identity, and one PASS provenance evidence record."""
    manifest, _ = read_json_object(Path(manifest_path))
    evidence, _ = read_json_object(Path(evidence_path))
    if manifest.get("schemaVersion") != 1 or manifest.get("documentType") != "CAPABILITY_ARTIFACT_MANIFEST":
        raise LifecycleBlocked("Artifact manifest identity is unsupported.")
    identity = manifest.get("identity")
    tree_entries = manifest.get("treeEntries")
    if not isinstance(identity, dict) or not isinstance(tree_entries, list):
        raise LifecycleBlocked("Artifact manifest lacks identity or tree entries.")
    try:
        artifact_id = compute_artifact_id(identity)
        tree_sha256 = compute_tree_sha256(tree_entries)
    except ContractBlocked as error:
        raise LifecycleBlocked(str(error)) from error
    if artifact_id != manifest.get("artifactID"):
        raise LifecycleBlocked("Artifact manifest ID does not match its canonical identity.")
    if tree_sha256 != identity.get("contentSHA256"):
        raise LifecycleBlocked("Artifact manifest content hash does not match its logical tree.")
    if evidence.get("schemaVersion") != 1 or evidence.get("documentType") != "CAPABILITY_EVIDENCE":
        raise LifecycleBlocked("Capability evidence identity is unsupported.")
    if evidence.get("artifactID") != artifact_id or evidence.get("skillName") != manifest.get("skillName"):
        raise LifecycleBlocked("Capability evidence does not match the selected artifact.")
    if evidence.get("probeStatus") != "PASS" or not isinstance(evidence.get("evidenceID"), str):
        raise LifecycleBlocked("Capability evidence is not one named PASS record.")
    report_path = Path(evidence_path).resolve().parents[2] / str(evidence.get("reportPath", ""))
    if not report_path.is_file() or sha256_file(report_path).lower() != evidence.get("reportSHA256"):
        raise LifecycleBlocked("Capability evidence report bytes do not match their SHA256 reference.")
    return manifest, evidence


# --- Prove the selected source checkout still represents the approved artifact ---
def validate_repository(manifest: dict[str, Any], repository_path: Path) -> Path:
    """Return the physical Skill root after checking Git remote, commit, clean tree, and content hash."""
    repository = Path(repository_path).resolve(strict=True)

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )  # Argument arrays keep the reviewed repository path out of shell parsing.
        if completed.returncode:
            raise LifecycleBlocked(f"Git identity query failed: {completed.stderr.strip()}")
        return completed.stdout.strip()

    identity = manifest["identity"]
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repository:
        raise LifecycleBlocked("Pilot repository path is not its Git top level.")
    if git("status", "--porcelain=v1"):
        raise LifecycleBlocked(f"Pilot source repository is dirty: {repository}")
    if git("rev-parse", "HEAD") != identity.get("resolvedCommit"):
        raise LifecycleBlocked("Pilot source commit differs from the approved artifact.")
    if git("remote", "get-url", "origin") != identity.get("canonicalSource"):
        raise LifecycleBlocked("Pilot source remote differs from the approved artifact.")
    if compute_tree_sha256(committed_tree_entries(repository)) != identity.get("contentSHA256"):
        raise LifecycleBlocked("Pilot source logical tree differs from the approved artifact.")
    skill_path = identity.get("skillPath")
    skill_root = repository if skill_path == "." else repository / str(skill_path)
    if not skill_root.is_dir() or not (skill_root / "SKILL.md").is_file():
        raise LifecycleBlocked(f"Pilot Skill entry is missing: {skill_root}")
    name, _, issues = read_skill(skill_root / "SKILL.md")
    if name != manifest.get("skillName") or issues:
        raise LifecycleBlocked(f"Pilot Skill entry does not match the artifact: {issues}")
    return skill_root


# --- Preserve or append one immutable decision record ---
def append_decision(host: HostLayout, decision: dict[str, Any]) -> int:
    """Append one new canonical JSON line, or accept an identical already-published retry."""
    decisions = read_decisions(host)
    matching = [record for record in decisions if record.get("decisionID") == decision["decisionID"]]
    if matching:
        if len(matching) != 1 or matching[0] != decision:
            raise LifecycleBlocked(f"Decision ID collision: {decision['decisionID']}")
        return 0  # An exact retry changes no journal byte.
    text = "".join(encode_json_line(record) for record in [*decisions, decision])
    atomic_text(host.decision_journal_path, text)
    return 1


# --- Build one approval plus ACTIVE lock revision ---
def approval_preview(host: HostLayout, request: dict[str, Any]) -> dict[str, Any]:
    """Validate one exact approval request and return its decision and lock with zero writes."""
    manifest, evidence = read_artifact_evidence(request["manifestPath"], request["evidencePath"])
    require_match(request["decisionID"], DECISION_ID, "Decision ID")
    require_match(request["hostID"], HOST_ID, "Host ID")
    requested_at = parse_timestamp(request["requestedAt"])
    decided_at = parse_timestamp(request["decidedAt"])
    expires_at = parse_timestamp(request["expiresAt"])
    if decided_at < requested_at or expires_at <= decided_at:
        raise LifecycleBlocked("Approval times must satisfy requestedAt <= decidedAt < expiresAt.")
    decision = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_APPROVAL_DECISION",
        "decisionID": request["decisionID"],
        "artifactID": manifest["artifactID"],
        "skillName": manifest["skillName"],
        "requestedBy": request["requestedBy"],
        "requestedAt": request["requestedAt"],
        "decision": "APPROVED",
        "decidedBy": request["decidedBy"],
        "decidedAt": request["decidedAt"],
        "policyVersion": POLICY_VERSION,
        "evidenceRefs": [evidence["evidenceID"]],
        "reason": request["reason"],
        "expiresAt": request["expiresAt"],
        "supersedesDecisionID": None,
    }
    if not all(isinstance(decision[field], str) and decision[field] for field in ("decisionID", "requestedBy", "decidedBy", "reason")):
        raise LifecycleBlocked("Approval identifiers, actors, and reason must be non-empty strings.")
    if len(decision["requestedBy"]) > 256 or len(decision["decidedBy"]) > 256 or len(decision["reason"]) > 4096:
        raise LifecycleBlocked("Approval actor or reason exceeds the V5 contract limit.")
    decisions = read_decisions(host)
    collision = [record for record in decisions if record.get("decisionID") == decision["decisionID"]]
    if collision and (len(collision) != 1 or collision[0] != decision):
        raise LifecycleBlocked(f"Decision ID collision: {decision['decisionID']}")
    current_lock = read_lock(host)
    if current_lock is not None and current_lock.get("hostID") != request["hostID"]:
        raise LifecycleBlocked("Capability lock belongs to another host ID.")
    entries = [] if current_lock is None else [entry for entry in current_lock["entries"] if entry.get("name") != manifest["skillName"]]
    desired_entry = {
        "name": manifest["skillName"],
        "artifactID": manifest["artifactID"],
        "desiredLifecycleMode": "SOURCE",
        "desiredActivity": "ACTIVE",
        "targetScopes": ["USER"],
        "targetAgents": ["CODEX"],
        "approvalDecisionID": decision["decisionID"],
        "policyVersion": POLICY_VERSION,
        "rollbackArtifactID": None,
    }
    entries.append(desired_entry)
    ordered_entries = sorted(entries, key=lambda item: item["name"])
    next_lock = {
        "schemaVersion": 1,
        "documentType": "AI_CAPABILITY_LOCK",
        "hostID": request["hostID"],
        "revision": 1 if current_lock is None else current_lock["revision"] + 1,
        "updatedAt": request["decidedAt"],
        "entries": ordered_entries,
    }
    lock = current_lock if current_lock and current_lock.get("hostID") == request["hostID"] and current_lock.get("entries") == ordered_entries else next_lock
    return {"status": "PASS", "action": "PILOT_APPROVAL_PREVIEW", "decision": decision, "lock": lock, "mutations": 0}


def approve_pilot(host: HostLayout, request: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Preview or publish one append-only approval and the matching ACTIVE desired-state lock."""
    preview = approval_preview(host, request)
    if not apply:
        return preview
    journal_mutations = append_decision(host, preview["decision"])
    lock_mutations = publish_lock(host, preview["lock"])
    return {**preview, "action": "PILOT_APPROVED", "mutations": journal_mutations + lock_mutations}


# --- Capture the four exact Registry/report preimages ---
def state_paths(host: HostLayout) -> dict[str, Path]:
    """Map the frozen transaction filenames to the four formal observed-state views."""
    return {
        "skills-registry.json": host.registry_path,
        "skills-registry.yaml": host.registry_yaml_path,
        "skill-capability-report.md": host.capability_report_path,
        "skill-governance-report.md": host.governance_report_path,
    }


def state_hashes(host: HostLayout) -> dict[str, str]:
    """Return lowercase hashes only after proving every governed state file exists."""
    hashes: dict[str, str] = {}
    for name, path in state_paths(host).items():
        if not path.is_file():
            raise LifecycleBlocked(f"Pilot state preimage is missing: {path}")
        hashes[name] = sha256_file(path).lower()
    return hashes


# --- Require the current lock to authorize this exact activation ---
def require_active_lock(host: HostLayout, manifest: dict[str, Any], decision_id: str) -> dict[str, Any]:
    """Return one exact ACTIVE lock entry or stop before transaction preparation."""
    lock = read_lock(host)
    if lock is None:
        raise LifecycleBlocked("Capability lock is missing.")
    matching = [entry for entry in lock["entries"] if entry.get("name") == manifest["skillName"]]
    if len(matching) != 1:
        raise LifecycleBlocked(f"Expected one lock entry for {manifest['skillName']}, found {len(matching)}.")
    entry = matching[0]
    expected = {
        "artifactID": manifest["artifactID"],
        "desiredLifecycleMode": "SOURCE",
        "desiredActivity": "ACTIVE",
        "targetScopes": ["USER"],
        "targetAgents": ["CODEX"],
        "approvalDecisionID": decision_id,
        "policyVersion": POLICY_VERSION,
    }
    if any(entry.get(field) != value for field, value in expected.items()):
        raise LifecycleBlocked("Capability lock does not authorize this exact activation.")
    return lock


# --- Preview one durable activation transaction ---
def activation_preview(host: HostLayout, request: dict[str, Any]) -> dict[str, Any]:
    """Return the exact activity and state mutation set after all identity checks pass."""
    require_match(request["decisionID"], DECISION_ID, "Decision ID")
    require_match(request["transactionID"], TRANSACTION_ID, "Transaction ID")
    require_match(request["expectedRegistrySHA256"], LOWER_SHA256, "Expected Registry SHA256")
    require_match(request["expectedBaselineSHA256"], LOWER_SHA256, "Expected baseline SHA256")
    manifest, _ = read_artifact_evidence(request["manifestPath"], request["evidencePath"])
    skill_root = validate_repository(manifest, request["repositoryPath"])
    try:
        require_current_approval(read_decisions(host), request["decisionID"], manifest["artifactID"], request["evaluatedAt"])
    except ContractBlocked as error:
        raise LifecycleBlocked(str(error)) from error
    active_lock = require_active_lock(host, manifest, request["decisionID"])
    activity = host.activity_root / manifest["skillName"]
    if activity.exists() or activity.is_symlink():
        raise LifecycleBlocked(f"Pilot activity collision: {activity}")
    registry_sha256 = sha256_file(host.registry_path).lower() if host.registry_path.is_file() else None
    baseline_sha256 = sha256_file(host.baseline_path).lower() if host.baseline_path.is_file() else None
    if registry_sha256 != request["expectedRegistrySHA256"]:
        raise LifecycleBlocked("Canonical Registry hash drifted before pilot activation.")
    if baseline_sha256 != request["expectedBaselineSHA256"]:
        raise LifecycleBlocked("Stable baseline hash drifted before pilot activation.")
    registry = json.loads(host.registry_path.read_text(encoding="utf-8"))
    if any(record.get("name") == manifest["skillName"] for record in registry.get("skills", [])):
        raise LifecycleBlocked("Pilot Skill is already present in the canonical Registry.")
    transaction_path = host.transaction_root / request["transactionID"]
    if transaction_path.exists() or transaction_path.is_symlink():
        raise LifecycleBlocked(f"Pilot transaction already exists: {transaction_path}")
    started_at = parse_timestamp(request["startedAt"])
    if started_at > parse_timestamp(request["evaluatedAt"]):
        raise LifecycleBlocked("Transaction start cannot be later than its approval evaluation time.")
    before_hashes = state_hashes(host)
    transaction = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_TRANSACTION",
        "transactionID": request["transactionID"],
        "action": "ACTIVATE",
        "skillName": manifest["skillName"],
        "approvalDecisionID": request["decisionID"],
        "beforeArtifactID": None,
        "afterArtifactID": manifest["artifactID"],
        "startedAt": request["startedAt"],
        "endedAt": None,
        "executedBy": request["executedBy"],
        "createdPaths": [f"activity/{manifest['skillName']}"],
        "modifiedPaths": list(STATE_FILES.values()),
        "steps": [
            {"name": "persist-preimages", "status": "PENDING", "detail": "Save exact Registry/report bytes."},
            {"name": "activate", "status": "PENDING", "detail": "Create one reviewed symbolic link."},
            {"name": "publish-registry", "status": "PENDING", "detail": "Publish four observed-state views atomically."},
        ],
        "rollbackPlan": {"type": "RESTORE_PREVIOUS_LINK_AND_REGISTRY", "backupRef": f"transactions/{request['transactionID']}/preimages"},
        "rollbackResult": None,
        "finalStatus": "IN_PROGRESS",
    }
    if not isinstance(request["executedBy"], str) or not request["executedBy"] or len(request["executedBy"]) > 256:
        raise LifecycleBlocked("Transaction executor must be one bounded non-empty actor.")
    return {
        "status": "PASS",
        "action": "PILOT_ACTIVATION_PREVIEW",
        "transaction": transaction,
        "activityPath": str(activity),
        "activityTarget": str(skill_root),
        "sourceRepository": str(Path(request["repositoryPath"]).resolve()),
        "canonicalSource": manifest["identity"]["canonicalSource"],
        "resolvedCommit": manifest["identity"]["resolvedCommit"],
        "beforeStateSHA256": before_hashes,
        "baselineSHA256": baseline_sha256,
        "activeLockRevision": active_lock["revision"],
        "mutations": 0,
    }


# --- Publish all four observed-state views from one scan ---
def publish_registry_views(host: HostLayout) -> dict[str, Any]:
    """Write Registry JSON/YAML and both reports from one coherent live inventory."""
    registry = scan_skills([host.activity_root])
    atomic_json(host.registry_path, registry)
    atomic_text(host.registry_yaml_path, json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    atomic_text(host.capability_report_path, capability_report(registry))
    atomic_text(host.governance_report_path, governance_report(registry))
    return registry


# --- Assemble the durable transaction directory before live mutation ---
def publish_transaction_start(host: HostLayout, preview: dict[str, Any]) -> Path:
    """Atomically publish the IN_PROGRESS event and exact preimages in one new transaction directory."""
    host.transaction_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".pilot-", dir=host.transaction_root))
    destination = host.transaction_root / preview["transaction"]["transactionID"]
    try:
        preimages = temporary / "preimages"
        preimages.mkdir()
        for name, source in state_paths(host).items():
            target = preimages / name
            shutil.copy2(source, target)
            if sha256_file(target).lower() != preview["beforeStateSHA256"][name]:
                raise LifecycleBlocked(f"Transaction preimage copy failed verification: {name}")
        atomic_json(temporary / "transaction-start.json", preview["transaction"])
        atomic_json(
            temporary / "before-state.json",
            {
                "schemaVersion": 1,
                "stateSHA256": preview["beforeStateSHA256"],
                "baselineSHA256": preview["baselineSHA256"],
                "activityPath": preview["activityPath"],
                "activityTarget": preview["activityTarget"],
                "activeLockRevision": preview["activeLockRevision"],
            },
        )
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def activate_pilot(host: HostLayout, request: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Preview or apply one temporary SOURCE activation with durable rollback preimages."""
    preview = activation_preview(host, request)
    if not apply:
        return preview
    transaction_path = publish_transaction_start(host, preview)
    activity = Path(preview["activityPath"])
    activity.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(preview["activityTarget"], activity, target_is_directory=True)
    registry = publish_registry_views(host)
    matching = [record for record in registry["skills"] if record.get("name") == preview["transaction"]["skillName"]]
    if len(matching) != 1 or matching[0].get("status") != "PASS":
        raise LifecycleBlocked("Activated pilot did not publish one PASS Registry record.")
    record = matching[0]
    expected_record = {
        "scope": "USER",
        "lifecycleMode": "SOURCE",
        "physicalPath": preview["activityTarget"],
        "sourceRepository": preview["sourceRepository"],
        "remote": preview["canonicalSource"],
        "commit": preview["resolvedCommit"],
        "activePaths": [preview["activityPath"]],
    }
    if any(record.get(field) != value for field, value in expected_record.items()):
        raise LifecycleBlocked("Activated Registry record differs from the approved source identity.")
    prior_registry = json.loads((transaction_path / "preimages/skills-registry.json").read_text(encoding="utf-8"))
    remaining_records = [item for item in registry["skills"] if item.get("name") != preview["transaction"]["skillName"]]
    if remaining_records != prior_registry.get("skills"):
        raise LifecycleBlocked("Pilot activation changed an existing Registry record.")
    if sha256_file(host.baseline_path).lower() != preview["baselineSHA256"]:
        raise LifecycleBlocked("Stable baseline changed during pilot activation.")
    activated = {
        **preview["transaction"],
        "endedAt": request["evaluatedAt"],
        "steps": [
            {"name": "persist-preimages", "status": "PASS", "detail": "Exact preimages are retained."},
            {"name": "activate", "status": "PASS", "detail": f"Created {activity}."},
            {"name": "publish-registry", "status": "PASS", "detail": "Published four observed-state views."},
        ],
        "finalStatus": "COMMITTED",
    }
    atomic_json(transaction_path / "transaction-activated.json", activated)
    atomic_json(transaction_path / "after-state.json", {"schemaVersion": 1, "stateSHA256": state_hashes(host)})
    return {
        **preview,
        "action": "PILOT_ACTIVATED",
        "transactionPath": str(transaction_path),
        "afterStateSHA256": state_hashes(host),
        "registrySummary": registry["summary"],
        "mutations": 8,
    }


# --- Read one transaction-owned event set ---
def transaction_directory(host: HostLayout, transaction_id: str) -> Path:
    """Resolve one exact child of the transaction root without accepting traversal or links."""
    root = host.transaction_root.resolve()
    path = host.transaction_root / transaction_id
    if path.is_symlink() or not path.is_dir() or path.resolve().parent != root:
        raise LifecycleBlocked(f"Pilot transaction directory is missing or unsafe: {path}")
    return path


def read_transaction_event(path: Path, name: str) -> dict[str, Any]:
    """Read one required immutable event document from the transaction directory."""
    event, _ = read_json_object(path / name)
    if event.get("schemaVersion") != 1 or event.get("documentType") != "CAPABILITY_TRANSACTION":
        raise LifecycleBlocked(f"Transaction event identity is unsupported: {name}")
    return event


# --- Preview or execute an explicit bounded probe plan ---
def verification_preview(host: HostLayout, transaction_id: str, probe_plan_path: Path) -> dict[str, Any]:
    """Validate one artifact-bound probe plan and current activated state without executing commands."""
    require_match(transaction_id, TRANSACTION_ID, "Transaction ID")
    directory = transaction_directory(host, transaction_id)
    activated = read_transaction_event(directory, "transaction-activated.json")
    plan, _ = read_json_object(Path(probe_plan_path))
    required = {"schemaVersion", "documentType", "artifactID", "skillName", "timeoutSeconds", "probes"}
    if set(plan) != required or plan.get("schemaVersion") != 1 or plan.get("documentType") != "PILOT_PROBE_PLAN":
        raise LifecycleBlocked("Pilot probe plan identity or fields are unsupported.")
    if plan.get("artifactID") != activated.get("afterArtifactID") or plan.get("skillName") != activated.get("skillName"):
        raise LifecycleBlocked("Pilot probe plan does not match the activated artifact.")
    timeout = plan.get("timeoutSeconds")
    if not isinstance(timeout, int) or not 1 <= timeout <= 300:
        raise LifecycleBlocked("Pilot probe timeout must be within 1..300 seconds.")
    probes = plan.get("probes")
    if not isinstance(probes, list) or not probes or len(probes) > 64:
        raise LifecycleBlocked("Pilot probe plan must contain between 1 and 64 probes.")
    for probe in probes:
        if set(probe) != {"name", "command", "stdin", "expectedExitCode", "stdoutContains"}:
            raise LifecycleBlocked("Pilot probe fields do not match the frozen plan contract.")
        if (
            not isinstance(probe["command"], list)
            or not probe["command"]
            or not all(isinstance(item, str) and len(item) <= 4096 for item in probe["command"])
        ):
            raise LifecycleBlocked("Pilot probe command must be a non-empty string array.")
        if probe["command"][0] != "${PYTHON}" and not Path(probe["command"][0]).is_absolute():
            raise LifecycleBlocked("Pilot probe executable must be ${PYTHON} or one absolute path.")
        if (
            not isinstance(probe["expectedExitCode"], int)
            or not 0 <= probe["expectedExitCode"] <= 255
            or not isinstance(probe["stdoutContains"], list)
        ):
            raise LifecycleBlocked("Pilot probe expectation is invalid.")
        if probe["stdin"] is not None and (not isinstance(probe["stdin"], str) or len(probe["stdin"]) > 65536):
            raise LifecycleBlocked("Pilot probe stdin must be text or null.")
        if (
            not isinstance(probe["name"], str)
            or not probe["name"]
            or len(probe["name"]) > 128
            or not all(isinstance(item, str) and len(item) <= 2048 for item in probe["stdoutContains"])
        ):
            raise LifecycleBlocked("Pilot probe name and output expectations must be strings.")
    before = json.loads((directory / "before-state.json").read_text(encoding="utf-8"))
    after = json.loads((directory / "after-state.json").read_text(encoding="utf-8"))
    if state_hashes(host) != after.get("stateSHA256"):
        raise LifecycleBlocked("Observed state drifted after pilot activation.")
    if sha256_file(host.baseline_path).lower() != before.get("baselineSHA256"):
        raise LifecycleBlocked("Stable baseline changed during the pilot.")
    activity = Path(before["activityPath"])
    if not activity.is_symlink() or str(activity.resolve(strict=True)) != before.get("activityTarget"):
        raise LifecycleBlocked("Pilot activity link differs from the transaction.")
    retained_plan = (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return {
        "status": "PASS",
        "action": "PILOT_VERIFY_PREVIEW",
        "transactionID": transaction_id,
        "planSHA256": hashlib.sha256(retained_plan).hexdigest(),
        "probeCount": len(probes),
        "skillRoot": before["activityTarget"],
        "mutations": 0,
        "plan": plan,
    }


def verify_pilot(host: HostLayout, transaction_id: str, probe_plan_path: Path, apply: bool) -> dict[str, Any]:
    """Preview or run one no-shell probe plan and retain bounded output inside its transaction."""
    preview = verification_preview(host, transaction_id, probe_plan_path)
    if not apply:
        return preview
    directory = transaction_directory(host, transaction_id)
    retained_paths = [directory / name for name in ("probe-plan.json", "probe-evidence.json", "transaction-verified.json")]
    if any(path.exists() or path.is_symlink() for path in retained_paths):
        if not all(path.is_file() and not path.is_symlink() for path in retained_paths):
            raise LifecycleBlocked("Pilot probe evidence is incomplete; preserve it and inspect before retry.")
        retained_plan, retained_plan_bytes = read_json_object(retained_paths[0])
        retained_evidence, _ = read_json_object(retained_paths[1])
        retained_event = read_transaction_event(directory, "transaction-verified.json")
        retained_step = retained_event.get("steps", [])[-1] if retained_event.get("steps") else {}
        if (
            retained_plan != preview["plan"]
            or hashlib.sha256(retained_plan_bytes).hexdigest() != preview["planSHA256"]
            or retained_evidence.get("transactionID") != transaction_id
            or retained_evidence.get("artifactID") != preview["plan"]["artifactID"]
            or retained_evidence.get("planSHA256") != preview["planSHA256"]
            or retained_evidence.get("status") not in {"PASS", "BLOCKED"}
            or not isinstance(retained_evidence.get("results"), list)
            or retained_event.get("afterArtifactID") != preview["plan"]["artifactID"]
            or retained_step.get("status") != retained_evidence.get("status")
            or retained_event.get("finalStatus") != ("COMMITTED" if retained_evidence.get("status") == "PASS" else "FAILED")
        ):
            raise LifecycleBlocked("Pilot verification retry differs from retained evidence.")
        return {
            **preview,
            "status": retained_evidence.get("status"),
            "action": "PILOT_VERIFY_ALREADY_COMPLETE",
            "results": retained_evidence.get("results"),
            "mutations": 0,
        }
    retained_plan = (json.dumps(preview["plan"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_bytes(directory / "probe-plan.json", retained_plan)
    results: list[dict[str, Any]] = []
    all_passed = True
    for probe in preview["plan"]["probes"]:
        command = [
            item.replace("${SKILL_ROOT}", preview["skillRoot"]).replace("${PYTHON}", sys.executable)
            for item in probe["command"]
        ]
        try:
            completed = subprocess.run(
                command,
                input=probe["stdin"],
                text=True,
                capture_output=True,
                timeout=preview["plan"]["timeoutSeconds"],
                check=False,
            )  # No shell or environment interpolation can reinterpret the reviewed argument array.
            exit_code = completed.returncode
            combined = (completed.stdout + completed.stderr)[:8000]
        except subprocess.TimeoutExpired as error:
            exit_code = -1
            partial_stdout = error.stdout if isinstance(error.stdout, str) else ""
            partial_stderr = error.stderr if isinstance(error.stderr, str) else ""
            combined = (partial_stdout + partial_stderr + "\nProbe timed out.")[:8000]
        except OSError as error:
            exit_code = -1
            combined = f"Probe executable failed: {error}"[:8000]
        missing = [text for text in probe["stdoutContains"] if text not in combined]
        passed = exit_code == probe["expectedExitCode"] and not missing
        all_passed = all_passed and passed
        results.append(
            {
                "name": probe["name"],
                "status": "PASS" if passed else "BLOCKED",
                "exitCode": exit_code,
                "expectedExitCode": probe["expectedExitCode"],
                "missingOutput": missing,
                "output": combined,
            }
        )
    probe_evidence = {
        "schemaVersion": 1,
        "documentType": "PILOT_PROBE_EVIDENCE",
        "transactionID": transaction_id,
        "artifactID": preview["plan"]["artifactID"],
        "planSHA256": preview["planSHA256"],
        "status": "PASS" if all_passed else "BLOCKED",
        "results": results,
    }
    atomic_json(directory / "probe-evidence.json", probe_evidence)
    activated = read_transaction_event(directory, "transaction-activated.json")
    verified = {
        **activated,
        "steps": [*activated["steps"], {"name": "verify", "status": "PASS" if all_passed else "BLOCKED", "detail": "Bounded probe evidence retained."}],
        "finalStatus": "COMMITTED" if all_passed else "FAILED",
    }
    atomic_json(directory / "transaction-verified.json", verified)
    return {**preview, "status": probe_evidence["status"], "action": "PILOT_VERIFIED", "results": results, "mutations": 3}


# --- Build a superseding decision plus INACTIVE lock revision ---
def rollback_preview(host: HostLayout, request: dict[str, Any]) -> dict[str, Any]:
    """Inspect exact transaction ownership and preimages before any rollback mutation."""
    require_match(request["transactionID"], TRANSACTION_ID, "Transaction ID")
    require_match(request["decisionID"], DECISION_ID, "Revocation decision ID")
    parse_timestamp(request["decidedAt"])
    if not isinstance(request["decidedBy"], str) or not request["decidedBy"] or len(request["decidedBy"]) > 256:
        raise LifecycleBlocked("Rollback actor must be one bounded non-empty string.")
    if not isinstance(request["reason"], str) or not request["reason"] or len(request["reason"]) > 4096:
        raise LifecycleBlocked("Rollback reason must be one bounded non-empty string.")
    directory = transaction_directory(host, request["transactionID"])
    rollback_event_path = directory / "transaction-rollback.json"
    if rollback_event_path.is_file():
        rollback = read_transaction_event(directory, "transaction-rollback.json")
        started = read_transaction_event(directory, "transaction-start.json")
        if rollback.get("approvalDecisionID") != request["decisionID"]:
            raise LifecycleBlocked("Completed rollback belongs to another revocation decision.")
        before = json.loads((directory / "before-state.json").read_text(encoding="utf-8"))
        activity = Path(before["activityPath"])
        restored = state_hashes(host) == before["stateSHA256"]
        baseline = sha256_file(host.baseline_path).lower() == before["baselineSHA256"]
        if activity.exists() or activity.is_symlink() or not restored or not baseline:
            raise LifecycleBlocked("Completed rollback evidence no longer matches formal state.")
        lock = read_lock(host)
        lock_entries = [] if lock is None else [entry for entry in lock["entries"] if entry.get("name") == rollback["skillName"]]
        revocations = [
            decision
            for decision in read_decisions(host)
            if decision.get("decisionID") == request["decisionID"]
            and decision.get("decision") == "REVOKED"
            and decision.get("supersedesDecisionID") == started.get("approvalDecisionID")
        ]
        expected_revocation = {
            "schemaVersion": 1,
            "documentType": "CAPABILITY_APPROVAL_DECISION",
            "decisionID": request["decisionID"],
            "artifactID": started["afterArtifactID"],
            "skillName": started["skillName"],
            "requestedBy": request["decidedBy"],
            "requestedAt": request["decidedAt"],
            "decision": "REVOKED",
            "decidedBy": request["decidedBy"],
            "decidedAt": request["decidedAt"],
            "policyVersion": POLICY_VERSION,
            "evidenceRefs": [],
            "reason": request["reason"],
            "expiresAt": None,
            "supersedesDecisionID": started["approvalDecisionID"],
        }
        active_revision_path = host.capability_lock_history_root / f"capability-lock-r{before['activeLockRevision']:06d}.json"
        inactive_revision_valid = bool(
            lock
            and (host.capability_lock_history_root / f"capability-lock-r{lock['revision']:06d}.json").is_file()
        )
        if (
            len(lock_entries) != 1
            or lock_entries[0].get("desiredActivity") != "INACTIVE"
            or lock_entries[0].get("approvalDecisionID") != request["decisionID"]
            or len(revocations) != 1
            or revocations[0] != expected_revocation
            or not active_revision_path.is_file()
            or not inactive_revision_valid
        ):
            raise LifecycleBlocked("Completed rollback audit state is incomplete.")
        return {"status": "PASS", "action": "PILOT_ROLLBACK_ALREADY_COMPLETE", "transaction": rollback, "mutations": 0}

    started = read_transaction_event(directory, "transaction-start.json")
    before = json.loads((directory / "before-state.json").read_text(encoding="utf-8"))
    current_lock = read_lock(host)
    if current_lock is None:
        raise LifecycleBlocked("Capability lock is missing before rollback.")
    matching = [entry for entry in current_lock["entries"] if entry.get("name") == started["skillName"]]
    if len(matching) != 1 or matching[0].get("desiredActivity") not in {"ACTIVE", "INACTIVE"}:
        raise LifecycleBlocked("Capability lock cannot be reconciled for the pilot transaction.")
    if matching[0].get("desiredActivity") == "INACTIVE" and matching[0].get("approvalDecisionID") != request["decisionID"]:
        raise LifecycleBlocked("Existing INACTIVE lock belongs to another revocation decision.")
    activity = Path(before["activityPath"])
    if activity.is_symlink() and str(activity.resolve(strict=True)) != before["activityTarget"]:
        raise LifecycleBlocked("Rollback activity link differs from the durable transaction.")
    if activity.exists() and not activity.is_symlink():
        raise LifecycleBlocked("Rollback activity path is an undeclared physical collision.")
    if sha256_file(host.baseline_path).lower() != before["baselineSHA256"]:
        raise LifecycleBlocked("Stable baseline changed before rollback.")
    for name, expected in before["stateSHA256"].items():
        preimage = directory / "preimages" / name
        if not preimage.is_file() or sha256_file(preimage).lower() != expected:
            raise LifecycleBlocked(f"Rollback preimage is missing or invalid: {name}")
    decisions = read_decisions(host)
    approved_matches = [
        decision
        for decision in decisions
        if decision.get("decisionID") == started["approvalDecisionID"]
        and decision.get("decision") == "APPROVED"
        and decision.get("artifactID") == started["afterArtifactID"]
    ]  # Expiry may block a new activation, but it must never block rollback of an existing transaction.
    if len(approved_matches) != 1:
        raise LifecycleBlocked("Rollback cannot resolve the transaction's original artifact approval.")
    approved = approved_matches[0]
    revocation = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_APPROVAL_DECISION",
        "decisionID": request["decisionID"],
        "artifactID": started["afterArtifactID"],
        "skillName": started["skillName"],
        "requestedBy": request["decidedBy"],
        "requestedAt": request["decidedAt"],
        "decision": "REVOKED",
        "decidedBy": request["decidedBy"],
        "decidedAt": request["decidedAt"],
        "policyVersion": POLICY_VERSION,
        "evidenceRefs": [],
        "reason": request["reason"],
        "expiresAt": None,
        "supersedesDecisionID": approved["decisionID"],
    }
    entries = [entry for entry in current_lock["entries"] if entry.get("name") != started["skillName"]]
    entries.append({**matching[0], "desiredActivity": "INACTIVE", "approvalDecisionID": revocation["decisionID"]})
    ordered_entries = sorted(entries, key=lambda item: item["name"])
    inactive_lock = current_lock if current_lock.get("entries") == ordered_entries else {
        **current_lock,
        "revision": current_lock["revision"] + 1,
        "updatedAt": request["decidedAt"],
        "entries": ordered_entries,
    }
    rollback = {
        **started,
        "action": "ROLLBACK",
        "approvalDecisionID": revocation["decisionID"],
        "beforeArtifactID": started["afterArtifactID"],
        "afterArtifactID": None,
        "endedAt": None,  # An IN_PROGRESS event has no completion time under the frozen Schema.
        "executedBy": request["decidedBy"],
        "steps": [
            {"name": "remove-activity", "status": "PENDING", "detail": "Remove only the declared pilot link."},
            {"name": "restore-state", "status": "PENDING", "detail": "Restore four exact preimages."},
            {"name": "revoke-and-lock", "status": "PENDING", "detail": "Append revocation and publish INACTIVE lock."},
        ],
        "rollbackResult": None,
        "finalStatus": "IN_PROGRESS",
    }
    return {
        "status": "PASS",
        "action": "PILOT_ROLLBACK_PREVIEW",
        "transaction": rollback,
        "revocation": revocation,
        "lock": inactive_lock,
        "activityPath": str(activity),
        "beforeStateSHA256": before["stateSHA256"],
        "mutations": 0,
    }


def rollback_pilot(host: HostLayout, request: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Preview or restore exact formal bytes, revoke approval, and publish an INACTIVE lock."""
    preview = rollback_preview(host, request)
    if not apply or preview["action"] == "PILOT_ROLLBACK_ALREADY_COMPLETE":
        return preview
    directory = transaction_directory(host, request["transactionID"])
    atomic_json(directory / "transaction-rollback-start.json", preview["transaction"])
    activity = Path(preview["activityPath"])
    if activity.is_symlink():
        activity.unlink()  # Preview proved this is the exact transaction-owned symbolic link.
    for name, destination in state_paths(host).items():
        atomic_bytes(destination, (directory / "preimages" / name).read_bytes())
    if state_hashes(host) != preview["beforeStateSHA256"]:
        raise LifecycleBlocked("Rollback could not restore the exact Registry/report preimages.")
    journal_mutations = append_decision(host, preview["revocation"])
    lock_mutations = publish_lock(host, preview["lock"])
    rollback = {
        **preview["transaction"],
        "endedAt": request["decidedAt"],  # Only the terminal event records when rollback completed.
        "steps": [
            {"name": "remove-activity", "status": "PASS", "detail": "Removed only the declared pilot link."},
            {"name": "restore-state", "status": "PASS", "detail": "Restored four exact preimages."},
            {"name": "revoke-and-lock", "status": "PASS", "detail": "Retained revocation and INACTIVE lock."},
        ],
        "rollbackResult": {"status": "PASS", "detail": "Activity removed and exact formal state restored."},
        "finalStatus": "ROLLED_BACK",
    }
    atomic_json(directory / "transaction-rollback.json", rollback)
    return {
        **preview,
        "action": "PILOT_ROLLED_BACK",
        "transaction": rollback,
        "restoredStateSHA256": state_hashes(host),
        "mutations": 7 + journal_mutations + lock_mutations,
    }
