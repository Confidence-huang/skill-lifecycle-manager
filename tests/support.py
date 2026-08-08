"""Deterministic cross-platform fixtures shared by lifecycle command tests."""

from __future__ import annotations  # Keep helper annotations stable on Python 3.12.

import json  # Write the JSON-compatible YAML verification manifest.
import subprocess  # Create local Git repositories without shell interpolation.
from pathlib import Path  # Keep every test path inside TemporaryDirectory roots.

from skill_lifecycle.paths import HostLayout  # Give each test fully isolated lifecycle roots.


def layout(root: Path) -> HostLayout:
    """Create a host layout whose every mutation stays below one disposable directory."""
    return HostLayout(root / "activity", root / "data", root / "state", root / "cache")


def link_directory(host: HostLayout, target: Path, link: Path) -> Path:
    """Create the current host's activity primitive and return its path."""
    link.parent.mkdir(parents=True, exist_ok=True)
    host.platform.create_directory_link(target, link)
    return link


def create_skill(root: Path, name: str, body: str = "# Test Skill\n") -> Path:
    """Create one valid UTF-8 Skill entry and return its physical directory."""
    root.mkdir(parents=True, exist_ok=True)
    text = f"---\nname: {name}\ndescription: fixture {name}\n---\n\n{body}"
    (root / "SKILL.md").write_text(text, encoding="utf-8")
    return root


def write_lifecycle_record(root: Path, record: dict) -> Path:
    """Publish one JSON PACKAGE provenance record beside a fixture Skill."""
    path = root / ".skill-lifecycle.json"  # PACKAGE provenance travels with the copied Skill entity.
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")  # JSON stays directly readable by the dependency-free runtime.
    return path  # Tests use the exact path for hash and preservation assertions.


def write_manifest(root: Path, runtime: dict | None = None, behavior: dict | None = None, required: list[str] | None = None) -> Path:
    """Write one dependency-free manifest from explicit probe dictionaries."""
    name = next(line.split(":", 1)[1].strip() for line in (root / "SKILL.md").read_text(encoding="utf-8").splitlines() if line.startswith("name:"))
    payload = {"schemaVersion": 1, "name": name, "requiredLayers": required or ["static"]}
    if runtime is not None:
        payload["runtime"] = runtime
    if behavior is not None:
        payload["behavior"] = behavior
    path = root / "skill.manifest.yaml"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def git(*arguments: str, cwd: Path | None = None) -> str:
    """Run one local Git fixture command and return stdout after proving success."""
    completed = subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed.stdout.strip()


def create_git_skill(root: Path, name: str, remote: str | None = None) -> Path:
    """Create one clean committed Skill repository with an optional origin URL."""
    create_skill(root, name)
    git("init", "-b", "main", cwd=root)
    git("config", "user.name", "Fixture", cwd=root)
    git("config", "user.email", "fixture@example.invalid", cwd=root)
    git("add", "--", "SKILL.md", cwd=root)
    git("commit", "-m", "initial", cwd=root)
    if remote:
        git("remote", "add", "origin", remote, cwd=root)
    return root
