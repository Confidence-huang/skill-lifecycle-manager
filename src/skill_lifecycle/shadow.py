"""
Generate V5 Phase B shadow artifacts without changing live capability state.

Callers provide one frozen Registry v1 file and one explicit source set. The module reads Git commit
objects, compares selected sources with observed Registry records, and returns documents destined
for a new shadow directory. It never writes the Registry, decisions, locks, links, baselines, or
source repositories.
"""

from __future__ import annotations  # Keep Python 3.12 annotations visible to readers and tooling.

import hashlib  # Bind shadow inputs and emitted files to exact bytes.
import json  # Parse explicit host inputs and render deterministic shadow documents.
import os  # Publish a completely prepared directory with one atomic rename.
import re  # Read the Skill name from committed frontmatter without executing Skill content.
import shutil  # Remove only a transaction-owned temporary output after a failed publication.
import subprocess  # Query immutable Git objects through argument-array commands.
import tempfile  # Stage a complete shadow tree beside its final destination.
import uuid  # Derive stable evidence identifiers from immutable artifact and host facts.
from dataclasses import dataclass  # Keep the generated document set separate from CLI feedback.
from datetime import datetime  # Require one timezone-aware evidence timestamp from the source set.
from pathlib import Path, PurePosixPath  # Separate host paths from portable artifact paths.
from typing import Any  # Describe JSON documents at the module boundary.

from skill_lifecycle.contracts import (  # Reuse the frozen Phase A identity algorithm.
    build_artifact_identity,
    compute_artifact_id,
    compute_tree_sha256,
    normalize_relative_path,
)
from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Share the existing hard stop gate.


FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")  # Branch names never satisfy an immutable source pin.
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")  # Frozen input hashes use one canonical representation.
HOST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # Match the shared Schema's host identifier.
SKILL_NAME = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)  # Frontmatter owns the public name.
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1\n"  # Pointer bytes are not full content.
OBSERVED_FIELDS = (
    "status",
    "scope",
    "lifecycleMode",
    "physicalPath",
    "activePaths",
    "sourceRepository",
    "remote",
    "branch",
    "commit",
    "entryCount",
    "issues",
    "isTopLevel",
    "skillSHA256",
    "sourceDirty",
    "lifecycleSHA256",
    "updates",
)  # Preserve the complete 4.1 identity, status, package provenance, and freshness view without rewriting it.


@dataclass(frozen=True)
class ShadowBundle:
    """Hold generated JSON documents and their human-facing summary before publication."""

    documents: dict[str, dict[str, Any]]
    summary: dict[str, Any]


# --- Run one read-only Git query ---
def git_bytes(repository: Path, *arguments: str) -> bytes:
    """Return stdout from one Git query and block on missing objects or repository failures."""
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=False,
    )  # Argument arrays keep host paths and Git revisions out of shell syntax.
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()
        raise LifecycleBlocked(f"Git query failed for {repository}: {diagnostic}")
    return completed.stdout


# --- Read one JSON object without accepting duplicate keys ---
def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one object while refusing a later key from silently replacing an earlier value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LifecycleBlocked(f"JSON object contains a duplicate key: {key}")
        result[key] = value
    return result


