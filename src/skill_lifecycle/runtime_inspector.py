"""Bounded read-only runtime/toolchain inspection."""
from __future__ import annotations
import os, shutil, subprocess
from typing import Any

def inspect_runtime() -> dict[str, Any]:
    tools = {}
    for name, args in (("python3", ("--version",)), ("node", ("--version",)), ("go", ("version",)), ("rustc", ("--version",)), ("git", ("--version",)), ("uv", ("--version",))):
        path = shutil.which(name)
        item: dict[str, Any] = {"status": "WARN", "path": path, "version": None}
        if path:
            try:
                p = subprocess.run([path, *args], capture_output=True, text=True, timeout=5, check=False)
                lines = (p.stdout or p.stderr).strip().splitlines()
                item.update(status="PASS" if p.returncode == 0 else "WARN", version=lines[0] if lines else None)
            except (OSError, subprocess.TimeoutExpired):
                pass
        tools[name] = item
    return {"status": "PASS" if all(v["status"] == "PASS" for v in tools.values() if v["path"]) else "WARN", "tools": tools, "path": os.environ.get("PATH", "").split(os.pathsep), "mutations": 0}
