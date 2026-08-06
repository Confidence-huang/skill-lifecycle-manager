"""
Linux host paths and durable-file primitives for Skill lifecycle commands.

Every command receives one HostLayout, so activity, source, state, cache, and recovery paths stay
visible and fixture-overridable. Atomic writers publish complete UTF-8 evidence without exposing a
half-written Registry or baseline.
"""

from __future__ import annotations  # Keep type annotations stable on Python 3.12.

import hashlib  # Produce the SHA256 identities shared by Registry, backup, and stability evidence.
import json  # Serialize canonical machine-readable lifecycle state.
import os  # Read the Linux XDG directory overrides.
from dataclasses import dataclass  # Keep the complete host layout immutable after CLI parsing.
from pathlib import Path  # Preserve POSIX path identity and symbolic-link behavior.
from typing import Any  # Describe structured JSON documents without hiding their fields.


class LifecycleBlocked(RuntimeError):
    """Stop when a command cannot prove its declared safety contract."""


@dataclass(frozen=True)
class HostLayout:
    """Directories owned by one Linux lifecycle-manager installation."""

    activity_root: Path  # Agent-visible Skill entries, normally ~/.agents/skills.
    data_root: Path  # Managed sources, package entities, and recovery backups.
    state_root: Path  # Canonical Registry, reports, verification, and baseline evidence.
    cache_root: Path  # Transaction-owned candidates and detached update worktrees.

    @classmethod
    def linux_default(cls) -> "HostLayout":
        """Resolve the documented XDG defaults without creating any directory."""
        home = Path.home()  # The current Ubuntu user owns every fallback path.
        data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
        state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
        cache_home = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
        return cls(
            activity_root=home / ".agents/skills",
            data_root=data_home / "skill-lifecycle-manager",
            state_root=state_home / "skill-lifecycle-manager",
            cache_root=cache_home / "skill-lifecycle-manager",
        )

    @property
    def registry_path(self) -> Path:
        """Return the only canonical host-local Registry path."""
        return self.state_root / "skills-registry.json"

    @property
    def registry_yaml_path(self) -> Path:
        """Return the generated readable mirror beside the canonical Registry."""
        return self.state_root / "skills-registry.yaml"

    @property
    def capability_report_path(self) -> Path:
        """Return the human-facing inventory and collision report path."""
        return self.state_root / "skill-capability-report.md"

    @property
    def governance_report_path(self) -> Path:
        """Return the evidence-readiness report path."""
        return self.state_root / "skill-governance-report.md"

    @property
    def baseline_path(self) -> Path:
        """Return the immutable current stable-use baseline path."""
        return self.state_root / "skill-stability-baseline.json"

    @property
    def verification_root(self) -> Path:
        """Return the directory for bounded targeted verification evidence."""
        return self.state_root / "verification"

    @property
    def v5_root(self) -> Path:
        """Return the audit-only V5 state root beside, but never replacing, Registry v1."""
        return self.state_root / "v5"

    @property
    def decision_journal_path(self) -> Path:
        """Return the append-only artifact approval journal path."""
        return self.v5_root / "decisions.jsonl"

    @property
    def capability_lock_path(self) -> Path:
        """Return the current host-local desired-state lock path."""
        return self.v5_root / "capability-lock.json"

    @property
    def capability_lock_history_root(self) -> Path:
        """Return the immutable per-revision lock history used by transaction audits."""
        return self.v5_root / "locks"

    @property
    def transaction_root(self) -> Path:
        """Return the parent that owns immutable event directories for applied transactions."""
        return self.v5_root / "transactions"


def sha256_file(path: Path) -> str:
    """Hash one physical file in bounded blocks and return uppercase evidence."""
    digest = hashlib.sha256()  # SHA256 matches the established PowerShell-era evidence contract.
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)  # One-megabyte blocks bound memory for large Skill assets.
    return digest.hexdigest().upper()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Publish one complete JSON document through a same-directory atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)  # The caller already authorized this state root.
    temporary = path.with_suffix(path.suffix + ".tmp")  # A sibling rename stays on one filesystem.
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(text, encoding="utf-8")  # UTF-8 prevents host-locale decoding drift.
    temporary.replace(path)  # Readers see the old complete file or the new complete file.


def atomic_text(path: Path, text: str) -> None:
    """Publish a complete UTF-8 generated view through an atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)  # Generated views share the authorized state root.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")  # Persist exactly one normalized UTF-8 document.
    temporary.replace(path)  # Never expose a partially generated Markdown or YAML mirror.


def atomic_bytes(path: Path, payload: bytes) -> None:
    """Restore one exact preimage through a same-directory atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)  # The transaction already declared this owner root.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)  # Byte restoration preserves the frozen Registry/report identity.
    temporary.replace(path)  # Readers see a complete old or restored file, never partial bytes.
