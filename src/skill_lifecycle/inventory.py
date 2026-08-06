"""
Read Skill identity, classify lifecycle evidence, and generate Registry views.

Scanning is the read side of the product: activity roots lead to physical SKILL.md files, physical
identity leads to Git and governance evidence, and the result becomes structured feedback. Writers
publish only a caller-approved complete Registry plus generated YAML and Markdown views.
"""

from __future__ import annotations  # Keep modern type syntax stable on Python 3.12.

import hashlib  # Fingerprint stable physical inventory independently from presentation fields.
import json  # Build deterministic Registry identity and a YAML-compatible mirror.
import os  # Walk Skill trees without following symbolic-link directories.
import re  # Validate stable semantic versions and bounded tag prefixes in PACKAGE update contracts.
import subprocess  # Query Git identity without a shell command string.
from datetime import datetime, timezone  # Timestamp completed evidence in UTC.
from pathlib import Path  # Preserve Linux case-sensitive path identity.
from typing import Any, Iterable  # Describe the structured Registry data flow.

from skill_lifecycle.paths import HostLayout, atomic_json, atomic_text, sha256_file  # Publish verified state safely.


GENERATOR = "skill-lifecycle-manager/4.1.0"  # Identify Registries that include PACKAGE freshness contracts.

CAPABILITY_RULES = {
    "lifecycle-governance": ("skill", "lifecycle", "registry", "governance", "archive"),
    "software-engineering": ("code", "debug", "test", "implement", "architecture", "github"),
    "learning-research": ("learn", "teach", "research", "paper", "exam", "course"),
    "documents-media": ("document", "pdf", "slide", "video", "audio", "image"),
    "hardware-embedded": ("mcu", "stm32", "mspm0", "embedded", "hardware", "k230"),
}  # Lexical navigation rules never claim semantic equivalence or quality.

STABLE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")  # PACKAGE baselines exclude prerelease ambiguity.
TAG_PREFIX = re.compile(r"^[A-Za-z0-9._-]{0,32}$")  # A short literal prefix cannot become an open-ended ref expression.


def utc_now() -> str:
    """Create one sortable UTC timestamp for a completed evidence document."""
    return datetime.now(timezone.utc).isoformat()


def read_skill(skill_file: Path) -> tuple[str, str, list[str]]:
    """Read the frontmatter scalars required for identity and retain exact parse gaps."""
    text = skill_file.read_text(encoding="utf-8")  # Skill metadata is required to be UTF-8.
    name = skill_file.parent.name  # Directory identity remains visible when frontmatter is invalid.
    description = ""  # Missing descriptions remain evidence gaps instead of invented content.
    issues: list[str] = []
    if not text.startswith("---\n"):
        return name, description, ["Missing YAML frontmatter."]

    end = text.find("\n---\n", 4)  # Only the first YAML document controls Skill discovery.
    if end < 0:
        return name, description, ["Unterminated YAML frontmatter."]
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")  # The name/description subset is scalar-only.
        if not separator:
            continue
        cleaned = value.strip().strip('"\'')
        if key.strip() == "name" and cleaned:
            name = cleaned
        if key.strip() == "description":
            description = cleaned
    if not description:
        issues.append("Frontmatter description is missing.")
    return name, description, issues


