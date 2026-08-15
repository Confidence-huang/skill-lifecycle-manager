---
name: skill-lifecycle-manager
description: Manage and govern Codex Skills and plugin evidence on Windows and Linux with a Python 3.12 and uv CLI. Use to inventory or classify Skills, observe plugins and marketplaces without writes, generate the canonical Registry, run daily scan-only Guardian checks, publish update and compatibility reports, require exact human approval before source updates, verify Skills, install or update Skills transactionally, back up or restore capabilities, freeze a stable baseline, or run zero-write health checks.
---

# Skill Lifecycle Manager

Manage Skill assets as a small software supply chain. Keep desired approvals, physical inventory,
activity entries, observed Registry state, verification evidence, and recovery material separate.

## Operating rules

1. Load workspace and project rules before changing Skill state.
2. Use Python 3.12 through the committed uv project and lock file.
   Run repository scripts as `uv run python ...`; never create or require a system `python` alias.
3. Run the matching preview before every lifecycle mutation.
4. Treat `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_RUN` literally.
5. Mutating commands require `--apply`; never add it unless the user authorized that exact change.
6. Never replace an existing source or activity entry. Resolve collisions separately.
7. Keep one physical SOURCE/HYBRID entity. Linux activates it with a symbolic link; Windows uses a
   directory junction through the platform adapter.
8. Pin Git-backed state to a full commit. A branch is only an update channel.
9. Verify never repairs dependencies, edits a failing Skill, changes PATH, or retries credentials.
10. Backup records filesystem links without following them; restore requires an empty destination.
11. Health is read-only and never fetches, installs, updates, deletes, grades, or routes.
12. Treat Registry and baselines as host-local evidence; regenerate them after an OS migration.
13. On Windows, do not run Phase D pilot or manager-promotion commands. The CLI blocks them until a
    Windows-native rollback rehearsal is implemented and verified.
14. Guardian scheduling runs only `guardian scan --apply`; no policy tier authorizes unattended
    install, update, activation, project-log editing, or dependency repair.
15. Compatibility remains `UNKNOWN` unless a declared bounded probe supplies direct evidence.
16. Plugin installation and enabled metadata never prove connector authorization, runtime injection,
    or representative behavior; keep those evidence layers `UNKNOWN`, `NOT_CONFIGURED`, or `NOT_RUN`.
17. PACKAGE mutation is Linux-only and fail-closed. Require a validated `uv-tool-git` contract,
    exact baseline/candidate commits, Guardian approval, a verified snapshot, and a runnable health
    check; never substitute a moving branch, `latest`, install script, or system-level side effect.

## Command entry

From the source repository:

```text
uv sync --frozen
uv run skill --help
```

Install the reviewed checkout with `./bootstrap.sh install` on Linux or `.\bootstrap.ps1 install` in
Windows PowerShell.

## Inventory and governance

```text
skill scan
skill registry
skill registry --apply
skill report --apply
skill governance --apply
```

JSON is the canonical Registry. YAML and Markdown are generated views. Read
[references/registry-schema.md](references/registry-schema.md) and
[references/governance.md](references/governance.md) before consuming their fields.

## Verification

```text
skill verify --name NAME
skill verify --name NAME --apply
skill verify --target-skill PATH --apply
```

A legacy Skill without `skill.manifest.yaml` keeps Static verification while Runtime and Behavior
report `NOT_CONFIGURED`. Manifests use a JSON-compatible YAML subset, argument arrays, and the
portable `{python}` placeholder. Read [references/verification-v2.md](references/verification-v2.md).

## Plugin evidence

```text
skill plugins
skill plugins --available
skill plugins --codex-command /exact/path/to/codex
```

Plugin observation is read-only and separate from the Skill Registry. It records Codex CLI identity,
installed/enabled metadata, marketplace identity and local path topology while leaving connector
authentication and runtime behavior unclaimed. Read
[references/plugin-governance.md](references/plugin-governance.md) before consuming these fields.

## Install, update, backup, and restore

```text
skill install SOURCE --mode package
skill install SOURCE --mode source --apply
skill install SOURCE --mode hybrid --skill-path skills/NAME --apply
skill package-configure --name NAME --contract CONTRACT.json
skill package-configure --name NAME --contract CONTRACT.json --apply
skill update --name NAME
skill update --name NAME --approval APPROVAL.json --evaluated-at TIMESTAMP --apply
skill updates --name NAME
skill backup --path PATH --apply
skill restore --backup-path BACKUP --destination EMPTY_PATH --apply
```

Installation publishes Registry evidence only after required probes pass. Source update never uses
an unchecked pull or history rewrite. A PACKAGE update uses its declared adapter, durable lock,
verified preimages, exact Git commit, smoke checks, and automatic rollback before publishing
`COMMITTED`. Restore returns link records for review instead of silently recreating machine-specific
topology. Read [references/operations.md](references/operations.md).

## Daily Guardian

```text
skill guardian policy --file /exact/guardian-policy.json
skill guardian policy --file /exact/guardian-policy.json --apply
skill guardian scan
skill guardian scan --apply
skill guardian schedule --time 03:00
skill guardian schedule --time 03:00 --apply
```

The Guardian consumes the existing canonical Registry; it does not create a second Registry. A
missing per-Skill rule uses `UNKNOWN` risk plus `REQUIRE_APPROVAL`. Scheduled scans may write only
Guardian JSON/Markdown evidence. Publish a report-bound credential with
`skill guardian approve ... --apply`, then pass that file and an exact timezone-aware evaluation
time to `skill update ... --apply`. Read [references/guardian.md](references/guardian.md) before
enabling a schedule or approving an update.

## Stable operation

```text
skill stabilize
skill stabilize --apply
skill health
skill health --project-root PROJECT_PATH
```

An existing baseline is immutable. A deliberate rebaseline uses `--archive-existing` and preserves
the old bytes first. Read [references/stability.md](references/stability.md).

## V5 supply-chain controls

The `schemas/` directory and `skill_lifecycle.contracts` implement artifact identity, desired locks,
approval decisions, evidence, and transaction journals. `skill shadow` writes only isolated,
non-authoritative output. Read [references/supply-chain-v5.md](references/supply-chain-v5.md) before
extending these contracts.

Linux additionally exposes reviewed Phase D pilot and exact offline manager-promotion commands.
These operations require separately approved plans and remain outside Windows support.

## Completion checks

After implementation or environment changes:

1. Run `uv sync --frozen` and the complete unittest suite.
2. Run the official Skill `quick_validate.py` against this root.
3. Run `uv build` and inspect the wheel and source distribution.
4. Exercise preview/write pairs only against isolated roots.
5. Review the exact diff and run credential/private-path scans before publishing.
6. Require both Ubuntu and Windows GitHub Actions jobs for cross-platform changes.
