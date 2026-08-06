"""
Build path-independent V5 artifact identities and canonical JSON records.

Phase A deliberately stays pure: callers supply already observed source facts and logical tree
entries, then receive normalized data or a deterministic SHA256 identity. The module does not scan
live Skills, read the Registry, make approval decisions, append journals, or mutate host state.

Typical use:
    tree_sha256 = compute_tree_sha256(tree_entries)
    identity = build_artifact_identity("GIT", source_url, commit, ".", tree_sha256)
    artifact_id = compute_artifact_id(identity)
"""

from __future__ import annotations  # Keep the Python 3.12 contract explicit for type readers.

import hashlib  # Produce lowercase SHA256 values required by the V5 Schema contract.
import json  # Serialize one canonical, whitespace-free JSON representation.
import re  # Reject malformed commits, hashes, and host-specific absolute paths.
import unicodedata  # Normalize equivalent Unicode path spellings before identity hashing.
from collections.abc import Iterable, Mapping  # Accept explicit read-only structured inputs.
from pathlib import PurePosixPath  # Express portable Skill-relative paths without touching disk.
from typing import Any  # Preserve the visible JSON field structure at the module boundary.


FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")  # V5 records resolved Git commits, never branch aliases.
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")  # Canonical hashes use one lowercase representation.
WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")  # Drive-qualified paths are host facts, not artifact facts.
TREE_TYPES = {"FILE", "SYMLINK"}  # Phase A models physical files and recorded link text only.


class ContractBlocked(ValueError):
    """Stop when supplied identity data cannot meet the frozen V5 contract."""


# --- Produce canonical JSON bytes ---
def canonical_json_bytes(payload: Any) -> bytes:
    """Encode one JSON-compatible value deterministically for hashing and JSON Lines records."""
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )  # Stable key order and separators remove host formatter differences from identity.
    except (TypeError, ValueError) as error:
        raise ContractBlocked(f"Value is not canonical JSON data: {error}") from error
    return text.encode("utf-8")  # UTF-8 is the single byte encoding used by the identity algorithm.


# --- Normalize one portable relative path ---
def normalize_relative_path(value: str, *, allow_root: bool = False) -> str:
    """Convert slash variants to one safe POSIX path while rejecting host or parent traversal."""
    if not isinstance(value, str) or not value:  # Empty paths cannot identify Skill content.
        raise ContractBlocked("Relative path must be a non-empty string.")
    if value != value.strip():  # Boundary whitespace is cross-host ambiguous and must not be hidden.
        raise ContractBlocked(f"Leading or trailing path whitespace is forbidden: {value!r}")
    normalized_text = unicodedata.normalize("NFC", value).replace("\\", "/")
    if normalized_text.startswith(("/", "//")) or WINDOWS_DRIVE.match(normalized_text):
        raise ContractBlocked(f"Absolute or drive-qualified path is forbidden: {value}")

    parts = [part for part in normalized_text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):  # Parent traversal could escape the declared Skill root.
        raise ContractBlocked(f"Parent traversal is forbidden: {value}")
    if any("\x00" in part for part in parts):  # NUL cannot be represented by real filesystem paths.
        raise ContractBlocked("Relative path contains a NUL character.")
    if not parts:
        if allow_root:
            return "."  # The repository root is the canonical Skill path for root Skills.
        raise ContractBlocked("A tree entry cannot identify the root directory itself.")
    return str(PurePosixPath(*parts))  # PurePosixPath never consults the current host filesystem.


