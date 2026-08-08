"""
Layered Static, Runtime, and Behavior verification for one explicit Skill.

The verifier reads one target and optional JSON-compatible YAML manifest, resolves only documented
placeholders, executes argument arrays without a shell, and returns bounded redacted evidence. It
never installs dependencies, repairs a failure, changes PATH, fetches credentials, or touches an
unrelated Skill.
"""

from __future__ import annotations  # Keep type annotations stable on Python 3.12.

import json  # Parse the dependency-free manifest subset and structured probe output.
import os  # Read already-present environment placeholders without changing them.
import re  # Redact common credential-bearing diagnostic shapes.
import shutil  # Resolve named executables through the current PATH.
import subprocess  # Run declared probes through explicit argument arrays.
import sys  # Resolve the current cross-platform Python interpreter explicitly.
import tempfile  # Give each applied verification one disposable work root.
from datetime import datetime, timezone  # Name persisted reports uniquely in UTC.
from pathlib import Path  # Enforce target-local executable and placeholder paths.
from typing import Any  # Describe manifest and evidence dictionaries explicitly.

from skill_lifecycle.inventory import read_skill  # Reuse canonical Static identity parsing.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked, atomic_json  # Share stop and persistence rules.


SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|cookie|authorization|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)"
)  # Persist the key name while removing its sensitive value.


def redact(text: str, limit: int = 4000) -> str:
    """Bound diagnostics and replace common credential values before display or persistence."""
    bounded = text[:limit]  # Probe output is evidence, not an unlimited log transport.
    return SECRET_PATTERN.sub(r"\1\2[REDACTED]", bounded)


def read_manifest(target: Path) -> dict[str, Any] | None:
    """Read the optional JSON-compatible YAML manifest without adding a machine-wide parser."""
    manifest_path = target / "skill.manifest.yaml"
    if not manifest_path.is_file():
        return None  # Legacy Skills remain compatible and explicit as NOT_CONFIGURED.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1:
        raise LifecycleBlocked(f"Unsupported verification manifest schema: {manifest_path}")
    if manifest.get("name") and manifest["name"] != read_skill(target / "SKILL.md")[0]:
        raise LifecycleBlocked("Verification manifest name does not match SKILL.md.")
    return manifest


def expand_value(value: str, target: Path, temporary: Path) -> tuple[str | None, str | None]:
    """Resolve one documented placeholder and report missing environment evidence explicitly."""
    expanded = (
        value.replace("{skillRoot}", str(target))
        .replace("{tempRoot}", str(temporary))
        .replace("{python}", sys.executable)
    )
    for variable in re.findall(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}", expanded):
        if variable not in os.environ:
            return None, f"Environment variable is missing: {variable}"
        expanded = expanded.replace(f"{{env:{variable}}}", os.environ[variable])
    if re.search(r"\{[A-Za-z][A-Za-z0-9_:.-]*\}", expanded):
        return None, f"Unsupported placeholder in value: {value}"
    return expanded, None


def executable_path(command: str, target: Path) -> Path | None:
    """Resolve a named executable or prove a relative executable stays inside the Skill root."""
    command_path = Path(command)
    if command_path.is_absolute():
        if not command_path.is_file() or not os.access(command_path, os.X_OK):
            raise LifecycleBlocked(f"Probe executable is not runnable: {command_path}")
        return command_path  # Preserve virtual-environment symlink semantics instead of collapsing to system Python.
    if command_path.parent != Path("."):
        resolved = (target / command_path).resolve(strict=True)
        if resolved != target and target not in resolved.parents:
            raise LifecycleBlocked(f"Relative probe executable escapes the Skill root: {resolved}")
        return resolved
    resolved_text = shutil.which(command)
    return Path(resolved_text).resolve() if resolved_text else None


def expectation_status(probe: dict[str, Any], completed: subprocess.CompletedProcess[str]) -> tuple[str, list[str]]:
    """Compare observed exit and JSON fields with the declared bounded expectation."""
    expectation = probe.get("expect", {})
    issues: list[str] = []
    expected_exit = expectation.get("exitCode", 0)
    if completed.returncode != expected_exit:
        issues.append(f"Expected exit {expected_exit}, observed {completed.returncode}.")
    expected_json = expectation.get("stdoutJsonEquals")
    if expected_json is not None:
        try:
            observed_json = json.loads(completed.stdout)
        except json.JSONDecodeError:
            issues.append("Probe stdout is not valid JSON.")
        else:
            for key, value in expected_json.items():
                if observed_json.get(key) != value:
                    issues.append(f"stdout JSON field {key!r} did not match the expected value.")
    return ("PASS" if not issues else "BLOCKED"), issues


