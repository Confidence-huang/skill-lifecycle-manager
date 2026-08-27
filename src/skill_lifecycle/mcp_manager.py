"""Read-only MCP declaration discovery with fail-closed evidence semantics."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def discover_mcp() -> dict[str, Any]:
    candidates = [Path.home() / ".codex/config.toml", Path.home() / ".config/claude/claude_desktop_config.json", Path.home() / ".config/mcp.json"]
    found = [str(p) for p in candidates if p.is_file()]
    # TOML parsing is intentionally not inferred here; Codex config presence alone is not MCP registration evidence.
    return {"status": "NOT_CONFIGURED" if not found else "UNKNOWN", "configCandidates": found, "servers": [], "runtime": "NOT_RUN", "mutations": 0}
