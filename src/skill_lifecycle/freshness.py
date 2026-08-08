"""
Read configured PACKAGE release channels and return zero-write freshness evidence.

The command follows one visible path: select Registry records, inspect stable remote tags, inspect an
optional local CLI, compare semantic versions, and return structured feedback. It never fetches,
installs, upgrades, edits Registry state, or invokes GitHub CLI.
"""

from __future__ import annotations  # Keep Python 3.12 annotations available to callers and tests.

import json  # Read the canonical Registry without changing generated state.
import re  # Extract exact stable semantic versions from tags and CLI output.
import shutil  # Resolve an optional companion CLI through the reviewed process PATH.
import subprocess  # Run Git and CLI probes through argument arrays without a shell.
from pathlib import Path  # Preserve configured local or remote repository strings as literal arguments.
from typing import Any  # Describe Registry records and JSON feedback without hidden classes.

from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Reuse canonical paths and literal stop evidence.


STABLE_VERSION = re.compile(r"(?<![0-9])([0-9]+)\.([0-9]+)\.([0-9]+)(?![0-9A-Za-z.-])")  # Reject prerelease suffixes and partial digits.
GIT_TIMEOUT_SECONDS = 20  # Remote inspection stays bounded even when an endpoint is unavailable.
CLI_TIMEOUT_SECONDS = 10  # Version commands should finish quickly and never become a workflow runner.


# --- Read one canonical Registry snapshot ---
def read_registry(layout: HostLayout) -> dict[str, Any]:
    """Return canonical host evidence or stop before any network probe."""
    if not layout.registry_path.is_file():  # Freshness cannot guess which duplicate Skill is authoritative.
        raise LifecycleBlocked(f"Registry is missing: {layout.registry_path}")
    registry = json.loads(layout.registry_path.read_text(encoding="utf-8"))  # This read has no generated-file side effect.
    if not isinstance(registry.get("skills"), list):  # A malformed Registry cannot safely select command metadata.
        raise LifecycleBlocked("Registry skills collection is unreadable.")
    return registry


# --- Convert one stable version into comparable integers ---
def version_parts(version: str) -> tuple[int, int, int]:
    """Parse an already validated MAJOR.MINOR.PATCH value for ordering."""
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", version)
    if not match:  # Registry validation should prevent this, but canonical bytes remain an external boundary.
        raise LifecycleBlocked(f"Invalid stable version in Registry: {version}")
    return tuple(int(value) for value in match.groups())  # Integer ordering makes 0.16.0 newer than 0.9.0.


# --- Resolve the newest exact stable tag ---
def latest_tag(repository: str, tag_prefix: str) -> tuple[str | None, str | None]:
    """Read remote tag refs without fetching objects or modifying any repository."""
    try:
        completed = subprocess.run(
            ["git", "ls-remote", "--tags", repository],
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )  # The repository remains one literal argument even when it is a URL.
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"Git tag inspection failed: {error}"
    if completed.returncode:
        detail = completed.stderr.strip() or f"git exited {completed.returncode}"
        return None, f"Git tag inspection failed: {detail}"

    ref_pattern = re.compile(rf"^refs/tags/{re.escape(tag_prefix)}([0-9]+\.[0-9]+\.[0-9]+)$")
    versions: list[str] = []
    for line in completed.stdout.splitlines():
        fields = line.split(maxsplit=1)  # Git returns `<object> <ref>` for each remote tag.
        if len(fields) != 2:
            continue  # An incomplete line is not release evidence.
        match = ref_pattern.fullmatch(fields[1])
        if match:
            versions.append(match.group(1))  # Prerelease and unrelated tags never enter comparison.
    if not versions:
        return None, "No stable release tags matched the configured prefix."
    return max(versions, key=version_parts), None


