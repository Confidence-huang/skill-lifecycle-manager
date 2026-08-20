"""Artifact-bound, preview-first v6 update plan primitives."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
import hashlib, json

@dataclass(frozen=True)
class UpdateCandidate:
    kind: str
    name: str
    current: str | None
    candidate: str | None
    compatibility: str = "UNKNOWN"
    action: str = "REQUIRE_APPROVAL"

def build_plan(candidates: list[UpdateCandidate], baseline_sha256: str | None = None) -> dict[str, Any]:
    payload = {"schema": "v6.update-plan", "createdAt": datetime.now(timezone.utc).isoformat(), "baselineSHA256": baseline_sha256, "candidates": [asdict(c) for c in candidates], "apply": {"requiresApproval": True, "requiresBackup": True, "requiresHealth": True, "rollbackOnFailure": True}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["planSHA256"] = hashlib.sha256(canonical).hexdigest()
    return payload
