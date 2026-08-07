---
name: skill-lifecycle-manager
description: Manage and govern the complete lifecycle of Codex and cross-agent Skills on Linux with a Python 3.12 and uv native CLI. Use to inventory or classify Skills, generate the canonical Registry, report evidence-backed governance, run explicit Static Runtime and Behavior verification, install or update one managed Skill transactionally, create or restore a link-aware capability backup, freeze a host-local stable baseline, or run zero-write health checks without PowerShell or Windows junction dependencies.
---

# Skill Lifecycle Manager

Manage Linux Skill assets as a small software supply chain. Keep physical inventory, Agent activity
entries, Registry evidence, runtime behavior, and human governance decisions separate.

The normal Ubuntu entrypoint is the Python 3.12 `skill` command installed from this repository with
`uv`. PowerShell scripts remain tracked only as a migration fallback and are not a runtime dependency.

## Operating rules

1. Load workspace and project rules before changing global Skill state.
2. Use Python 3.12 through the committed uv project and lock file.
3. Run `skill scan` or a preview before every lifecycle mutation.
4. Treat `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_RUN` literally.
5. Mutating commands preview by default and require `--apply`.
6. Never replace an existing source or activity entry. Resolve collisions separately.
7. Preserve one physical entity and expose SOURCE/HYBRID assets through Linux symbolic links.
8. Pin Git-backed state to a full commit SHA. A branch is only an update channel.
9. Update through remote inspection, fetch, ancestry proof, detached validation, and fast-forward.
10. Verify never repairs dependencies, edits a failing Skill, changes PATH, or retries credentials.
11. Backup records symbolic links without following them; restore requires an empty destination.
12. Health is always read-only and never fetches, installs, updates, deletes, grades, or routes.
13. Shadow generation reads a frozen Registry and exact Git commits; it may write only a new child
    below `data-root/shadows` after `--apply`, and it never creates approval or authoritative lock state.
14. Manager promotion requires one exact Schema-valid plan, previews by default, runs offline, and
    may inject failures only beneath a declared disposable REHEARSAL sandbox.

## Command entry

From the source repository:

```bash
uv sync --frozen
uv run skill --help
```

After the reviewed checkout passes acceptance, publish the user-level command:

```bash
./bootstrap.sh install
skill --help
skill --version
```

## Inventory, Registry, and reports

```bash
skill scan
skill registry
skill registry --apply
skill report --apply
skill governance --apply
```

The canonical host-local files are under
`$XDG_STATE_HOME/skill-lifecycle-manager` with fallback
`~/.local/state/skill-lifecycle-manager`. JSON is authoritative; YAML and Markdown are generated
views. Read [references/registry-schema.md](references/registry-schema.md) and
[references/governance.md](references/governance.md) before consuming their fields.

## Verification

```bash
skill verify --name bilibili-video-learning
skill verify --name bilibili-video-learning --apply
skill verify --target-skill /exact/candidate/root --apply
```

A legacy Skill without `skill.manifest.yaml` keeps Static verification while Runtime and Behavior
report `NOT_CONFIGURED`. A manifest uses the documented JSON-compatible YAML subset and argument
arrays. Read [references/verification-v2.md](references/verification-v2.md).

## Install and update

```bash
skill install /path/to/package --mode package
skill install /path/to/package --mode package --apply
skill install https://github.com/owner/repository.git --mode source --apply
skill install https://github.com/owner/repository.git --mode hybrid --skill-path skills/chosen --apply
skill update --name hop
skill update --name hop --apply
skill updates --name spec-kit
skill updates --all
```

Install publishes Registry evidence only after activation and required install probes pass. Update
never uses unchecked pull or history rewriting. `updates` is a separate zero-write PACKAGE release
check: it reads configured stable Git tags and optional CLI version evidence without fetching,
installing, upgrading, or requiring GitHub CLI. Read [references/operations.md](references/operations.md).

## Backup and restore

```bash
skill backup --path ~/.agents/skills --path ~/.local/share/skill-lifecycle-manager --apply
skill restore --backup-path /exact/backup --destination /empty/destination
skill restore --backup-path /exact/backup --destination /empty/destination --apply
```

Links are returned for explicit review and are never silently recreated on another host.

## Stable operation

```bash
skill stabilize
skill stabilize --apply
skill health
skill health --project-root /home/a/CodexProjects/Project_25-AI-Courses
```

An existing baseline is immutable. A deliberate migration rebaseline must add
`--archive-existing`, preserving the old bytes in baseline history first. Read
[references/stability.md](references/stability.md) and
[references/python-linux-v4.md](references/python-linux-v4.md).

## V5 Phase A contract candidate

The repository contains machine-valid V5 supply-chain Schemas and pure artifact-identity fixtures.
They are an isolated candidate, not an active Registry migration or approval system. Do not create
live lock, evidence, decision, or transaction state from these files until later phases pass their
separate stop gates. Read [references/supply-chain-v5.md](references/supply-chain-v5.md).

