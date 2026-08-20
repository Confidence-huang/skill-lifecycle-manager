"""Read-only AI development environment health aggregation for the v6 rollout."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from skill_lifecycle.manager_identity import manager_identity
from skill_lifecycle.plugin_inventory import scan_plugins
from skill_lifecycle.runtime_inspector import inspect_runtime
from skill_lifecycle.migration_checker import inspect_migration
from skill_lifecycle.cache_manager import inspect_caches
from skill_lifecycle.stability import health
from skill_lifecycle.paths import HostLayout


def _tool(name: str, version_args: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Observe one executable without shell expansion or installation side effects."""
    path = shutil.which(name)
    if not path:
        return {"status": "WARN", "path": None, "version": None}
    try:
        args = version_args if version_args is not None else (("version",) if name == "go" else ("--version",))
        result = subprocess.run([path, *args], capture_output=True, text=True, timeout=5, check=False)
        text = (result.stdout or result.stderr).strip().splitlines()
        return {"status": "PASS" if result.returncode == 0 else "WARN", "path": path, "version": text[0] if text else None}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "WARN", "path": path, "version": None}


def doctor(host: HostLayout, project_root: Path | None = None, codex_command: str = "codex") -> dict[str, Any]:
    """Return a bounded, non-mutating report over current manager and tool evidence."""
    identity = manager_identity()
    skill_health = health(host, project_root)
    plugins = scan_plugins(codex_command, include_available=False)
    runtime = inspect_runtime()
    tools = runtime["tools"]
    migration = inspect_migration([Path.home() / ".local/share", Path.home() / ".config", Path.home() / ".cache", Path.home() / ".codex"])
    mcp = {"status": "NOT_CONFIGURED", "message": "No independent MCP registry is configured."}
    caches = inspect_caches([Path.home() / ".cache", Path.home() / ".codex/cache", Path.home() / ".local/share/skill-lifecycle-manager"])
    overall = "PASS"
    if skill_health.get("status") != "PASS" or any(item["status"] != "PASS" for item in tools.values() if item["path"]):
        overall = "WARN"
    return {
        "status": overall,
        "action": "DOCTOR_CHECKED",
        "manager": identity,
        "environment": runtime,
        "skills": skill_health,
        "plugins": plugins,
        "mcp": mcp,
        "migration": migration,
        "cache": caches,
        "update": {"status": "NOT_RUN", "available": None},
        "mutations": 0,
    }
