# Python Linux-native v4 migration contract

This document freezes the cutover boundary before implementation. The migration keeps the public
Skill name `skill-lifecycle-manager`, the canonical Registry schema, the preview/apply safety model,
and the established rollback evidence. It replaces PowerShell as the normal Ubuntu runtime with a
Python 3.12 CLI managed by `uv`.

## Observed problem

Ubuntu currently exposes two independent products:

- `skill-lifecycle-manager`, whose entrypoint and implementation still require PowerShell 7;
- `linux-skill-lifecycle`, a Python MVP with a different name, state root, Registry, and partial
  command set.

This duplicates identity and governance state without completing a migration. Running the first
product through `pwsh` proves cross-platform compatibility, but it does not provide the requested
Linux-native development environment.

## Frozen outcome

The accepted Ubuntu state has one active lifecycle Skill named `skill-lifecycle-manager`:

```text
CLI trigger -> Python lifecycle command -> host-local data change -> structured JSON feedback
```

The existing activity symbolic link continues to target the original Git repository so its history,
references, Registry semantics, and rollback commits remain continuous. The Python MVP is used as
implementation evidence, then its separate activity entry and tool installation are retired into a
readable backup instead of becoming a second long-lived product.

## Public contracts retained

- Python 3.12 and `uv` own the runtime and lock file; normal commands do not invoke `pwsh`.
- The command name is `skill`, with `scan`, `registry`, `report`, `governance`, `verify`, `install`,
  `update`, `backup`, `restore`, `stabilize`, and `health` subcommands.
- Read-only commands never write. Mutations preview by default and require `--apply`.
- Results remain structured JSON with literal `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and
  `NOT_RUN` evidence labels where applicable.
- Registry JSON remains canonical and schema version 1. YAML and Markdown files remain generated
  views rather than independent authority.
- Asset scope and lifecycle mode remain separate dimensions.
- Installation refuses collisions, validates before activation, publishes Registry last, and removes
  only transaction-created paths on failure.
- Update uses fetch, ancestry proof, detached candidate validation, and fast-forward; it never uses an
  unchecked pull or rewrites history.
- Backup hashes physical files, records symbolic links without following them, writes its manifest
  last, and restore accepts only an empty destination.
- Verification never installs dependencies, repairs a Skill, changes PATH, fetches credentials, or
  uses a shell command string.
- Stability baselines are host-local and immutable. Existing PowerShell-era evidence is archived
  before the Python baseline is published.

## Repository and rollback boundary

The original PowerShell files remain tracked as a migration fallback during v4. `SKILL.md` and the
installed `skill` command name Python as the normal Ubuntu entry. A rollback can therefore restore
the pre-v4 Git commit and the archived state files without recovering deleted source code.

Before cutover:

1. Verify both source repositories are clean and record their exact commits.
2. Create a link-aware backup of both sources, activities, state roots, and the installed tool entry.
3. Commit this migration contract separately from implementation.
4. Run the existing 63 PowerShell fixtures as the frozen legacy oracle.

## Acceptance gates

Implementation is accepted only when all of the following pass on the real Ubuntu host:

1. `uv sync --frozen` resolves Python 3.12 from the committed lock.
2. Python unit and transaction fixtures cover every public command, collision refusal, failed-install
   rollback, update blocking, verification layers, link-aware backup, safe restore, immutable
   stabilize, and zero-write health.
3. The official Skill validator passes and the package builds both wheel and source distribution.
4. Preview commands write nothing; every mutation requires `--apply`.
5. A fresh live Registry, capability report, governance report, complete backup, baseline, and health
   pass under the `skill-lifecycle-manager` XDG roots.
6. The installed `skill` executable resolves to this repository and runs without `pwsh` in PATH.
7. Codex discovery finds `skill-lifecycle-manager` exactly once and no active
   `linux-skill-lifecycle` entry remains.
8. Both the source and activity cutover have a verified readable rollback path.

If any gate fails, keep the original activity target and archived evidence unchanged, report the
exact blocker, and do not retire the Python MVP activity.
