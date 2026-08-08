#!/usr/bin/env bash
# Install or explicitly promote the verified user-level `skill` command without sudo.

set -euo pipefail  # Stop before partial publication when any required command fails.

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)  # Resolve the exact checked-out source.
uv_path=${UV_PATH:-"$HOME/.local/bin/uv"}  # The migration pins uv in the user executable directory.

usage() {
    printf '%s\n' \
        'Usage: bootstrap.sh install' \
        '       bootstrap.sh upgrade --plan /absolute/manager-promotion.json [--apply]' >&2
}

if [[ $(uname -s) != "Linux" ]]; then
    printf 'BLOCKED: bootstrap requires Linux.\n' >&2  # Windows is historical input, not a runtime target.
    exit 1
fi
if [[ ! -x "$uv_path" ]]; then
    printf 'BLOCKED: uv is missing at %s.\n' "$uv_path" >&2  # Never fall back to global pip implicitly.
    exit 1
fi

mode=${1:-}
if [[ -z "$mode" ]]; then
    usage
    exit 1
fi
shift

if [[ -n $(git -C "$repo_root" status --porcelain=v1) ]]; then
    printf 'BLOCKED: manager source is dirty: %s\n' "$repo_root" >&2
    exit 1
fi

case "$mode" in
    install)
        if (( $# != 0 )); then
            usage
            exit 1
        fi
        "$uv_path" tool install --editable "$repo_root"  # Fresh installation has no existing receipt to replace.
        printf 'PASS: skill command installed from %s\n' "$repo_root"
        ;;
    upgrade)
        plan_path=
        apply_argument=()
        while (( $# > 0 )); do
            case "$1" in
                --plan)
                    if (( $# < 2 )); then
                        usage
                        exit 1
                    fi
                    plan_path=$2
                    shift 2
                    ;;
                --apply)
                    apply_argument=(--apply)
                    shift
                    ;;
                *)
                    usage
                    exit 1
                    ;;
            esac
        done
        if [[ -z "$plan_path" || "$plan_path" != /* || ! -f "$plan_path" ]]; then
            printf 'BLOCKED: upgrade requires one existing absolute --plan path.\n' >&2
            exit 1
        fi
        exec "$uv_path" run --no-dev --offline --frozen skill manager-upgrade \
            --plan "$plan_path" "${apply_argument[@]}"  # The Python transaction owns receipt backup and rollback.
        ;;
    *)
        usage
        exit 1
        ;;
esac