# --- Inspect one optional companion CLI ---
def cli_version(cli: dict[str, Any] | None) -> tuple[str, str | None, str | None]:
    """Return CLI state, stable version, and a literal diagnostic without changing PATH."""
    if cli is None:
        return "NOT_CONFIGURED", None, None  # Some PACKAGE adapters track only upstream compatibility.
    command = cli["command"]  # Inventory validation guarantees a non-empty string.
    executable = shutil.which(command)
    if executable is None:
        return "NOT_INSTALLED", None, None  # Absence is expected evidence, not a failed update.
    try:
        completed = subprocess.run(
            [executable, *cli.get("arguments", [])],
            text=True,
            capture_output=True,
            check=False,
            timeout=CLI_TIMEOUT_SECONDS,
        )  # Version arguments cannot become shell syntax.
    except (OSError, subprocess.TimeoutExpired) as error:
        return "UNKNOWN", None, f"CLI version inspection failed: {error}"
    output = f"{completed.stdout}\n{completed.stderr}"
    match = STABLE_VERSION.search(output)
    if completed.returncode or not match:
        detail = f"exit {completed.returncode}" if completed.returncode else "no stable version in output"
        return "UNKNOWN", None, f"CLI version inspection failed: {detail}"
    return "INSTALLED", ".".join(match.groups()), None


# --- Compare one configured PACKAGE with its release channel ---
def check_record(record: dict[str, Any]) -> dict[str, Any]:
    """Build one self-contained freshness result from Registry, Git tags, and CLI evidence."""
    contract = record.get("updates")
    if not contract:
        return {
            "name": record.get("name"),
            "lifecycleMode": record.get("lifecycleMode"),
            "updateStatus": "NOT_CONFIGURED",
            "mutations": 0,
        }  # A named historical PACKAGE gets literal configuration feedback without network access.

    baseline = contract["baselineVersion"]  # The adapter records its last reviewed compatibility point.
    cli_status, installed, cli_issue = cli_version(contract.get("cli"))
    current = installed or baseline  # A missing CLI falls back to adapter compatibility, never an invented installation.
    current_source = "CLI" if installed else "ADAPTER_BASELINE"
    latest, tag_issue = latest_tag(contract["repository"], contract["tagPrefix"])
    issue = cli_issue or tag_issue
    if issue or latest is None or cli_status == "UNKNOWN":
        update_status = "UNKNOWN"
    elif version_parts(latest) > version_parts(current):
        update_status = "UPDATE_AVAILABLE"
    elif version_parts(latest) == version_parts(current):
        update_status = "CURRENT"
    else:
        update_status = "AHEAD"
    return {
        "name": record["name"],
        "lifecycleMode": record["lifecycleMode"],
        "strategy": contract["strategy"],
        "repository": contract["repository"],
        "baselineVersion": baseline,
        "cliCommand": contract.get("cli", {}).get("command") if contract.get("cli") else None,
        "cliStatus": cli_status,
        "installedVersion": installed,
        "currentVersion": current,
        "currentVersionSource": current_source,
        "latestVersion": latest,
        "updateStatus": update_status,
        "issue": issue,
        "mutations": 0,
    }  # One row carries enough context to explain every comparison decision locally.


# --- Check one named Skill or every configured PACKAGE ---
def check_updates(layout: HostLayout, name: str | None) -> dict[str, Any]:
    """Return aggregate PACKAGE freshness feedback without creating or changing any path."""
    registry = read_registry(layout)
    records = registry["skills"]
    if name is not None:
        selected = [record for record in records if record.get("name") == name]
        if len(selected) != 1:  # Equal names with multiple physical entries cannot choose one update channel safely.
            raise LifecycleBlocked(f"Expected one Registry record named {name}, found {len(selected)}.")
    else:
        selected = [record for record in records if record.get("updates")]  # Batch mode skips known unconfigured packages.

    updates = [check_record(record) for record in selected]
    states = ("CURRENT", "UPDATE_AVAILABLE", "AHEAD", "UNKNOWN", "NOT_CONFIGURED")
    summary = {state: sum(update["updateStatus"] == state for update in updates) for state in states}
    status = "UNKNOWN" if summary["UNKNOWN"] else "PASS"
    return {
        "status": status,
        "action": "UPDATES_CHECKED",
        "summary": {"checked": len(updates), **summary},
        "updates": updates,
        "mutations": 0,
    }  # The renderer receives evidence only; no writer exists in this module.