# --- Normalize one logical artifact tree ---
def normalize_tree_entries(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate logical file/link facts and return a path-sorted, duplicate-free tree manifest."""
    normalized_entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for entry in entries:
        path = normalize_relative_path(entry.get("path", ""))  # Paths are the tree's stable keys.
        if path in seen_paths:  # Duplicate normalized names are ambiguous on every target host.
            raise ContractBlocked(f"Duplicate normalized tree path: {path}")
        seen_paths.add(path)

        entry_type = entry.get("type")
        if entry_type not in TREE_TYPES:  # Directories are implicit; unsupported nodes stay blocked.
            raise ContractBlocked(f"Unsupported tree entry type for {path}: {entry_type}")
        if entry_type == "FILE":
            size = entry.get("size")
            file_sha256 = entry.get("sha256")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ContractBlocked(f"File size must be a non-negative integer: {path}")
            if not isinstance(file_sha256, str) or not LOWER_SHA256.fullmatch(file_sha256):
                raise ContractBlocked(f"File SHA256 must be 64 lowercase hexadecimal characters: {path}")
            normalized_entries.append(
                {"path": path, "type": "FILE", "size": size, "sha256": file_sha256}
            )  # Only byte identity fields contribute to one file entry.
            continue

        link_target = entry.get("linkTarget")
        if not isinstance(link_target, str) or not link_target:
            raise ContractBlocked(f"Symbolic-link text is required: {path}")
        normalized_entries.append(
            {"path": path, "type": "SYMLINK", "linkTarget": unicodedata.normalize("NFC", link_target)}
        )  # Record link text without following it into another tree.
    return sorted(normalized_entries, key=lambda item: item["path"])


# --- Hash one logical artifact tree ---
def compute_tree_sha256(entries: Iterable[Mapping[str, Any]]) -> str:
    """Return the deterministic lowercase SHA256 of normalized logical tree entries."""
    normalized_entries = normalize_tree_entries(entries)  # Ordering and slash style converge here.
    return hashlib.sha256(canonical_json_bytes(normalized_entries)).hexdigest()


# --- Build immutable identity input ---
def build_artifact_identity(
    source_type: str,
    canonical_source: str,
    resolved_commit: str | None,
    skill_path: str,
    content_sha256: str,
) -> dict[str, Any]:
    """Create the exact host-independent object whose canonical bytes define an artifact."""
    if source_type not in {"GIT", "PACKAGE", "LOCAL"}:
        raise ContractBlocked(f"Unsupported source type: {source_type}")
    if not isinstance(canonical_source, str) or not canonical_source:
        raise ContractBlocked("Canonical source must be a non-empty string.")
    if canonical_source != canonical_source.strip():  # Identity must not silently rewrite source text.
        raise ContractBlocked("Canonical source cannot contain boundary whitespace.")
    if source_type == "GIT" and (
        not isinstance(resolved_commit, str) or not FULL_COMMIT.fullmatch(resolved_commit)
    ):
        raise ContractBlocked("Git artifacts require one resolved 40-character lowercase commit.")
    if source_type != "GIT" and resolved_commit is not None:
        raise ContractBlocked("Only Git artifacts may carry a resolved commit.")
    if not isinstance(content_sha256, str) or not LOWER_SHA256.fullmatch(content_sha256):
        raise ContractBlocked("Content SHA256 must be 64 lowercase hexadecimal characters.")
    return {
        "identityVersion": 1,
        "sourceType": source_type,
        "canonicalSource": canonical_source,
        "resolvedCommit": resolved_commit,
        "skillPath": normalize_relative_path(skill_path, allow_root=True),
        "contentPolicyVersion": "logical-tree-sha256-v1",
        "contentSHA256": content_sha256,
    }  # Timestamps, approvals, host IDs, and absolute paths are intentionally absent.


# --- Compute immutable artifact identity ---
def compute_artifact_id(identity: Mapping[str, Any]) -> str:
    """Hash one already normalized identity object and return the schema's artifactID format."""
    expected_keys = {
        "identityVersion",
        "sourceType",
        "canonicalSource",
        "resolvedCommit",
        "skillPath",
        "contentPolicyVersion",
        "contentSHA256",
    }
    if set(identity) != expected_keys:  # Extra host or governance fields must never enter identity.
        unexpected = sorted(set(identity).symmetric_difference(expected_keys))
        raise ContractBlocked(f"Artifact identity fields do not match the contract: {unexpected}")
    rebuilt = build_artifact_identity(
        identity["sourceType"],
        identity["canonicalSource"],
        identity["resolvedCommit"],
        identity["skillPath"],
        identity["contentSHA256"],
    )  # Rebuilding proves that precomputed callers did not bypass normalization or validation.
    return f"sha256:{hashlib.sha256(canonical_json_bytes(rebuilt)).hexdigest()}"


# --- Encode one append-only journal record ---
def encode_json_line(record: Mapping[str, Any]) -> str:
    """Return exactly one canonical JSON record terminated by one newline for append-only logs."""
    encoded = canonical_json_bytes(dict(record)).decode("utf-8")
    if "\n" in encoded or "\r" in encoded:  # Compact JSON must escape embedded user newlines.
        raise ContractBlocked("Canonical JSON Lines records cannot contain literal line breaks.")
    return encoded + "\n"