def run_probe(layer: str, probe: dict[str, Any], target: Path, temporary: Path) -> dict[str, Any]:
    """Execute one manifest layer and return bounded structured evidence."""
    command, command_gap = expand_value(str(probe.get("command", "")), target, temporary)
    if command_gap or not command:
        return {"layer": layer, "status": "UNKNOWN", "issues": [command_gap or "Probe command is missing."]}
    arguments: list[str] = []
    for raw_argument in probe.get("arguments", []):
        argument, gap = expand_value(str(raw_argument), target, temporary)
        if gap or argument is None:
            return {"layer": layer, "status": "UNKNOWN", "issues": [gap or "Probe argument is invalid."]}
        arguments.append(argument)
    executable = executable_path(command, target)
    if not executable:
        return {"layer": layer, "status": "UNKNOWN", "issues": [f"Executable is missing: {command}"]}
    timeout = int(probe.get("timeoutSeconds", 60))
    if timeout < 1 or timeout > 900:
        raise LifecycleBlocked(f"Probe timeout is outside 1..900 seconds: {timeout}")
    try:
        completed = subprocess.run(
            [str(executable), *arguments],
            cwd=target,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )  # shell=False is the default and preserves the declared argument boundary.
    except subprocess.TimeoutExpired as error:
        return {"layer": layer, "status": "BLOCKED", "issues": [f"Probe timed out after {timeout} seconds."], "stdout": redact(error.stdout or ""), "stderr": redact(error.stderr or "")}
    status, issues = expectation_status(probe, completed)
    return {
        "layer": layer,
        "status": status,
        "issues": issues,
        "command": str(executable),
        "arguments": arguments,
        "exitCode": completed.returncode,
        "stdout": redact(completed.stdout),
        "stderr": redact(completed.stderr),
    }


def verify_target(layout: HostLayout, target: Path, apply: bool, install_only: bool = False) -> dict[str, Any]:
    """Preview Static identity or run the target's declared verification layers."""
    physical = Path(target).expanduser().resolve(strict=True)
    skill_file = physical / "SKILL.md"
    if not skill_file.is_file():
        raise LifecycleBlocked(f"Skill entry is missing: {skill_file}")
    name, description, static_issues = read_skill(skill_file)
    manifest = read_manifest(physical)
    static_status = "PASS" if not static_issues else "UNKNOWN"
    layers: list[dict[str, Any]] = [{"layer": "static", "status": static_status, "issues": static_issues}]
    if manifest is None:
        layers.extend([
            {"layer": "runtime", "status": "NOT_CONFIGURED", "issues": []},
            {"layer": "behavior", "status": "NOT_CONFIGURED", "issues": []},
        ])
        return {"status": "PASS" if static_status == "PASS" else "UNKNOWN", "action": "VERIFICATION_PREVIEW" if not apply else "VERIFIED", "name": name, "target": str(physical), "description": description, "layers": layers, "mutations": 0}

    required = manifest.get("requiredLayers", ["static"])
    if not apply:
        for layer in ("runtime", "behavior"):
            configured = isinstance(manifest.get(layer), dict)
            layers.append({"layer": layer, "status": "NOT_RUN" if configured else "NOT_CONFIGURED", "issues": []})
        return {"status": "PASS" if static_status == "PASS" else "UNKNOWN", "action": "VERIFICATION_PREVIEW", "name": name, "target": str(physical), "layers": layers, "mutations": 0}

    layout.cache_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verify-", dir=layout.cache_root) as temporary_text:
        temporary = Path(temporary_text)
        for layer in ("runtime", "behavior"):
            probe = manifest.get(layer)
            if not isinstance(probe, dict):
                layers.append({"layer": layer, "status": "NOT_CONFIGURED", "issues": []})
                continue
            if install_only and not probe.get("runOnInstall", False):
                layers.append({"layer": layer, "status": "NOT_RUN", "issues": []})
                continue
            layers.append(run_probe(layer, probe, physical, temporary))

    required_statuses = [entry["status"] for entry in layers if entry["layer"] in required]
    if "BLOCKED" in required_statuses:
        overall = "BLOCKED"
    elif any(status in {"UNKNOWN", "NOT_CONFIGURED"} for status in required_statuses):
        overall = "UNKNOWN"
    else:
        overall = "PASS"
    report = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "name": name,
        "target": str(physical),
        "layers": layers,
        "autoRepair": False,
    }
    layout.verification_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = layout.verification_root / f"{name}-{stamp}.json"
    atomic_json(report_path, report)
    return {**report, "action": "VERIFIED", "reportPath": str(report_path), "mutations": 1}
