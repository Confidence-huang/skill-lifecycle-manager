#!/usr/bin/env python3
"""Run the exact offline manager promotion fault matrix in disposable roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
RAN_TESTS = re.compile(r"Ran (\d+) tests?")


def run(command: list[str], *, cwd: Path) -> str:
    """Return stdout from one required local command without invoking a shell."""
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Command failed ({command[0]}): {detail}")
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    """Hash the exact offline carrier in bounded blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def parser() -> argparse.ArgumentParser:
    """Require every immutable identity used by the rehearsal."""
    result = argparse.ArgumentParser(description="Rehearse V5 manager self-promotion without live mutations")
    result.add_argument("--old-commit", required=True)
    result.add_argument("--new-commit", required=True)
    result.add_argument("--carrier", type=Path, required=True)
    result.add_argument("--uv", type=Path, required=True)
    return result


def main(arguments: list[str] | None = None) -> int:
    """Validate exact inputs, execute the real integration matrix, and report JSON evidence."""
    parsed = parser().parse_args(arguments)
    repository = Path(__file__).resolve().parents[1]
    carrier = parsed.carrier.expanduser().resolve(strict=True)
    uv_path = parsed.uv.expanduser().resolve(strict=True)
    try:
        if not FULL_COMMIT.fullmatch(parsed.old_commit) or not FULL_COMMIT.fullmatch(parsed.new_commit):
            raise RuntimeError("Both rehearsal commits must be full lowercase Git identities.")
        if not os.access(uv_path, os.X_OK):
            raise RuntimeError(f"uv is not executable: {uv_path}")
        head = run(["git", "rev-parse", "HEAD"], cwd=repository)
        if head != parsed.new_commit:
            raise RuntimeError(f"Repository HEAD {head} does not match new commit {parsed.new_commit}.")
        if run(["git", "status", "--porcelain=v1"], cwd=repository):
            raise RuntimeError(f"Repository is dirty: {repository}")
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", parsed.old_commit, parsed.new_commit],
            cwd=repository,
            capture_output=True,
            check=False,
        )
        if ancestry.returncode:
            raise RuntimeError("New manager commit is not a descendant of the frozen old commit.")
        heads = run(["git", "bundle", "list-heads", str(carrier)], cwd=repository).splitlines()
        if not any(line.split(maxsplit=1)[0] == parsed.new_commit for line in heads if line.strip()):
            raise RuntimeError("Carrier does not publish the exact new manager commit.")

        environment = {
            **os.environ,
            "SLM_REHEARSAL_OLD_COMMIT": parsed.old_commit,
            "SLM_REHEARSAL_NEW_COMMIT": parsed.new_commit,
            "SLM_REHEARSAL_CARRIER": str(carrier),
            "SLM_REHEARSAL_UV": str(uv_path),
        }
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_manager_promotion.py",
                "-v",
            ],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        if completed.returncode:
            raise RuntimeError(f"Promotion rehearsal failed:\n{completed.stdout}\n{completed.stderr}")
        match = RAN_TESTS.search(completed.stderr)
        test_count = int(match.group(1)) if match else None
        result = {
            "status": "PASS",
            "action": "MANAGER_PROMOTION_REHEARSED",
            "oldCommit": parsed.old_commit,
            "newCommit": parsed.new_commit,
            "carrierPath": str(carrier),
            "carrierSHA256": sha256(carrier),
            "uvPath": str(uv_path),
            "testCount": test_count,
            "failurePoints": [
                "before-source-publication",
                "after-cli-publication",
                "after-registry-regeneration",
                "after-baseline-archival",
            ],
            "successPromotion": True,
            "formalMutations": 0,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
