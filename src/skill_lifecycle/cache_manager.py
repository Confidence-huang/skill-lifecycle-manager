"""Read-only cache inventory; no cache is removed by this module."""
from __future__ import annotations
from pathlib import Path
from typing import Any

def inspect_caches(roots: list[Path]) -> dict[str, Any]:
    records = []
    for root in roots:
        if not root.exists():
            continue
        count = size = 0
        for path in root.rglob("*"):
            if any(part in {"node_modules", ".git", "attachments", "go-build"} for part in path.parts):
                continue
            if path.is_file() and not path.is_symlink():
                count += 1
                try: size += path.stat().st_size
                except OSError: pass
        records.append({"root": str(root), "files": count, "bytes": size, "reclaimCandidate": False})
    return {"status": "PASS", "roots": records, "mutations": 0}
