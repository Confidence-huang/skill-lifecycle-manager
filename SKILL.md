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

## Command entry

From the source repository:

```bash
uv sync --frozen
uv run skill --help
```

After the reviewed checkout passes acceptance, publish the user-level command:

```bash
./bootstrap.sh
skill --help
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
