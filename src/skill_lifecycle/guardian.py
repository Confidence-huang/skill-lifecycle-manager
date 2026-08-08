"""
Observe every registered Skill, publish daily evidence, and bind updates to human approval.

The Guardian keeps one readable chain: a CLI trigger selects desired monitoring policy, this module
reads canonical Registry state, performs bounded read-only probes, and returns or publishes a report.
Approval consumes one immutable report and creates one exact credential; it never performs an update.

Typical use:
    scan_guardian(layout, apply=True)
    approve_guardian_update(layout, report_path=report, name="example", ..., apply=True)
"""

from __future__ import annotations  # Keep Python 3.12 annotations visible to callers and tests.

import hashlib  # Give reports and built-in policy deterministic identities.
import json  # Read desired policy, Registry evidence, reports, and approvals.
import re  # Validate durable decision IDs and extract dependency versions without exposing output.
import shutil  # Resolve declared dependency and compatibility executables on the reviewed PATH.
import subprocess  # Execute only bounded argument arrays; no probe is interpreted by a shell.
import sys  # Schedule the exact running Python environment instead of guessing a global executable.
from datetime import datetime, timezone  # Create explicit UTC report times and evaluate approval expiry.
from pathlib import Path  # Keep every evidence location exact and host-native.
from typing import Any  # Preserve visible JSON document shapes at the module interface.

from skill_lifecycle.contracts import parse_timestamp  # Reuse the timezone-aware approval gate.
from skill_lifecycle.freshness import STABLE_VERSION, check_record  # Reuse PACKAGE stable-release evidence.
from skill_lifecycle.operations import run_git  # Reuse the no-shell Git command seam.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_json, atomic_text, sha256_file  # Publish only approved evidence.