# --- Validate one optional release-check contract ---
def validate_updates(updates: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Accept the dependency-free git-tag and CLI fields used by read-only freshness checks."""
    if updates is None:  # Historical PACKAGE records remain valid without freshness configuration.
        return None, []
    if not isinstance(updates, dict):  # Structured fields prevent a scalar from becoming command input.
        return None, ["Installed-package update contract must be an object."]

    strategy = updates.get("strategy")  # Only an implemented strategy can reach a network probe.
    repository = updates.get("repository")  # The reviewed Git endpoint is passed as one argument.
    tag_prefix = updates.get("tagPrefix", "v")  # Literal `v` matches common stable release tags.
    baseline = updates.get("baselineVersion")  # Adapter compatibility remains distinct from live CLI state.
    cli = updates.get("cli")  # CLI evidence is optional for packages without a companion executable.
    issues: list[str] = []
    if strategy != "git-tags":
        issues.append("Installed-package update strategy must be git-tags.")
    if not isinstance(repository, str) or not repository.strip():
        issues.append("Installed-package update repository must be a non-empty string.")
    if not isinstance(tag_prefix, str) or not TAG_PREFIX.fullmatch(tag_prefix):
        issues.append("Installed-package tagPrefix must be a short literal ref prefix.")
    if not isinstance(baseline, str) or not STABLE_VERSION.fullmatch(baseline):
        issues.append("Installed-package baselineVersion must be MAJOR.MINOR.PATCH.")
    if cli is not None:
        if not isinstance(cli, dict):
            issues.append("Installed-package cli contract must be an object.")
        else:
            command = cli.get("command")  # Command names are resolved through PATH without a shell.
            arguments = cli.get("arguments", [])  # Every argument remains one literal subprocess item.
            if not isinstance(command, str) or not command.strip():
                issues.append("Installed-package cli command must be a non-empty string.")
            if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
                issues.append("Installed-package cli arguments must be a string array.")
    if issues:
        return None, issues  # Invalid contracts stay visible but can never trigger a subprocess.
    return {
        "strategy": strategy,
        "repository": repository.strip(),
        "tagPrefix": tag_prefix,
        "baselineVersion": baseline,
        "cli": cli,
    }, []  # Registry stores the normalized executable contract, not unrelated package metadata.


# --- Read PACKAGE provenance beside one physical Skill ---
def read_package_record(skill_root: Path) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    """Return validated PACKAGE provenance, its hash, and literal evidence gaps."""
    record_path = skill_root / ".skill-lifecycle.json"  # The provenance record travels with PACKAGE bytes.
    if not record_path.is_file():
        return None, None, []  # Older unmanaged packages remain observable without invented history.
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))  # JSON is the established schema-1 format.
    except (OSError, json.JSONDecodeError) as error:
        return None, sha256_file(record_path), [f"Installed-package provenance is unreadable: {error}"]
    if not isinstance(record, dict) or record.get("schemaVersion") != 1 or record.get("lifecycleMode") != "PACKAGE":
        return None, sha256_file(record_path), ["Installed-package provenance uses an unsupported schema."]

    updates, update_issues = validate_updates(record.get("updates"))  # Untrusted command fields pass one strict gate.
    normalized = {
        "origin": record.get("origin") if isinstance(record.get("origin"), str) else None,
        "remote": record.get("remote") if isinstance(record.get("remote"), str) else None,
        "commit": record.get("commit") if isinstance(record.get("commit"), str) else None,
        "updates": updates,
    }  # Only provenance and freshness fields belong in Registry evidence.
    return normalized, sha256_file(record_path), update_issues


def walk_skill_files(entry: Path) -> Iterable[Path]:
    """Yield physical SKILL.md files without entering nested filesystem links."""
    target = entry.resolve(strict=True)  # Broken activity links are captured by the caller.
    if target.is_file():
        return  # A top-level file cannot expose a Skill directory.
    for directory, child_directories, files in os.walk(target, followlinks=False):
        child_directories[:] = [
            name for name in child_directories if not (Path(directory) / name).is_symlink()
        ]  # Nested activity aliases are evidence, never traversal requests.
        if "SKILL.md" in files:
            yield Path(directory) / "SKILL.md"


def git_value(path: Path, *arguments: str) -> str | None:
    """Read one Git fact from the repository containing path without changing it."""
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )  # Argument arrays prevent source paths from becoming shell syntax.
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else None


def git_identity(path: Path) -> dict[str, Any]:
    """Return repository provenance and cleanliness for one physical Skill path."""
    repository_text = git_value(path, "rev-parse", "--show-toplevel")
    if not repository_text:
        return {"repository": None, "remote": None, "branch": None, "commit": None, "dirty": None, "entryCount": 1}
    repository = Path(repository_text).resolve()  # Git returns the authoritative physical top level.
    status = git_value(repository, "status", "--porcelain=v1") or ""
    entries = sum(1 for _ in repository.rglob("SKILL.md"))  # Multi-Skill sources require HYBRID activation.
    return {
        "repository": str(repository),
        "remote": git_value(repository, "remote", "get-url", "origin"),
        "branch": git_value(repository, "branch", "--show-current"),
        "commit": git_value(repository, "rev-parse", "HEAD"),
        "dirty": bool(status),
        "entryCount": entries,
    }


def infer_scope(active_paths: list[str]) -> str:
    """Classify activation ownership separately from acquisition mode."""
    normalized = [path.replace("\\", "/") for path in active_paths]
    if any("/plugins-cache/" in path or "/.system/" in path for path in normalized):
        return "SYSTEM"
    if any("/.agents/skills/" in path or path.endswith("/.agents/skills") for path in normalized):
        return "USER"
    if any("/.codex/skills/" in path for path in normalized):
        return "PROJECT"
    return "UNKNOWN"


def capability_domains(name: str, description: str) -> tuple[list[str], list[str]]:
    """Map explicit lexical signals to navigation domains and explain every assignment."""
    haystack = f"{name} {description}".lower()
    domains: list[str] = []
    evidence: list[str] = []
    for domain, terms in CAPABILITY_RULES.items():
        matched = [term for term in terms if term in haystack]
        if matched:
            domains.append(domain)  # Domains overlap because a Skill may serve several workflows.
            evidence.append(f"{domain}: {', '.join(matched)}")
    if not domains:
        return ["unclassified"], ["No configured lexical capability signal matched."]
    return domains, evidence


def add_governance(record: dict[str, Any], collision_count: int) -> None:
    """Attach evidence readiness without fabricating quality, usage, or security claims."""
    score = 0
    score += 25 if record["name"] and record["description"] else 0
    score += 15 if record["activePaths"] else 0
    score += 20 if record["lifecycleMode"] != "UNKNOWN" else 0
    score += 25 if record["scope"] == "SYSTEM" or record["commit"] or record["origin"] else 0
    score += 15 if collision_count == 1 else 0
    gaps: list[str] = []
    if not record["description"]:
        gaps.append("description")
    if record["lifecycleMode"] == "UNKNOWN":
        gaps.append("lifecycleMode")
    if not (record["scope"] == "SYSTEM" or record["commit"] or record["origin"]):
        gaps.append("provenance")
    if collision_count > 1:
        gaps.append("nameCollision")
    record["evidenceReadinessScore"] = score
    record["evidenceTier"] = "READY_EVIDENCE" if score >= 90 else "PARTIAL_EVIDENCE" if score >= 75 else "REVIEW_EVIDENCE"
    if record["issues"] or collision_count > 1:
        record["governanceState"] = "REVIEW_REQUIRED"
    elif record["scope"] == "SYSTEM":
        record["governanceState"] = "SYSTEM_MANAGED"
    elif not record["isTopLevel"]:
        record["governanceState"] = "MANAGED_WITH_PARENT"
    else:
        record["governanceState"] = "AVAILABLE"
    record["qualityEvidence"] = "UNKNOWN"
    record["usageEvidence"] = "UNKNOWN"
    record["securityEvidence"] = "UNKNOWN"
    record["overallGrade"] = "UNRATED"
    record["recommendedAction"] = "Review evidence gaps." if gaps else "Keep available and gather real-use evidence."
    record["governanceGaps"] = gaps


def inventory_fingerprint(records: list[dict[str, Any]]) -> str:
    """Hash physical identity without folding host-derived governance labels into drift."""
    identity = [
        {
            "name": record["name"],
            "physicalPath": record["physicalPath"],
            "lifecycleMode": record["lifecycleMode"],
            "commit": record["commit"],
            "skillSHA256": record["skillSHA256"],
            "lifecycleSHA256": record["lifecycleSHA256"],
        }
        for record in records
    ]
    ordered = sorted(identity, key=lambda item: (item["name"], item["physicalPath"]))
    encoded = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def scan_skills(activity_roots: Iterable[Path]) -> dict[str, Any]:
    """Inventory exact Linux Skill identities without changing any scanned path."""
    roots = [Path(root).expanduser().resolve() for root in activity_roots]
    records_by_file: dict[str, dict[str, Any]] = {}  # Physical SKILL.md identity deduplicates aliases.
    broken_links: list[str] = []
    for root in roots:
        if not root.exists():
            continue  # An absent optional root contributes no invented assets.
        for entry in sorted(root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink() and not entry.exists():
                broken_links.append(str(entry))  # Preserve the unusable activation as explicit evidence.
                continue
            if not entry.is_dir():
                continue
            for skill_file in walk_skill_files(entry):
                physical_file = skill_file.resolve(strict=True)
                physical_key = str(physical_file)  # Linux case-sensitive identities must never be lowercased.
                relative = skill_file.parent.relative_to(entry.resolve(strict=True))
                active_path = entry if str(relative) == "." else entry / relative
                if physical_key not in records_by_file:
                    name, description, issues = read_skill(physical_file)
                    git = git_identity(physical_file.parent)
                    package, lifecycle_hash, package_issues = read_package_record(physical_file.parent)
                    issues.extend(package_issues)  # Malformed provenance degrades evidence instead of disappearing.
                    is_link = entry.is_symlink()
                    if git["repository"]:
                        mode = "HYBRID" if git["entryCount"] > 1 else "SOURCE"
                    else:
                        mode = "PACKAGE" if not is_link else "HYBRID"
                    domains, domain_evidence = capability_domains(name, description)
                    records_by_file[physical_key] = {
                        "name": name,
                        "description": description,
                        "status": "PASS" if not issues else "UNKNOWN",
                        "scope": "UNKNOWN",
                        "lifecycleMode": mode,
                        "activePaths": [],
                        "physicalPath": str(physical_file.parent),
                        "origin": package.get("origin") if package and not git["repository"] else None,
                        "sourceRepository": git["repository"],
                        "remote": git["remote"] or (package.get("remote") if package else None),
                        "branch": git["branch"],
                        "commit": git["commit"] or (package.get("commit") if package else None),
                        "entryCount": git["entryCount"],
                        "issues": issues,
                        "isTopLevel": str(relative) == ".",
                        "capabilityDomains": domains,
                        "capabilityEvidence": domain_evidence,
                        "skillSHA256": sha256_file(physical_file),
                        "lifecycleSHA256": lifecycle_hash,
                        "updates": package.get("updates") if package and not git["repository"] else None,
                        "sourceDirty": git["dirty"],
                    }
                records_by_file[physical_key]["activePaths"].append(str(active_path))

    records = list(records_by_file.values())
    records_by_name: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        record["activePaths"] = sorted(set(record["activePaths"]))
        record["scope"] = infer_scope(record["activePaths"])
        records_by_name.setdefault(record["name"], []).append(record)
    for name, same_name_records in records_by_name.items():
        if len(same_name_records) > 1:
            for record in same_name_records:
                record["status"] = "UNKNOWN"
                record["issues"].append(f"Name collision: {name} has {len(same_name_records)} physical entries.")
        for record in same_name_records:
            add_governance(record, len(same_name_records))

    records.sort(key=lambda item: (item["name"], item["physicalPath"]))
    top_level = sum(record["isTopLevel"] for record in records)
    collision_groups = sum(len(group) > 1 for group in records_by_name.values())
    status_counts = {status: sum(record["status"] == status for record in records) for status in ("PASS", "BLOCKED", "UNKNOWN")}
    return {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "generator": GENERATOR,
        "platform": "linux",
        "roots": [str(root) for root in roots],
        "summary": {
            "total": len(records),
            "inventory": {
                "physicalEntries": len(records),
                "uniqueNames": len(records_by_name),
                "topLevelEntries": top_level,
                "nestedEntries": len(records) - top_level,
                "activationAliases": sum(max(0, len(record["activePaths"]) - 1) for record in records),
                "nameCollisionGroups": collision_groups,
                "sameNamePhysicalExtras": sum(max(0, len(group) - 1) for group in records_by_name.values()),
            },
            "status": status_counts,
            "brokenLinks": len(broken_links),
        },
        "brokenLinks": sorted(broken_links),
        "inventoryFingerprint": inventory_fingerprint(records),
        "skills": records,
    }


def registry_result(layout: HostLayout, roots: Iterable[Path] | None = None) -> dict[str, Any]:
    """Build a fresh Registry result without writing it."""
    registry = scan_skills(list(roots or [layout.activity_root]))
    return {"status": "PASS", "action": "REGISTRY_PREVIEW", "registryPath": str(layout.registry_path), "registry": registry, "mutations": 0}


def write_registry(layout: HostLayout, roots: Iterable[Path] | None = None) -> dict[str, Any]:
    """Publish canonical JSON and a JSON-compatible YAML mirror after explicit approval."""
    result = registry_result(layout, roots)
    registry = result["registry"]
    atomic_json(layout.registry_path, registry)  # JSON is the only canonical Registry authority.
    yaml_text = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"  # JSON is valid YAML 1.2.
    atomic_text(layout.registry_yaml_path, yaml_text)
    result.update({"action": "REGISTRY_WRITTEN", "yamlPath": str(layout.registry_yaml_path), "mutations": 2})
    return result


def capability_report(registry: dict[str, Any]) -> str:
    """Render inventory units and collisions without equating assets with UI rows."""
    inventory = registry["summary"]["inventory"]
    lines = [
        "# Skill Capability Report",
        "",
        f"Generated by `{registry['generator']}` at `{registry['generatedAt']}`.",
        "",
        f"- Physical entries: {inventory['physicalEntries']}",
        f"- Unique names: {inventory['uniqueNames']}",
        f"- Top-level entries: {inventory['topLevelEntries']}",
        f"- Nested entries: {inventory['nestedEntries']}",
        f"- Activation aliases: {inventory['activationAliases']}",
        f"- Name-collision groups: {inventory['nameCollisionGroups']}",
        "",
        "## Review-required names",
        "",
    ]
    review_names = sorted({record["name"] for record in registry["skills"] if record["governanceState"] == "REVIEW_REQUIRED"})
    lines.extend(f"- `{name}`" for name in review_names)
    if not review_names:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def governance_report(registry: dict[str, Any]) -> str:
    """Render evidence readiness while keeping quality, usage, and security unrated."""
    states: dict[str, int] = {}
    tiers: dict[str, int] = {}
    for record in registry["skills"]:
        states[record["governanceState"]] = states.get(record["governanceState"], 0) + 1
        tiers[record["evidenceTier"]] = tiers.get(record["evidenceTier"], 0) + 1
    lines = [
        "# Skill Governance Report",
        "",
        "Evidence readiness measures metadata and provenance completeness, not quality or safety.",
        "",
        "## Governance states",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in sorted(states.items()))
    lines.extend(["", "## Evidence tiers", ""])
    lines.extend(f"- {name}: {count}" for name, count in sorted(tiers.items()))
    lines.extend(["", "All quality, usage, security, and overall grades remain `UNKNOWN`/`UNRATED` without direct evidence."])
    return "\n".join(lines) + "\n"


def report_result(layout: HostLayout, apply: bool) -> dict[str, Any]:
    """Preview or publish the human inventory report from fresh live evidence."""
    registry = scan_skills([layout.activity_root])
    text = capability_report(registry)
    if apply:
        atomic_text(layout.capability_report_path, text)
    return {"status": "PASS", "action": "REPORT_WRITTEN" if apply else "REPORT_PREVIEW", "reportPath": str(layout.capability_report_path), "summary": registry["summary"], "mutations": 1 if apply else 0}


def governance_result(layout: HostLayout, apply: bool) -> dict[str, Any]:
    """Preview or publish governance after refreshing canonical Registry evidence."""
    registry = scan_skills([layout.activity_root])
    text = governance_report(registry)
    mutations = 0
    if apply:
        write_registry(layout, [layout.activity_root])  # Governance publication refreshes canonical evidence first.
        atomic_text(layout.capability_report_path, capability_report(registry))
        atomic_text(layout.governance_report_path, text)
        mutations = 4  # JSON, YAML, capability report, and governance report were published.
    return {"status": "PASS", "action": "GOVERNANCE_WRITTEN" if apply else "GOVERNANCE_PREVIEW", "reportPath": str(layout.governance_report_path), "summary": registry["summary"], "mutations": mutations}
