"""Observe Codex plugin and marketplace state without changing either host.

The public interface hides Codex CLI invocation, JSON contract checks, local path topology, and
evidence classification behind one read-only scan. Installation metadata never becomes runtime or
connector-authentication evidence: those layers remain literal NOT_RUN, UNKNOWN, or NOT_CONFIGURED.
Call with ``scan_plugins("codex", include_available=False)``.
"""

from __future__ import annotations  # Keep annotations available on Python 3.12.

import json  # Decode only the documented machine-readable Codex command results.
import os  # Normalize dot segments without resolving symbolic links or junctions.
import shutil  # Resolve the selected Codex executable without modifying PATH.
import subprocess  # Invoke Codex with bounded argument arrays and no shell.
from datetime import datetime, timezone  # Timestamp completed observations in UTC.
from pathlib import Path  # Compare local plugin sources with marketplace roots cross-platform.
from typing import Any  # Describe the normalized JSON document returned to callers.

from skill_lifecycle.diagnostics import redact  # Prevent CLI failures from returning credential values.
from skill_lifecycle import __version__  # Keep evidence provenance aligned with the running manager.
from skill_lifecycle.paths import LifecycleBlocked  # Reuse the manager's fail-closed command gate.


GENERATOR = f"skill-lifecycle-manager/{__version__}"  # Bind plugin evidence to the running manager release.
COMMAND_TIMEOUT_SECONDS = 30  # Inventory commands must not become an unbounded Desktop health probe.
DIAGNOSTIC_LIMIT = 400  # Preserve useful failures without returning arbitrary subprocess output.


# --- Timestamp one completed observation ---
def utc_now() -> str:
    """Return one sortable timestamp for a completed plugin observation."""
    return datetime.now(timezone.utc).isoformat()


# --- Select the exact Codex CLI named by the user ---
def _resolve_codex(codex_command: str) -> str:
    """Resolve one exact CLI selection and stop before subprocess execution when absent."""
    if not isinstance(codex_command, str) or not codex_command.strip():
        raise LifecycleBlocked("Codex command must be a non-empty path or executable name.")
    resolved = shutil.which(codex_command)
    if not resolved:
        raise LifecycleBlocked(f"Codex command was not found: {codex_command}")
    return resolved


