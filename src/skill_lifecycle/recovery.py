"""
Inspect and apply bounded recovery for one interrupted V5 transaction fixture.

The caller supplies a durable transaction document plus one isolated owner root. Inspection first
proves that every declared created path is portable, remains below that root, and has no symbolic-link
ancestor. A separate explicit call then removes only those declared paths in reverse order.

Typical use:
    preview = inspect_recovery(transaction_path, temporary_host_root)
    result = apply_recovery(transaction_path, temporary_host_root)
"""

from __future__ import annotations  # Keep the Python 3.12 type contract visible.

import json  # Read one durable interrupted transaction document.
import shutil  # Remove only transaction-declared physical directories.
from pathlib import Path, PurePosixPath  # Keep portable record paths separate from host paths.
from typing import Any  # Describe structured recovery feedback returned to tests and future commands.

from skill_lifecycle.contracts import ContractBlocked, normalize_relative_path  # Reject absolute and escaping record paths.
from skill_lifecycle.paths import LifecycleBlocked  # Reuse the CLI-visible hard stop label.


# --- Read one interrupted remove-created-paths transaction ---
def read_recovery_transaction(transaction_path: Path) -> dict[str, Any]:
    """Return one narrowly supported transaction or block before inspecting any target path."""
    try:
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleBlocked(f"Recovery transaction is unreadable: {transaction_path}: {error}") from error
    if not isinstance(transaction, dict):  # A list or scalar cannot declare transaction ownership.
        raise LifecycleBlocked("Recovery transaction must be one JSON object.")
    if transaction.get("schemaVersion") != 1 or transaction.get("documentType") != "CAPABILITY_TRANSACTION":
        raise LifecycleBlocked("Recovery transaction identity is unsupported.")
    if transaction.get("finalStatus") != "IN_PROGRESS":  # Completed records are evidence, not recovery requests.
        raise LifecycleBlocked("Only an IN_PROGRESS transaction can enter recovery inspection.")
    if transaction.get("modifiedPaths") != []:  # Phase C cannot infer restoration of pre-existing content.
        raise LifecycleBlocked("Created-path recovery cannot process modified paths.")
    rollback = transaction.get("rollbackPlan")
    if not isinstance(rollback, dict) or rollback.get("type") != "REMOVE_CREATED_PATHS":
        raise LifecycleBlocked("Recovery requires a REMOVE_CREATED_PATHS rollback plan.")
    return transaction


# --- Resolve declared created paths without following links ---
def recovery_targets(transaction_path: Path, owner_root: Path) -> tuple[dict[str, Any], list[Path]]:
    """Return safe transaction-declared targets beneath one physical owner root."""
    transaction = read_recovery_transaction(transaction_path)  # Parse the durable evidence before paths.
    requested_owner = owner_root.expanduser()  # Inspect the supplied node before resolution can hide a link.
    if requested_owner.is_symlink():  # A link-backed owner could redirect all relative targets.
        raise LifecycleBlocked(f"Recovery owner must be a physical directory: {requested_owner}")
    owner = requested_owner.resolve(strict=True)  # Recovery never creates or guesses its owner root.
    if not owner.is_dir():  # Only a directory can own portable created-path records.
        raise LifecycleBlocked(f"Recovery owner must be a physical directory: {owner}")

    declared = transaction.get("createdPaths")
    if not isinstance(declared, list) or not declared:  # An empty plan cannot explain any residual path.
        raise LifecycleBlocked("Recovery transaction declares no created paths.")
    targets: list[Path] = []
    try:
        normalized = [normalize_relative_path(value) for value in declared]
    except ContractBlocked as error:
        raise LifecycleBlocked(str(error)) from error
    if len(set(normalized)) != len(normalized):  # Duplicate removal entries hide ordering mistakes.
        raise LifecycleBlocked("Recovery transaction contains duplicate created paths.")

    for relative in normalized:
        target = owner / PurePosixPath(relative)  # Normalization already rejected roots and parent traversal.
        current = owner
        for part in PurePosixPath(relative).parts[:-1]:
            current = current / part
            if current.is_symlink():  # Never enter a pre-existing link while finding a child target.
                raise LifecycleBlocked(f"Recovery path has a symbolic-link ancestor: {relative}")
        targets.append(target)
    return transaction, targets


# --- Preview recovery without deleting anything ---
def inspect_recovery(transaction_path: Path, owner_root: Path) -> dict[str, Any]:
    """Report exact residual paths and keep the interrupted fixture unchanged."""
    transaction, targets = recovery_targets(transaction_path, owner_root)
    return {
        "status": "PASS",
        "action": "RECOVERY_INSPECTED",
        "transactionID": transaction.get("transactionID"),
        "targets": [str(target) for target in targets],
        "present": [target.exists() or target.is_symlink() for target in targets],
        "mutations": 0,
    }


# --- Remove only transaction-declared paths after inspection ---
def apply_recovery(transaction_path: Path, owner_root: Path) -> dict[str, Any]:
    """Remove declared created paths in reverse order and retain the transaction evidence file."""
    transaction, targets = recovery_targets(transaction_path, owner_root)
    removed: list[str] = []
    for target in reversed(targets):  # Children recorded after parents disappear before their owners.
        if target.is_symlink() or target.is_file():
            target.unlink()  # Unlink the declared node without following a symbolic-link target.
        elif target.is_dir():
            shutil.rmtree(target)  # The durable transaction declares this complete directory as created.
        else:
            continue  # A previously absent target is already recovered and needs no mutation.
        removed.append(str(target))
    return {
        "status": "PASS",
        "action": "RECOVERY_APPLIED",
        "transactionID": transaction.get("transactionID"),
        "removed": removed,
        "mutations": len(removed),
    }