## V5 Phase B shadow candidate

```bash
skill shadow --registry-path /exact/skills-registry.json \
  --source-set /exact/shadow-source-set.json \
  --output-root /exact/data-root/shadows/run-id
skill shadow --registry-path /exact/skills-registry.json \
  --source-set /exact/shadow-source-set.json \
  --output-root /exact/data-root/shadows/run-id --apply
```

The source set must pin every Git repository, commit, canonical remote, Skill path, role, lifecycle
mode, activity suggestion, and scope. Dirty worktrees, name collisions, incomplete Git objects, LFS
pointers, submodules, or Registry identity loss are hard blocks. Output is non-authoritative evidence;
all lock candidates remain blocked until a later artifact-bound decision exists.

## V5 Phase C isolated behavior candidate

Phase C adds no public CLI and creates no live lock, decision, or transaction state. It provides two
candidate primitives for later reviewed wiring:

- `skill_lifecycle.contracts.require_current_approval` rejects artifact-mismatched, expired,
  revoked, superseded, or evidence-free approvals without writes.
- `skill_lifecycle.recovery` requires a zero-write inspection of one durable `IN_PROGRESS`
  transaction before explicit removal of its declared created paths beneath one isolated owner root.

Run the bounded fault matrix only in disposable roots:

```bash
uv run python -m unittest discover -s tests -p 'test_phase_c.py' -v
```

The suite injects a hard process exit before Registry publication, install/update final-write
failures, activity collisions, stale approvals, and unsafe recovery paths. Passing Phase C does not
authorize a real pilot; Phase D still requires a separately approved non-manager Skill, backup,
rollback, baseline, and after-scan plan. Read
[references/supply-chain-v5.md](references/supply-chain-v5.md).

## V5 Phase D reviewed pilot candidate

Phase D exposes four reviewed commands for one explicitly authorized non-manager pilot:

```bash
skill pilot-approve --manifest /exact/manifest.json --evidence /exact/evidence.json ...
skill pilot-activate --manifest /exact/manifest.json --evidence /exact/evidence.json ...
skill pilot-verify --transaction-id transaction-... --probe-plan /exact/probe-plan.json ...
skill pilot-rollback --transaction-id transaction-... --decision-id decision-... ...
```

Every command previews by default and requires `--apply` to write. Approval appends one exact
artifact/evidence-bound decision and publishes an ACTIVE lock revision plus immutable revision history. Activation persists exact
Registry/report preimages plus an `IN_PROGRESS` event before creating one symbolic link. Verification
runs one Schema-valid no-shell argument-array plan and retains bounded output. Rollback consumes only
the durable transaction, restores the four exact preimages, appends a superseding revocation, and
publishes an INACTIVE lock revision.

The first reviewed run is temporary: it must end inactive with the existing baseline unchanged and
formal health restored. These commands do not authorize persistent adoption, another Skill, a
manager self-pilot, rebaseline, source relocation, or direct hand-written state repair. Read
[docs/superpowers/plans/2026-08-07-v5-phase-d-oil-tone-pilot.md](docs/superpowers/plans/2026-08-07-v5-phase-d-oil-tone-pilot.md).

## V5 manager promotion candidate

```bash
skill --version
skill manager-upgrade --plan /exact/manager-promotion-plan.json
skill manager-upgrade --plan /exact/manager-promotion-plan.json --apply
skill manager-rehearse --plan /disposable/manager-promotion-plan.json \
  --failure-point after-cli-publication --apply
```

The plan pins both full commits, clean candidate source, offline carrier SHA256, formal source and
activity paths, absolute uv/CLI/tool/receipt paths, all five state preimage hashes, and the expected
inventory count. FORMAL apply captures recovery evidence before publication, performs the exact
source/CLI/Registry/baseline sequence, and accepts only structured identity plus health `PASS` with
`mutations: 0`. Any failure restores the old source, uv receipt/tool, four generated views, baseline
bytes and activity resolution before running old-manager health. Exact successful retries write
nothing. Read
[docs/superpowers/plans/2026-08-07-v5-formal-promotion-readiness-and-rollback.md](docs/superpowers/plans/2026-08-07-v5-formal-promotion-readiness-and-rollback.md).

## Completion checks

After any implementation or environment change:

1. Run `uv sync --frozen` and `uv run python -m unittest discover -s tests -v`.
2. Run the official `quick_validate.py` against this Skill root.
3. Build both wheel and source distribution with `uv build`.
4. Run preview/write pairs against isolated roots and prove preview state hashes do not change.
5. Regenerate live Registry, reports, backup, and explicit baseline.
6. Confirm the activity path is one symbolic link to this clean source repository.
7. Confirm the installed `skill` executable resolves to this package without `pwsh` in PATH.
8. Confirm Codex discovers `skill-lifecycle-manager` exactly once.
9. Review exact Git diff, stage only this repository's files, and commit the verified atomic change.
