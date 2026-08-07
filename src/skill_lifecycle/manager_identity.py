"""Deterministic package and Git identity for the running lifecycle manager."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from skill_lifecycle import __version__
from skill_lifecycle.paths import LifecycleBlocked


def _git(repository: Path, *arguments: str) -> str:
    """Return one required local Git fact without invoking a shell or remote."""
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise LifecycleBlocked(f"Manager Git identity failed: {detail}")
    return completed.stdout.strip()


def manager_repository(source_root: Path | None = None) -> Path:
    """Resolve the exact Git top-level that owns this package or an explicit source."""
    package_root = Path(source_root).expanduser() if source_root else Path(__file__).resolve().parents[2]
    top_level = _git(package_root, "rev-parse", "--show-toplevel")
    return Path(top_level).resolve(strict=True)


def manager_identity(source_root: Path | None = None) -> dict[str, Any]:
    """Report stable release identity plus host observations without writing state."""
    repository = manager_repository(source_root)
    commit = _git(repository, "rev-parse", "HEAD")
    tree = _git(repository, "rev-parse", "HEAD^{tree}")
    clean = _git(repository, "status", "--porcelain=v1") == ""
    immutable = {
        "managerVersion": __version__,
        "sourceCommit": commit,
        "sourceTree": tree,
    }
    canonical = json.dumps(immutable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "status": "PASS",
        "action": "MANAGER_IDENTITY",
        "product": "skill-lifecycle-manager",
        **immutable,
        "sourcePath": str(repository),
        "sourceClean": clean,
        "identitySHA256": hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper(),
        "mutations": 0,
    }