# --- Execute one bounded read-only Codex command ---
def _run(executable: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one bounded read-only Codex command and return its completed result."""
    command = [executable, *arguments]
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
            shell=False,
        )  # Argument arrays and shell=False keep paths and plugin names out of command syntax.
    except subprocess.TimeoutExpired as error:
        message = f"Codex command timed out after {COMMAND_TIMEOUT_SECONDS} seconds: {' '.join(arguments)}"
        raise LifecycleBlocked(message) from error  # A hung Desktop probe must not become a lifecycle wait.
    if completed.returncode != 0:
        diagnostic = redact((completed.stderr or completed.stdout or "no diagnostic output").strip(), DIAGNOSTIC_LIMIT)
        raise LifecycleBlocked(f"Codex command failed ({completed.returncode}): {diagnostic}")
    return completed


# --- Read one required text result ---
def _run_text(executable: str, arguments: list[str]) -> str:
    """Read one required bounded text result."""
    text = _run(executable, arguments).stdout.strip()
    if not text:
        raise LifecycleBlocked(f"Codex command returned no output: {' '.join(arguments)}")
    return text[:DIAGNOSTIC_LIMIT]


# --- Read one required JSON result ---
def _run_json(executable: str, arguments: list[str]) -> dict[str, Any]:
    """Read one required JSON object without tolerating human-output fallback."""
    text = _run(executable, arguments).stdout
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LifecycleBlocked(f"Codex command did not return valid JSON: {' '.join(arguments)}") from error
    if not isinstance(payload, dict):
        raise LifecycleBlocked(f"Codex command JSON root must be an object: {' '.join(arguments)}")
    return payload


# --- Require one documented result array ---
def _required_array(payload: dict[str, Any], field: str, command: str) -> list[Any]:
    """Require one documented top-level array before normalizing any records."""
    value = payload.get(field)
    if not isinstance(value, list):
        raise LifecycleBlocked(f"Codex {command} JSON field must be an array: {field}")
    return value


# --- Observe one local plugin source path ---
def _local_path_status(path_text: Any) -> tuple[str, Path | None, list[str]]:
    """Observe one local path without creating, traversing its contents, or repairing it."""
    if not isinstance(path_text, str) or not path_text.strip():
        return "UNKNOWN", None, ["Local source path is missing."]
    path = Path(path_text).expanduser()
    if not path.exists():
        return "UNKNOWN", path, ["Local plugin source path does not exist."]
    return "PASS", path, []


# --- Normalize one configured marketplace ---
def _normalize_marketplace(raw: Any) -> dict[str, Any]:
    """Normalize one configured marketplace and preserve incomplete local-root evidence."""
    if not isinstance(raw, dict):
        return {
            "name": None,
            "root": None,
            "marketplaceSource": None,
            "rootStatus": "UNKNOWN",
            "issues": ["Marketplace record is not an object."],
        }
    name = raw.get("name") if isinstance(raw.get("name"), str) else None
    root_text = raw.get("root") if isinstance(raw.get("root"), str) else None
    issues: list[str] = []
    if not name:
        issues.append("Marketplace name is missing.")
    if not root_text:
        root_status = "UNKNOWN"
        issues.append("Marketplace root is missing.")
    elif not Path(root_text).expanduser().exists():
        root_status = "UNKNOWN"
        issues.append("Marketplace root does not exist.")
    else:
        root_status = "PASS"
    return {
        "name": name,
        "root": root_text,
        "marketplaceSource": raw.get("marketplaceSource"),
        "rootStatus": root_status,
        "issues": issues,
    }


# --- Classify connector authentication evidence ---
def _authentication_status(auth_policy: Any) -> str:
    """Classify configuration only; never infer a live connector session."""
    if auth_policy is None:
        return "NOT_CONFIGURED"
    if isinstance(auth_policy, str) and auth_policy.upper() in {"NONE", "NOT_REQUIRED"}:
        return "NOT_CONFIGURED"
    return "UNKNOWN"


# --- Normalize one installed or available plugin ---
def _normalize_plugin(raw: Any, marketplaces: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Normalize one plugin while keeping installation, source, auth, and runtime evidence separate."""
    if not isinstance(raw, dict):
        return {
            "pluginId": None,
            "name": None,
            "marketplaceName": None,
            "version": None,
            "installed": None,
            "enabled": None,
            "source": None,
            "installPolicy": None,
            "authPolicy": None,
            "sourceStatus": "UNKNOWN",
            "marketplaceStatus": "UNKNOWN",
            "authenticationStatus": "NOT_CONFIGURED",
            "runtimeStatus": "NOT_RUN",
            "evidenceStatus": "UNKNOWN",
            "issues": ["Plugin record is not an object."],
        }

    issues: list[str] = []
    plugin_id = raw.get("pluginId") if isinstance(raw.get("pluginId"), str) else None
    name = raw.get("name") if isinstance(raw.get("name"), str) else None
    marketplace_name = raw.get("marketplaceName") if isinstance(raw.get("marketplaceName"), str) else None
    version = raw.get("version") if isinstance(raw.get("version"), str) else None
    for value, label in ((plugin_id, "Plugin ID"), (name, "Plugin name"), (marketplace_name, "Marketplace name"), (version, "Plugin version")):
        if not value:
            issues.append(f"{label} is missing.")
    installed = raw.get("installed") if isinstance(raw.get("installed"), bool) else None
    enabled = raw.get("enabled") if isinstance(raw.get("enabled"), bool) else None
    if installed is None:
        issues.append("Plugin installed state is missing.")
    if enabled is None:
        issues.append("Plugin enabled state is missing.")

    source = raw.get("source")
    source_status = "UNKNOWN"
    source_path: Path | None = None
    if not isinstance(source, dict):
        issues.append("Plugin source is not an object.")
    elif source.get("source") == "local":
        source_status, source_path, path_issues = _local_path_status(source.get("path"))
        issues.extend(path_issues)
    else:
        issues.append("Plugin source topology is not locally inspectable.")

    marketplace = marketplaces.get(marketplace_name) if marketplace_name else None
    if not marketplace:
        marketplace_status = "UNKNOWN"
        issues.append("Configured marketplace was not observed.")
    else:
        marketplace_status = marketplace["rootStatus"]
        root_text = marketplace.get("root")
        if marketplace_status != "PASS":
            issues.append("Configured marketplace root is not healthy.")
        elif source_path is not None and isinstance(root_text, str):
            source_absolute = Path(os.path.abspath(source_path))  # Normalize dots without resolving link targets.
            root_absolute = Path(os.path.abspath(Path(root_text).expanduser()))
            if not source_absolute.is_relative_to(root_absolute):
                marketplace_status = "UNKNOWN"
                issues.append("Local plugin source is outside the observed marketplace root.")

    return {
        "pluginId": plugin_id,
        "name": name,
        "marketplaceName": marketplace_name,
        "version": version,
        "installed": installed,
        "enabled": enabled,
        "source": source,
        "marketplaceSource": raw.get("marketplaceSource"),
        "installPolicy": raw.get("installPolicy"),
        "authPolicy": raw.get("authPolicy"),
        "sourceStatus": source_status,
        "marketplaceStatus": marketplace_status,
        "authenticationStatus": _authentication_status(raw.get("authPolicy")),
        "runtimeStatus": "NOT_RUN",
        "evidenceStatus": "PASS" if not issues else "UNKNOWN",
        "issues": issues,
    }


# --- Observe the complete Codex plugin inventory ---
def scan_plugins(codex_command: str = "codex", include_available: bool = False) -> dict[str, Any]:
    """Return normalized Codex plugin evidence through one zero-write interface."""
    executable = _resolve_codex(codex_command)
    version = _run_text(executable, ["--version"])
    list_arguments = ["plugin", "list"]
    if include_available:
        list_arguments.append("--available")
    list_arguments.append("--json")
    plugin_payload = _run_json(executable, list_arguments)
    marketplace_payload = _run_json(executable, ["plugin", "marketplace", "list", "--json"])

    installed_raw = _required_array(plugin_payload, "installed", "plugin list")
    available_raw = _required_array(plugin_payload, "available", "plugin list")
    marketplaces_raw = _required_array(marketplace_payload, "marketplaces", "plugin marketplace list")
    marketplace_records = [_normalize_marketplace(record) for record in marketplaces_raw]
    marketplace_index = {
        record["name"]: record for record in marketplace_records if isinstance(record.get("name"), str)
    }
    plugins = [_normalize_plugin(record, marketplace_index) for record in installed_raw]
    available_plugins = (
        [_normalize_plugin(record, marketplace_index) for record in available_raw] if include_available else []
    )
    observed = [*plugins, *available_plugins]
    evidence_counts = {
        status: sum(record["evidenceStatus"] == status for record in observed) for status in ("PASS", "UNKNOWN")
    }
    return {
        "status": "PASS",
        "action": "PLUGINS_SCANNED",
        "generatedAt": utc_now(),
        "generator": GENERATOR,
        "codexCommand": executable,
        "codexVersion": version,
        "summary": {
            "installed": len(plugins),
            "enabled": sum(record["enabled"] is True for record in plugins),
            "available": len(available_plugins),
            "marketplaces": len(marketplace_records),
            "evidence": evidence_counts,
        },
        "plugins": plugins,
        "availablePlugins": available_plugins,
        "marketplaces": marketplace_records,
        "runtimeEvidence": "NOT_RUN",
        "mutations": 0,
    }
