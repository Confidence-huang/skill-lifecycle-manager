"""Read-only AI development environment health aggregation for the v6 rollout."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from skill_lifecycle.manager_identity import manager_identity
from skill_lifecycle.plugin_inventory import scan_plugins
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
    tools = {name: _tool(name) for name in ("git", "uv", "python3", "node", "go", "rustc")}
    migration = {"status": "UNKNOWN", "message": "v6 migration checker not yet enabled; no cleanup performed."}
    mcp = {"status": "NOT_CONFIGURED", "message": "No independent MCP registry is configured."}
    overall = "PASS"
    if skill_health.get("status") != "PASS" or any(item["status"] != "PASS" for item in tools.values() if item["path"]):
        overall = "WARN"
    return {
        "status": overall,
        "action": "DOCTOR_CHECKED",
        "manager": identity,
        "environment": tools,
        "skills": skill_health,
        "plugins": plugins,
        "mcp": mcp,
        "migration": migration,
        "update": {"status": "NOT_RUN", "available": None},
        "mutations": 0,
    }