def read_json_object(path: Path) -> tuple[dict[str, Any], bytes]:
    """Return one UTF-8 JSON object and its exact source bytes for provenance hashing."""
    source_bytes = path.read_bytes()
    try:
        payload = json.loads(source_bytes.decode("utf-8"), object_pairs_hook=unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LifecycleBlocked(f"JSON input is invalid: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise LifecycleBlocked(f"JSON input must be an object: {path}")
    return payload, source_bytes


# --- Validate the frozen Registry input ---
def read_registry_v1(path: Path) -> tuple[dict[str, Any], str]:
    """Read one Registry v1 snapshot without rescanning or changing observed host state."""
    registry, source_bytes = read_json_object(path)
    if registry.get("schemaVersion") != 1 or not isinstance(registry.get("skills"), list):
        raise LifecycleBlocked("Shadow generation requires one Registry v1 object with a skills array.")
    if not isinstance(registry.get("inventoryFingerprint"), str):
        raise LifecycleBlocked("Registry v1 is missing its inventory fingerprint.")
    return registry, hashlib.sha256(source_bytes).hexdigest()


# --- Validate one explicit Phase B source set ---
def read_source_set(path: Path) -> dict[str, Any]:
    """Validate host, time, policy, targets, and immutable source pins before any Git read."""
    source_set, _ = read_json_object(path)
    required = {
        "schemaVersion",
        "documentType",
        "hostID",
        "generatedAt",
        "expectedRegistrySHA256",
        "targetAgents",
        "policyVersion",
        "sources",
    }
    if set(source_set) != required:
        raise LifecycleBlocked("Shadow source-set fields do not match the Phase B contract.")
    if source_set["schemaVersion"] != 1 or source_set["documentType"] != "AI_CAPABILITY_SHADOW_SOURCE_SET":
        raise LifecycleBlocked("Shadow source set has an unsupported identity or version.")
    host_id = source_set["hostID"]
    if not isinstance(host_id, str) or len(host_id) > 128 or not HOST_ID.fullmatch(host_id):
        raise LifecycleBlocked("Shadow source set has an invalid host identifier.")
    try:
        generated_at = datetime.fromisoformat(source_set["generatedAt"])
    except (TypeError, ValueError) as error:
        raise LifecycleBlocked("Shadow source set has an invalid generatedAt timestamp.") from error
    if generated_at.tzinfo is None:
        raise LifecycleBlocked("Shadow source set generatedAt must include a timezone offset.")
    registry_sha256 = source_set["expectedRegistrySHA256"]
    if not isinstance(registry_sha256, str) or not LOWER_SHA256.fullmatch(registry_sha256):
        raise LifecycleBlocked("Shadow source set must pin one lowercase Registry SHA256.")
    if not isinstance(source_set["sources"], list) or not source_set["sources"]:
        raise LifecycleBlocked("Shadow source set must contain at least one explicit source.")
    target_agents = source_set["targetAgents"]
    if (
        not isinstance(target_agents, list)
        or not target_agents
        or len(target_agents) != len(set(target_agents))
        or any(not isinstance(agent, str) or not agent or len(agent) > 64 for agent in target_agents)
    ):
        raise LifecycleBlocked("Shadow source set must name at least one target Agent.")
    policy_version = source_set["policyVersion"]
    if not isinstance(policy_version, str) or not policy_version or len(policy_version) > 128:
        raise LifecycleBlocked("Shadow source set must name one policy version.")
    return source_set


# --- Parse one committed Skill name ---
def committed_skill_name(repository: Path, skill_path: str) -> str:
    """Read the public name from the pinned commit rather than the mutable working-tree file."""
    skill_file = "SKILL.md" if skill_path == "." else f"{skill_path}/SKILL.md"
    try:
        text = git_bytes(repository, "show", f"HEAD:{skill_file}").decode("utf-8")
    except UnicodeDecodeError as error:
        raise LifecycleBlocked(f"Committed Skill entry is not UTF-8: {skill_file}") from error
    if not text.startswith("---"):
        raise LifecycleBlocked(f"Committed Skill entry has no frontmatter: {skill_file}")
    closing = text.find("\n---", 3)
    match = SKILL_NAME.search(text[:closing] if closing >= 0 else "")
    if not match or not match.group(1).strip():
        raise LifecycleBlocked(f"Committed Skill entry has no name: {skill_file}")
    return match.group(1).strip().strip('"\'')


# --- Convert a pinned Git tree into Phase A logical entries ---
def committed_tree_entries(repository: Path) -> list[dict[str, Any]]:
    """Hash the full tracked repository tree while refusing incomplete supply-chain objects."""
    entries: list[dict[str, Any]] = []
    lfs_paths: list[str] = []
    submodule_paths: list[str] = []
    for raw_record in git_bytes(repository, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split(b"\0"):
        if not raw_record:
            continue
        header, raw_path = raw_record.split(b"\t", 1)
        mode, object_type, object_id = header.decode("ascii").split(" ")
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as error:
            raise LifecycleBlocked("Git tree contains a path that is not valid UTF-8.") from error
        normalized_path = normalize_relative_path(path)
        if mode == "160000" or object_type == "commit":
            submodule_paths.append(normalized_path)  # A gitlink does not contain the child tree bytes.
            continue
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            raise LifecycleBlocked(f"Unsupported Git tree object for {normalized_path}: {mode} {object_type}")
        content = git_bytes(repository, "cat-file", "blob", object_id)
        if content.startswith(LFS_HEADER):
            lfs_paths.append(normalized_path)  # LFS pointer text cannot stand in for the declared object.
            continue
        if mode == "120000":
            try:
                link_target = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise LifecycleBlocked(f"Symbolic-link text is not UTF-8: {normalized_path}") from error
            entries.append({"path": normalized_path, "type": "SYMLINK", "linkTarget": link_target})
            continue
        entries.append(
            {
                "path": normalized_path,
                "type": "FILE",
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )  # Executable mode is source metadata; exact file bytes remain the Phase A content identity.
    if submodule_paths:
        raise LifecycleBlocked(f"Git submodules require separate complete-tree evidence: {submodule_paths}")
    if lfs_paths:
        raise LifecycleBlocked(f"Git LFS pointers are not complete artifact bytes: {lfs_paths}")
    if not entries:
        raise LifecycleBlocked(f"Pinned Git repository contains no artifact files: {repository}")
    return entries


# --- Validate one source declaration ---
def validate_source(source: dict[str, Any]) -> tuple[Path, str, str]:
    """Return the physical repository, normalized Skill path, and exact resolved commit."""
    required = {
        "role",
        "repositoryPath",
        "skillPath",
        "expectedName",
        "canonicalSource",
        "expectedCommit",
        "suggestedLifecycleMode",
        "suggestedActivity",
        "targetScopes",
    }
    if not isinstance(source, dict) or set(source) != required:
        raise LifecycleBlocked("One shadow source declaration does not match the Phase B contract.")
    role = source["role"]
    expected_activity = "ACTIVE" if role == "ACTIVE_OBSERVED" else "INACTIVE"
    if role not in {"ACTIVE_OBSERVED", "REVIEW_ONLY"} or source["suggestedActivity"] != expected_activity:
        raise LifecycleBlocked(f"Shadow source role and suggested activity disagree: {source.get('expectedName')}")
    repository_text = source["repositoryPath"]
    if not isinstance(repository_text, str) or not repository_text or repository_text != repository_text.strip():
        raise LifecycleBlocked(f"Shadow source has an invalid repository path: {source.get('expectedName')}")
    repository = Path(repository_text).expanduser().resolve(strict=True)
    if not (repository / ".git").exists():
        raise LifecycleBlocked(f"Shadow source is not a complete Git repository: {repository}")
    skill_path = normalize_relative_path(source["skillPath"], allow_root=True)
    expected_commit = source["expectedCommit"]
    if not isinstance(expected_commit, str) or not FULL_COMMIT.fullmatch(expected_commit):
        raise LifecycleBlocked(f"Shadow source has no full commit pin: {source.get('expectedName')}")
    expected_name = source["expectedName"]
    if (
        not isinstance(expected_name, str)
        or not expected_name
        or len(expected_name) > 128
        or expected_name != expected_name.strip()
        or "/" in expected_name
        or "\\" in expected_name
    ):
        raise LifecycleBlocked("Shadow source has an invalid expected Skill name.")
    canonical_source = source["canonicalSource"]
    if not isinstance(canonical_source, str) or not canonical_source or canonical_source != canonical_source.strip():
        raise LifecycleBlocked(f"Shadow source has an invalid canonical source: {expected_name}")
    if source["suggestedLifecycleMode"] not in {"PACKAGE", "SOURCE", "HYBRID"}:
        raise LifecycleBlocked(f"Shadow source has an invalid lifecycle suggestion: {expected_name}")
    scopes = source["targetScopes"]
    if (
        not isinstance(scopes, list)
        or not scopes
        or len(scopes) != len(set(scopes))
        or any(scope not in {"SYSTEM", "USER", "PROJECT"} for scope in scopes)
    ):
        raise LifecycleBlocked(f"Shadow source has invalid target scopes: {expected_name}")
    return repository, skill_path, expected_commit


# --- Preserve the current host Registry facts needed for loss detection ---
def observed_state(record: dict[str, Any]) -> dict[str, Any]:
    """Project one Registry record without dropping identity, activation, provenance, or freshness evidence."""
    missing = [field for field in OBSERVED_FIELDS if field not in record]
    if missing:
        raise LifecycleBlocked(f"Registry record loses required observed fields: {record.get('name')}: {missing}")
    return {field: record[field] for field in OBSERVED_FIELDS}


# --- Compare one pinned source with Registry v1 ---
def build_source_record(
    source: dict[str, Any],
    registry_records: list[dict[str, Any]],
    host_id: str,
    registry_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return an artifact manifest, shadow record, and non-authoritative lock candidate."""
    repository, skill_path, expected_commit = validate_source(source)
    status_bytes = git_bytes(repository, "status", "--porcelain=v1", "-z")
    if status_bytes:
        raise LifecycleBlocked(f"Shadow source worktree is dirty: {repository}")
    resolved_commit = git_bytes(repository, "rev-parse", "HEAD").decode("ascii").strip()
    if resolved_commit != expected_commit:
        raise LifecycleBlocked(f"Shadow source commit drifted: {source['expectedName']}: {resolved_commit}")
    remote = git_bytes(repository, "remote", "get-url", "origin").decode("utf-8").strip()
    if remote != source["canonicalSource"]:
        raise LifecycleBlocked(f"Shadow source remote differs from canonical source: {source['expectedName']}")
    actual_name = committed_skill_name(repository, skill_path)
    if actual_name != source["expectedName"]:
        raise LifecycleBlocked(f"Committed Skill name mismatch: expected {source['expectedName']}, found {actual_name}")

    tree_entries = committed_tree_entries(repository)  # Full tracked tree conservatively includes shared resources.
    tree_sha256 = compute_tree_sha256(tree_entries)
    identity = build_artifact_identity("GIT", remote, resolved_commit, skill_path, tree_sha256)
    artifact_id = compute_artifact_id(identity)
    manifest = {
        "schemaVersion": 1,
        "documentType": "CAPABILITY_ARTIFACT_MANIFEST",
        "artifactID": artifact_id,
        "skillName": actual_name,
        "identity": identity,
        "treeEntries": tree_entries,
    }

    matching = [record for record in registry_records if record.get("name") == actual_name]
    role = source["role"]
    if role == "ACTIVE_OBSERVED" and len(matching) != 1:
        raise LifecycleBlocked(f"Expected one active Registry record named {actual_name}, found {len(matching)}.")
    if role == "REVIEW_ONLY" and matching:
        raise LifecycleBlocked(f"Reviewed-only source is already observed by Registry: {actual_name}")
    observed = observed_state(matching[0]) if matching else None
    physical_match = None
    commit_match = None
    lifecycle_match = None
    remote_match = None
    source_match = None
    scope_match = None
    if observed:
        if not isinstance(observed["physicalPath"], str) or not isinstance(observed["sourceRepository"], str):
            raise LifecycleBlocked(f"Observed Registry paths are not usable strings: {actual_name}")
        physical_skill = repository if skill_path == "." else repository / PurePosixPath(skill_path)
        physical_match = Path(observed["physicalPath"]).resolve(strict=True) == physical_skill.resolve(strict=True)
        commit_match = observed["commit"] == resolved_commit
        lifecycle_match = observed["lifecycleMode"] == source["suggestedLifecycleMode"]
        source_match = Path(observed["sourceRepository"]).resolve(strict=True) == repository
        remote_match = observed["remote"] == remote
        scope_match = observed["scope"] in source["targetScopes"]
        if not all((physical_match, commit_match, lifecycle_match, remote_match, source_match, scope_match)):
            raise LifecycleBlocked(f"Observed Registry identity differs from pinned source: {actual_name}")
        if observed["status"] != "PASS" or observed["sourceDirty"] is not False:
            raise LifecycleBlocked(f"Observed Registry source is not a clean PASS record: {actual_name}")

    evidence_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"{artifact_id}|{host_id}|{registry_sha256}")
    evidence_id = f"evidence-{evidence_uuid}"
    convergence = "UNMANAGED" if observed else "NOT_EVALUATED"
    diagnostics = [
        "Observed Registry facts match the pinned artifact; no lock or approval was created."
        if observed
        else "Reviewed-only source remains absent from Registry; no activation or approval was created."
    ]
    record = {
        "role": role,
        "name": actual_name,
        "artifactID": artifact_id,
        "evidenceID": evidence_id,
        "canonicalSource": remote,
        "repositoryPath": str(repository),
        "skillPath": skill_path,
        "resolvedCommit": resolved_commit,
        "lifecycleMode": source["suggestedLifecycleMode"],
        "suggestedActivity": source["suggestedActivity"],
        "observedPresence": "PRESENT" if observed else "ABSENT",
        "convergenceStatus": convergence,
        "physicalPathMatches": physical_match,
        "registryCommitMatches": commit_match,
        "registryLifecycleMatches": lifecycle_match,
        "registryRemoteMatches": remote_match,
        "registrySourceMatches": source_match,
        "registryScopeMatches": scope_match,
        "sourceClean": True,
        "skillNameMatches": True,
        "lfsPointerCount": 0,
        "submoduleCount": 0,
        "status": "PASS",
        "diagnostics": diagnostics,
        "observedState": observed,
    }
    candidate = {
        "name": actual_name,
        "artifactID": artifact_id,
        "suggestedLifecycleMode": source["suggestedLifecycleMode"],
        "suggestedActivity": source["suggestedActivity"],
        "targetScopes": source["targetScopes"],
        "targetAgents": [],  # The source-set target Agents are attached after this source comparison.
        "approvalDecisionID": None,
        "eligibility": "BLOCKED_MISSING_APPROVAL",
        "observedPresence": record["observedPresence"],
        "convergenceStatus": convergence,
        "reasons": ["Phase B cannot create or infer an artifact-bound approval decision."],
    }
    return manifest, record, candidate


# --- Serialize one shadow document exactly ---
def document_bytes(payload: dict[str, Any]) -> bytes:
    """Render stable UTF-8 bytes used by preview hashes, evidence, and publication."""
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


# --- Build the complete Phase B shadow document set ---
def build_shadow_bundle(registry_path: Path, source_set_path: Path) -> ShadowBundle:
    """Generate all documents in memory and stop before any output directory exists."""
    registry, registry_sha256 = read_registry_v1(registry_path)
    source_set = read_source_set(source_set_path)
    if source_set["expectedRegistrySHA256"] != registry_sha256:
        raise LifecycleBlocked("Frozen Registry bytes do not match the source-set SHA256 pin.")
    names = [source.get("expectedName") for source in source_set["sources"]]
    if len(names) != len(set(names)):
        raise LifecycleBlocked("Shadow source set contains a duplicate expected Skill name.")

    manifests: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for source in source_set["sources"]:
        manifest, record, candidate = build_source_record(
            source,
            registry["skills"],
            source_set["hostID"],
            registry_sha256,
        )
        candidate["targetAgents"] = source_set["targetAgents"]
        manifests.append(manifest)
        records.append(record)
        candidates.append(candidate)

    active_count = sum(record["role"] == "ACTIVE_OBSERVED" for record in records)
    reviewed_count = sum(record["role"] == "REVIEW_ONLY" for record in records)
    summary = {
        "artifacts": len(manifests),
        "evidence": len(manifests),
        "activeObserved": active_count,
        "reviewedOnly": reviewed_count,
        "blocked": 0,
        "unmanaged": active_count,
    }
    shadow_report = {
        "schemaVersion": 1,
        "documentType": "AI_CAPABILITY_SHADOW_REPORT",
        "hostID": source_set["hostID"],
        "generatedAt": source_set["generatedAt"],
        "registrySHA256": registry_sha256,
        "registrySchemaVersion": registry["schemaVersion"],
        "registryInventoryFingerprint": registry["inventoryFingerprint"],
        "inputSourceCount": len(records),
        "summary": summary,
        "records": sorted(records, key=lambda item: item["name"]),
        "mutations": 0,
    }
    report_sha256 = hashlib.sha256(document_bytes(shadow_report)).hexdigest()
    lock_candidates = {
        "schemaVersion": 1,
        "documentType": "AI_CAPABILITY_LOCK_CANDIDATES",
        "hostID": source_set["hostID"],
        "generatedAt": source_set["generatedAt"],
        "policyVersion": source_set["policyVersion"],
        "registrySHA256": registry_sha256,
        "entries": sorted(candidates, key=lambda item: item["name"]),
    }

    documents: dict[str, dict[str, Any]] = {
        "shadow-report.json": shadow_report,
        "lock-candidates.json": lock_candidates,
    }
    for manifest, record in zip(manifests, records, strict=True):
        artifact_suffix = manifest["artifactID"].split(":", 1)[1]
        documents[f"artifacts/{artifact_suffix}/manifest.json"] = manifest
        documents[f"evidence/{artifact_suffix}/{record['evidenceID']}.json"] = {
            "schemaVersion": 1,
            "documentType": "CAPABILITY_EVIDENCE",
            "evidenceID": record["evidenceID"],
            "artifactID": record["artifactID"],
            "skillName": record["name"],
            "kind": "PROVENANCE",
            "tool": "skill-lifecycle-manager shadow",
            "toolVersion": "5-phase-b-shadow-1",
            "policyVersion": source_set["policyVersion"],
            "generatedAt": source_set["generatedAt"],
            "hostID": source_set["hostID"],
            "probeStatus": "PASS",
            "findingCounts": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "informational": 1,
                "unknown": 0,
            },
            "reportSHA256": report_sha256,
            "reportPath": "shadow-report.json",
            "diagnostics": record["diagnostics"],
        }
    return ShadowBundle(documents=documents, summary=summary)


# --- Keep a requested shadow output away from live roots ---
def validate_shadow_destination(host: HostLayout, output_root: Path) -> Path:
    """Allow one new child below data-root/shadows and reject every existing destination."""
    shadow_root = (host.data_root / "shadows").expanduser().resolve()
    destination = output_root.expanduser().resolve()
    if destination == shadow_root or not destination.is_relative_to(shadow_root):
        raise LifecycleBlocked(f"Shadow output must be a named child of {shadow_root}: {destination}")
    if destination.exists():
        raise LifecycleBlocked(f"Shadow output destination already exists: {destination}")
    return destination


# --- Preview one Phase B shadow run ---
def preview_shadow(
    host: HostLayout,
    registry_path: Path,
    source_set_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Return exact planned file hashes while proving that no output path was created."""
    destination = validate_shadow_destination(host, output_root)
    bundle = build_shadow_bundle(registry_path, source_set_path)
    planned = [
        {"path": path, "sha256": hashlib.sha256(document_bytes(payload)).hexdigest()}
        for path, payload in sorted(bundle.documents.items())
    ]
    return {
        "status": "PASS",
        "action": "SHADOW_PREVIEW",
        "shadowRoot": str(destination),
        "summary": bundle.summary,
        "plannedFiles": planned,
        "mutations": 0,
    }


# --- Publish one isolated Phase B shadow run ---
def write_shadow(
    host: HostLayout,
    registry_path: Path,
    source_set_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Atomically publish generated files only beneath the dedicated non-live shadow root."""
    destination = validate_shadow_destination(host, output_root)
    bundle = build_shadow_bundle(registry_path, source_set_path)
    destination.parent.mkdir(parents=True, exist_ok=True)  # Apply may create only the shadow container.
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for relative_path, payload in sorted(bundle.documents.items()):
            safe_relative = normalize_relative_path(relative_path)
            target = temporary / PurePosixPath(safe_relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(document_bytes(payload))
        os.replace(temporary, destination)  # A complete tree becomes visible in one directory rename.
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)  # The path was created by this transaction only.
        raise
    return {
        "status": "PASS",
        "action": "SHADOW_WRITTEN",
        "shadowRoot": str(destination),
        "summary": bundle.summary,
        "writtenFiles": sorted(bundle.documents),
        "mutations": len(bundle.documents),
    }
