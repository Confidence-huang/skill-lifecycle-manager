#!/usr/bin/env bash
# Install the verified Python package as the user-level `skill` command without sudo.

set -euo pipefail  # Stop before partial publication when any required command fails.

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)  # Resolve the exact checked-out source.
uv_path=${UV_PATH:-"$HOME/.local/bin/uv"}  # The migration pins uv in the user executable directory.

if [[ $(uname -s) != "Linux" ]]; then
    printf 'BLOCKED: bootstrap requires Linux.\n' >&2  # Windows is historical input, not a runtime target.
    exit 1
fi
if [[ ! -x "$uv_path" ]]; then
    printf 'BLOCKED: uv is missing at %s.\n' "$uv_path" >&2  # Never fall back to global pip implicitly.
    exit 1
fi

"$uv_path" tool install --editable "$repo_root"  # Publish only this reviewed local Git checkout.
printf 'PASS: skill command installed from %s\n' "$repo_root"  # Report the immutable source boundary.
