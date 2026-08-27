"""Classify Linux migration remnants without deleting or following links."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

WINDOWS = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|\\Users\\|AppData|powershell(?:\.exe)?$)", re.I)

def inspect_migration(roots: list[Path]) -> dict[str, Any]:
    findings = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in {"node_modules", ".git", "attachments", "go-build", "Trash"} for part in path.parts):
                continue
            raw = str(path)
            if WINDOWS.search(raw) or path.suffix.lower() in {".ps1", ".bat", ".cmd", ".exe", ".msi"}:
                findings.append({"path": raw, "classification": "WINDOWS_COMPATIBILITY_OR_REMAINDER", "action": "REVIEW_ONLY"})
            if path.is_symlink():
                findings.append({"path": raw, "classification": "SYMLINK", "target": str(path.readlink()), "action": "REVIEW_ONLY"})
    return {"status": "WARN" if findings else "PASS", "findings": findings[:1000], "total": len(findings), "mutations": 0}