POLICY_FIELDS = {"schemaVersion", "documentType", "policyVersion", "skills"}  # Reject hidden desired-state controls.
SKILL_POLICY_FIELDS = {"name", "enabled", "riskTier", "updatePolicy", "dependencies", "compatibilityProbe"}
PROBE_FIELDS = {"command", "arguments"}  # A probe is always one executable plus literal arguments.
DEPENDENCY_FIELDS = {"name", "command", "arguments"}  # Dependency names are report labels, not command input.
RISK_TIERS = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}  # Risk is declared judgment, never inferred quality.
UPDATE_POLICIES = {"NOTIFY", "REQUIRE_APPROVAL"}  # Neither value grants unattended mutation in V5.2.
DECISION_ID = re.compile(r"^approval-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
PROBE_TIMEOUT_SECONDS = 10  # Scheduled checks must finish instead of becoming unbounded workflows.
SAFE_POLICY_VERSION = "builtin-safe-v1"  # Missing policy means observe all and require human review.


# --- Validate one argument-array probe ---
def validate_probe(probe: Any, *, dependency: bool = False) -> dict[str, Any]:
    """Return one normalized probe or stop before untrusted fields can reach subprocess."""
    expected = DEPENDENCY_FIELDS if dependency else PROBE_FIELDS
    if not isinstance(probe, dict) or set(probe) != expected:  # Exact keys prevent hidden shell or environment controls.
        raise LifecycleBlocked(f"Guardian probe fields must be exactly {sorted(expected)}.")
    command = probe.get("command")
    arguments = probe.get("arguments")
    if not isinstance(command, str) or not command or len(command) > 256:
        raise LifecycleBlocked("Guardian probe command must be a non-empty bounded string.")
    if not isinstance(arguments, list) or len(arguments) > 32 or any(not isinstance(value, str) or len(value) > 1024 for value in arguments):
        raise LifecycleBlocked("Guardian probe arguments must be a bounded string array.")
    normalized = {"command": command, "arguments": list(arguments)}  # Copy input so later callers cannot mutate policy in place.
    if dependency:
        name = probe.get("name")
        if not isinstance(name, str) or not name or len(name) > 128:
            raise LifecycleBlocked("Guardian dependency name must be a non-empty bounded string.")
        normalized = {"name": name, **normalized}
    return normalized


# --- Validate desired monitoring policy ---
def validate_guardian_policy(document: Any) -> dict[str, Any]:
    """Return one strict policy whose tiers can notify but never authorize automatic updates."""
    if not isinstance(document, dict) or set(document) != POLICY_FIELDS:
        raise LifecycleBlocked(f"Guardian policy fields must be exactly {sorted(POLICY_FIELDS)}.")
    if document.get("schemaVersion") != 1 or document.get("documentType") != "SKILL_GUARDIAN_POLICY":
        raise LifecycleBlocked("Guardian policy identity is unsupported.")
    version = document.get("policyVersion")
    policies = document.get("skills")
    if not isinstance(version, str) or not version or len(version) > 128:
        raise LifecycleBlocked("Guardian policyVersion must be a non-empty bounded string.")
    if not isinstance(policies, list):
        raise LifecycleBlocked("Guardian policy skills must be an array.")

    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for policy in policies:
        if not isinstance(policy, dict) or set(policy) != SKILL_POLICY_FIELDS:
            raise LifecycleBlocked(f"Guardian Skill policy fields must be exactly {sorted(SKILL_POLICY_FIELDS)}.")
        name = policy.get("name")
        if not isinstance(name, str) or not name or len(name) > 128 or name in names:
            raise LifecycleBlocked(f"Guardian Skill policy name is invalid or duplicated: {name!r}")
        names.add(name)
        if not isinstance(policy.get("enabled"), bool):
            raise LifecycleBlocked(f"Guardian enabled must be boolean: {name}")
        if policy.get("riskTier") not in RISK_TIERS or policy.get("updatePolicy") not in UPDATE_POLICIES:
            raise LifecycleBlocked(f"Guardian risk or update policy is unsupported: {name}")
        dependencies = policy.get("dependencies")
        if not isinstance(dependencies, list) or len(dependencies) > 32:
            raise LifecycleBlocked(f"Guardian dependencies must be a bounded array: {name}")
        probe = policy.get("compatibilityProbe")
        normalized.append(
            {
                "name": name,
                "enabled": policy["enabled"],
                "riskTier": policy["riskTier"],
                "updatePolicy": policy["updatePolicy"],
                "dependencies": [validate_probe(item, dependency=True) for item in dependencies],
                "compatibilityProbe": None if probe is None else validate_probe(probe),
            }
        )
    return {"schemaVersion": 1, "documentType": "SKILL_GUARDIAN_POLICY", "policyVersion": version, "skills": normalized}


# --- Read and identify policy without changing canonical state ---
def read_guardian_policy(layout: HostLayout, source: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return configured policy plus identity, or the explicit built-in safe default."""
    path = source or layout.guardian_policy_path
    if not path.is_file():
        document = {"schemaVersion": 1, "documentType": "SKILL_GUARDIAN_POLICY", "policyVersion": SAFE_POLICY_VERSION, "skills": []}
        identity = {"state": "SAFE_DEFAULT", "version": SAFE_POLICY_VERSION, "sha256": None, "path": None}
        return document, identity
    document = validate_guardian_policy(json.loads(path.read_text(encoding="utf-8")))
    identity = {"state": "CONFIGURED", "version": document["policyVersion"], "sha256": sha256_file(path), "path": str(path.resolve())}
    return document, identity


# --- Preview or publish canonical desired policy ---
def publish_guardian_policy(layout: HostLayout, source: Path, apply: bool) -> dict[str, Any]:
    """Validate one policy and publish it only after the caller supplies --apply."""
    if not source.is_file():
        raise LifecycleBlocked(f"Guardian policy source is missing: {source}")
    document = validate_guardian_policy(json.loads(source.read_text(encoding="utf-8")))
    result = {
        "status": "PASS",
        "action": "GUARDIAN_POLICY_WRITTEN" if apply else "GUARDIAN_POLICY_PREVIEW",
        "policyPath": str(layout.guardian_policy_path),
        "policyVersion": document["policyVersion"],
        "policySHA256": hashlib.sha256((json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).hexdigest().upper(),
        "mutations": 1 if apply else 0,
    }
    if apply:
        atomic_json(layout.guardian_policy_path, document)  # Desired monitoring state stays separate from Registry observations.
        result["policySHA256"] = sha256_file(layout.guardian_policy_path)
    return result


# --- Run one declared local probe ---
def run_probe(probe: dict[str, Any], *, compatibility: bool) -> dict[str, Any]:
    """Return bounded status and optional version without retaining potentially sensitive output."""
    executable = shutil.which(probe["command"])
    if executable is None:
        state = "UNKNOWN" if compatibility else "MISSING"
        return {"name": probe.get("name"), "status": state, "version": None, "issue": "Executable is not installed."}
    try:
        completed = subprocess.run(
            [executable, *probe["arguments"]],
            text=True,
            capture_output=True,
            check=False,
            timeout=PROBE_TIMEOUT_SECONDS,
        )  # Argument arrays keep policy text from becoming shell syntax.
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"name": probe.get("name"), "status": "UNKNOWN", "version": None, "issue": f"Probe failed: {type(error).__name__}."}
    if compatibility:
        return {"name": None, "status": "PASS" if completed.returncode == 0 else "BLOCKED", "version": None, "issue": None if completed.returncode == 0 else f"Probe exited {completed.returncode}."}
    version_match = STABLE_VERSION.search(f"{completed.stdout}\n{completed.stderr}")
    version = ".".join(version_match.groups()) if version_match else None
    return {"name": probe["name"], "status": "PRESENT" if completed.returncode == 0 else "UNKNOWN", "version": version, "issue": None if completed.returncode == 0 else f"Probe exited {completed.returncode}."}


# --- Inspect one SOURCE or HYBRID update channel without fetching ---
def inspect_source_update(record: dict[str, Any]) -> tuple[str | None, str | None, str, str | None]:
    """Return current/candidate/status/issue through `ls-remote`, leaving Git object state unchanged."""
    repository_text = record.get("sourceRepository")
    remote = record.get("remote")
    branch = record.get("branch")
    current = record.get("commit")
    if not repository_text or not remote or not branch or not current:
        return current, None, "NOT_CONFIGURED", "Source update channel lacks repository, origin, branch, or commit evidence."
    repository = Path(repository_text)
    if record.get("sourceDirty"):
        return current, None, "UNKNOWN", f"Source repository is dirty: {repository}"
    completed = run_git(repository, "ls-remote", "--heads", "origin", branch)
    if completed.returncode or not completed.stdout.strip():
        detail = completed.stderr.strip() or "remote branch was not found"
        return current, None, "UNKNOWN", f"Remote inspection failed: {detail}"
    candidate = completed.stdout.split()[0]
    status = "CURRENT" if candidate == current else "UPDATE_AVAILABLE"
    return current, candidate, status, None


# --- Build one Skill report row ---
def scan_record(record: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    """Combine observed Registry identity, desired monitoring rules, and bounded probe evidence."""
    selected = policy or {
        "name": record.get("name"),
        "enabled": True,
        "riskTier": "UNKNOWN",
        "updatePolicy": "REQUIRE_APPROVAL",
        "dependencies": [],
        "compatibilityProbe": None,
    }  # Unconfigured Skills remain visible under the most conservative action policy.
    dependencies = [run_probe(probe, compatibility=False) for probe in selected["dependencies"]] if selected["enabled"] else []
    compatibility = run_probe(selected["compatibilityProbe"], compatibility=True) if selected["enabled"] and selected["compatibilityProbe"] else {"status": "UNKNOWN", "issue": "No compatibility probe is configured."}

    if not selected["enabled"]:
        current, candidate, update_status, issue = record.get("commit"), None, "DISABLED", "Monitoring is disabled by policy."
    elif record.get("lifecycleMode") in {"SOURCE", "HYBRID"} and record.get("sourceRepository"):
        current, candidate, update_status, issue = inspect_source_update(record)
    elif record.get("updates"):
        package = check_record(record)
        current, candidate = package.get("currentVersion"), package.get("latestVersion")
        update_status, issue = package["updateStatus"], package.get("issue")
    else:
        current = record.get("commit")
        candidate, update_status, issue = None, "NOT_CONFIGURED", "No supported update channel is configured."

    issues = [value for value in [issue, compatibility.get("issue")] if value]
    issues.extend(result["issue"] for result in dependencies if result.get("issue"))
    action = "MANUAL_REVIEW" if update_status == "UPDATE_AVAILABLE" else "INVESTIGATE" if update_status == "UNKNOWN" else "NONE"
    return {
        "name": record.get("name"),
        "lifecycleMode": record.get("lifecycleMode"),
        "healthStatus": record.get("status", "UNKNOWN"),
        "current": current,
        "candidate": candidate,
        "updateStatus": update_status,
        "compatibilityStatus": compatibility["status"],
        "riskTier": selected["riskTier"],
        "updatePolicy": selected["updatePolicy"],
        "dependencies": dependencies,
        "issues": issues,
        "action": action,
    }


# --- Render one standalone human report ---
def guardian_markdown(report: dict[str, Any]) -> str:
    """Render compact evidence without writing to a project continuity log."""
    lines = [
        "# Skill Guardian Report",
        "",
        f"Generated at `{report['generatedAt']}` from Registry fingerprint `{report['registry']['inventoryFingerprint']}`.",
        "",
        "| Skill | Health | Update | Dependencies | Compatibility | Risk | Action |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["skills"]:
        lines.append(f"| `{row['name']}` | {row['healthStatus']} | {row['updateStatus']} | {row['dependencyChangeStatus']} | {row['compatibilityStatus']} | {row['riskTier']} | {row['action']} |")
    lines.extend(["", "This report never authorizes or performs a Skill update. Compatibility remains `UNKNOWN` without a declared passing probe."])
    return "\n".join(lines) + "\n"


# --- Compare declared dependency evidence with the previous completed scan ---
def add_dependency_changes(layout: HostLayout, rows: list[dict[str, Any]]) -> None:
    """Annotate host dependency drift while leaving candidate-file compatibility explicitly unknown."""
    previous_rows: dict[str, dict[str, Any]] = {}
    if layout.guardian_latest_json_path.is_file():
        try:
            previous = json.loads(layout.guardian_latest_json_path.read_text(encoding="utf-8"))
            previous_rows = {row.get("name"): row for row in previous.get("skills", []) if isinstance(row, dict)}
        except (OSError, json.JSONDecodeError):
            previous_rows = {}  # Unreadable prior evidence cannot establish a change; it is never silently repaired.
    for row in rows:
        dependencies = row["dependencies"]
        if not dependencies:
            row["dependencyChangeStatus"] = "NOT_CONFIGURED"
            continue
        previous_dependencies = {
            dependency.get("name"): dependency
            for dependency in previous_rows.get(row["name"], {}).get("dependencies", [])
            if isinstance(dependency, dict)
        }
        changes: list[str] = []
        for dependency in dependencies:
            previous_version = previous_dependencies.get(dependency["name"], {}).get("version")
            dependency["previousVersion"] = previous_version
            if dependency["version"] is None or previous_version is None:
                dependency["changeStatus"] = "UNKNOWN"
            elif dependency["version"] == previous_version:
                dependency["changeStatus"] = "UNCHANGED"
            else:
                dependency["changeStatus"] = "CHANGED"
            changes.append(dependency["changeStatus"])
        row["dependencyChangeStatus"] = "CHANGED" if "CHANGED" in changes else "UNKNOWN" if "UNKNOWN" in changes else "UNCHANGED"


# --- Scan all canonical Registry records ---
def scan_guardian(layout: HostLayout, policy_path: Path | None = None, apply: bool = False, observed_at: str | None = None) -> dict[str, Any]:
    """Return or publish one daily report while leaving every managed Skill and Registry unchanged."""
    if not layout.registry_path.is_file():
        raise LifecycleBlocked(f"Registry is missing: {layout.registry_path}")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
    records = registry.get("skills")
    fingerprint = registry.get("inventoryFingerprint")
    if not isinstance(records, list) or not isinstance(fingerprint, str):
        raise LifecycleBlocked("Registry lacks readable skills or inventoryFingerprint evidence.")
    policy, policy_identity = read_guardian_policy(layout, policy_path)
    policies = {item["name"]: item for item in policy["skills"]}
    generated_at = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed_time = parse_timestamp(generated_at)
    canonical_time = parsed_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [scan_record(record, policies.get(record.get("name"))) for record in records]
    add_dependency_changes(layout, rows)  # Compare only host-observed versions; candidate dependency files remain unproved.
    states = ("CURRENT", "UPDATE_AVAILABLE", "AHEAD", "UNKNOWN", "NOT_CONFIGURED", "DISABLED")
    summary = {
        "checked": len(rows),
        **{state: sum(row["updateStatus"] == state for row in rows) for state in states},
        "compatibilityUnknown": sum(row["compatibilityStatus"] == "UNKNOWN" for row in rows),
        "healthUnknown": sum(row["healthStatus"] == "UNKNOWN" for row in rows),
        "dependencyUnknown": sum(row["dependencyChangeStatus"] == "UNKNOWN" for row in rows),
    }
    identity_input = f"{canonical_time}\n{fingerprint}\n{policy_identity['version']}\n{policy_identity['sha256']}"
    report_id = f"guardian-{parsed_time.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(identity_input.encode()).hexdigest()[:12]}"
    report = {
        "schemaVersion": 1,
        "documentType": "SKILL_GUARDIAN_REPORT",
        "reportID": report_id,
        "generatedAt": canonical_time,
        "registry": {"path": str(layout.registry_path.resolve()), "sha256": sha256_file(layout.registry_path), "inventoryFingerprint": fingerprint},
        "policy": policy_identity,
        "summary": summary,
        "skills": rows,
        "mutations": 0,
    }
    history_json = layout.guardian_history_root / f"{report_id}.json"
    history_markdown = layout.guardian_history_root / f"{report_id}.md"
    if apply and (history_json.exists() or history_markdown.exists()):
        raise LifecycleBlocked(f"Guardian report identity already exists: {report_id}")
    if apply:
        atomic_json(history_json, report)
        atomic_text(history_markdown, guardian_markdown(report))
        atomic_json(layout.guardian_latest_json_path, report)
        atomic_text(layout.guardian_latest_markdown_path, guardian_markdown(report))
    return {
        "status": "UNKNOWN" if any(summary[key] for key in ("UNKNOWN", "compatibilityUnknown", "healthUnknown", "dependencyUnknown")) else "PASS",
        "action": "GUARDIAN_REPORT_WRITTEN" if apply else "GUARDIAN_SCAN_PREVIEW",
        "report": report,
        "jsonPath": str(history_json),
        "markdownPath": str(history_markdown),
        "latestJSONPath": str(layout.guardian_latest_json_path),
        "latestMarkdownPath": str(layout.guardian_latest_markdown_path),
        "mutations": 4 if apply else 0,
    }


# --- Publish one exact human update approval ---
def approve_guardian_update(
    layout: HostLayout,
    *,
    report_path: Path,
    name: str,
    decision_id: str,
    requested_by: str,
    requested_at: str,
    decided_by: str,
    decided_at: str,
    expires_at: str,
    reason: str,
    apply: bool,
) -> dict[str, Any]:
    """Create an immutable credential for one report row without changing the selected Skill."""
    if not DECISION_ID.fullmatch(decision_id):
        raise LifecycleBlocked("Guardian approval decision ID must be an approval-prefixed UUIDv4.")
    if not report_path.is_file():
        raise LifecycleBlocked(f"Guardian approval report is missing: {report_path}")
    if report_path.resolve().parent != layout.guardian_history_root.resolve():
        raise LifecycleBlocked("Guardian approval requires an immutable report beneath the Guardian history root.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("documentType") != "SKILL_GUARDIAN_REPORT":
        raise LifecycleBlocked("Guardian approval input is not a Guardian report.")
    rows = [row for row in report.get("skills", []) if row.get("name") == name]
    if len(rows) != 1:
        raise LifecycleBlocked(f"Guardian approval expected one report row named {name}, found {len(rows)}.")
    row = rows[0]
    if row.get("lifecycleMode") not in {"SOURCE", "HYBRID"} or row.get("updateStatus") != "UPDATE_AVAILABLE":
        raise LifecycleBlocked("Guardian approval requires one SOURCE/HYBRID update candidate.")
    if not row.get("current") or not row.get("candidate"):
        raise LifecycleBlocked("Guardian approval requires exact current and candidate commits.")
    requested_time = parse_timestamp(requested_at)
    decided_time = parse_timestamp(decided_at)
    expiry_time = parse_timestamp(expires_at)
    if requested_time > decided_time or expiry_time <= decided_time:
        raise LifecycleBlocked("Guardian approval timestamps must satisfy requestedAt <= decidedAt < expiresAt.")
    if not all(isinstance(value, str) and value.strip() for value in (requested_by, decided_by, reason)):
        raise LifecycleBlocked("Guardian approval actors and reason must be non-empty strings.")

    _, current_policy = read_guardian_policy(layout)
    if report.get("policy") != current_policy:
        raise LifecycleBlocked("Guardian approval report policy no longer matches canonical desired state.")
    current_registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
    if report.get("registry", {}).get("inventoryFingerprint") != current_registry.get("inventoryFingerprint"):
        raise LifecycleBlocked("Guardian approval report Registry fingerprint is stale.")
    document = {
        "schemaVersion": 1,
        "documentType": "SKILL_GUARDIAN_UPDATE_APPROVAL",
        "decisionID": decision_id,
        "decision": "APPROVED",
        "skillName": name,
        "lifecycleMode": row["lifecycleMode"],
        "current": row["current"],
        "candidate": row["candidate"],
        "registryFingerprint": report["registry"]["inventoryFingerprint"],
        "policyVersion": report["policy"]["version"],
        "policySHA256": report["policy"]["sha256"],
        "reportPath": str(report_path.resolve()),
        "reportSHA256": sha256_file(report_path),
        "requestedBy": requested_by,
        "requestedAt": requested_at,
        "decidedBy": decided_by,
        "decidedAt": decided_at,
        "expiresAt": expires_at,
        "reason": reason,
    }
    approval_path = layout.guardian_approval_root / f"{decision_id}.json"
    if apply and approval_path.exists():
        raise LifecycleBlocked(f"Guardian approval already exists: {approval_path}")
    if apply:
        atomic_json(approval_path, document)
    return {"status": "PASS", "action": "GUARDIAN_APPROVAL_WRITTEN" if apply else "GUARDIAN_APPROVAL_PREVIEW", "approvalPath": str(approval_path), "approval": document, "mutations": 1 if apply else 0}


# --- Require exact approval immediately before mutation ---
def require_guardian_approval(layout: HostLayout, approval_path: Path | None, name: str, current: str, candidate: str, evaluated_at: str | None) -> dict[str, Any]:
    """Return one current approval or block before fetch, worktree creation, merge, or Registry write."""
    if approval_path is None or evaluated_at is None:
        raise LifecycleBlocked("Source update apply requires a Guardian approval and --evaluated-at.")
    if not approval_path.is_file():
        raise LifecycleBlocked(f"Guardian approval is missing: {approval_path}")
    if approval_path.resolve().parent != layout.guardian_approval_root.resolve():
        raise LifecycleBlocked("Guardian approval must be an immutable file beneath the Guardian approval root.")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("documentType") != "SKILL_GUARDIAN_UPDATE_APPROVAL" or approval.get("decision") != "APPROVED":
        raise LifecycleBlocked("Guardian approval document is unsupported or not approved.")
    expected = {"skillName": name, "current": current, "candidate": candidate}
    for field, value in expected.items():
        if approval.get(field) != value:
            raise LifecycleBlocked(f"Guardian approval {field} does not match the live update candidate.")
    if parse_timestamp(approval.get("expiresAt")) <= parse_timestamp(evaluated_at):
        raise LifecycleBlocked("Guardian approval is expired.")
    report_path = Path(approval.get("reportPath", ""))
    if not report_path.is_file() or sha256_file(report_path) != approval.get("reportSHA256"):
        raise LifecycleBlocked("Guardian approval report evidence is missing or changed.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = [row for row in report.get("skills", []) if row.get("name") == name]
    if len(rows) != 1 or rows[0].get("current") != current or rows[0].get("candidate") != candidate:
        raise LifecycleBlocked("Guardian approval fields do not match their immutable report row.")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))
    if registry.get("inventoryFingerprint") != approval.get("registryFingerprint"):
        raise LifecycleBlocked("Guardian approval Registry fingerprint no longer matches.")
    _, policy = read_guardian_policy(layout)
    if policy["version"] != approval.get("policyVersion") or policy["sha256"] != approval.get("policySHA256"):
        raise LifecycleBlocked("Guardian approval policy identity no longer matches.")
    if report.get("registry", {}).get("inventoryFingerprint") != approval.get("registryFingerprint") or report.get("policy") != policy:
        raise LifecycleBlocked("Guardian approval report no longer matches Registry or policy identity.")
    return approval


# --- Preview or install one daily scan trigger ---
def schedule_guardian(layout: HostLayout, schedule_time: str, apply: bool, *, home: Path | None = None) -> dict[str, Any]:
    """Install only `guardian scan --apply`; production update remains a separate human trigger."""
    if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", schedule_time):
        raise LifecycleBlocked("Guardian schedule time must use 24-hour HH:MM format.")
    command = [
        sys.executable,
        "-m",
        "skill_lifecycle",
        "--activity-root",
        str(layout.activity_root),
        "--data-root",
        str(layout.data_root),
        "--state-root",
        str(layout.state_root),
        "--cache-root",
        str(layout.cache_root),
        "guardian",
        "scan",
        "--apply",
    ]  # Exact roots make a scheduled report refer to the same Registry selected during installation.
    try:
        schedule = layout.platform.guardian_schedule(command, schedule_time, apply, home=home)
    except OSError as error:
        raise LifecycleBlocked(str(error)) from error
    return {
        "status": "PASS",
        "action": "GUARDIAN_SCHEDULE_INSTALLED" if apply else "GUARDIAN_SCHEDULE_PREVIEW",
        "scheduleTime": schedule_time,
        **schedule,
    }
