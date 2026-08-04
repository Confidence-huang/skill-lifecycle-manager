# Cross-platform v3 design and migration contract

This document freezes the Linux-first compatibility boundary before implementation. Version 3
keeps the existing lifecycle product and makes its host-dependent filesystem behavior explicit; it
does not create a second manager, Registry, active tree, or Python rewrite.

## Outcome

The same PowerShell 7 command entry will run on Windows and Linux while preserving the existing
structured output and lifecycle rules. Windows remains the currently accepted host. Linux becomes a
first-class target only after its own isolated and real-host acceptance evidence passes.

The product contracts remain unchanged:

- canonical Registry schema version 1 and generated YAML mirror;
- separate asset scope and lifecycle mode classifications;
- preview by default and explicit `-Apply` mutation;
- `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_RUN` evidence labels;
- one physical active entity, transactional install, failed-install cleanup, backup, restore, and
  immutable stable-use baseline;
- read-only routine health and no automatic repair, update, deletion, grading, or routing.

## Host-dependent facts

Only the following facts vary by operating system:

| Fact | Windows | Linux |
|---|---|---|
| User activity root | Existing `D:\CodexProjects\_skills\agents\skills` | `~/.agents/skills` |
| Source and backup state | Existing D-drive capability root | XDG data home, falling back to `~/.local/share` |
| Registry and baseline state | Existing D-drive Registry root | XDG state home, falling back to `~/.local/state` |
| Transaction staging | Existing D-drive staging root | XDG cache home, falling back to `~/.cache` |
| SOURCE/HYBRID activity link | `Junction` | `SymbolicLink` |
| Path identity | Ordinal, case-insensitive | Ordinal, case-sensitive |
| Directory separator | Runtime-provided separator | Runtime-provided separator |

Every CLI root remains explicitly overridable. Defaults are convenience values, not authorization
to scan or mutate unrelated home directories.

## Filesystem flow

The shared state module owns the host facts and exposes small path and link operations:

```text
CLI trigger -> host layout -> lifecycle command -> filesystem operation -> structured evidence
```

Commands must ask the shared module to compare paths, prove containment, and create activity links.
They must not embed drive letters, slash direction, case rules, or a specific link type.

Path containment remains a safety gate. A candidate must be a strict child of its declared owner
root; a textually similar sibling such as `skills-other` must never pass. Linux comparisons must not
collapse distinct case-sensitive paths.

## Host-local evidence boundary

Registry paths, activity targets, source roots, backup locations, and stability baselines describe
one live host. A Windows Registry or baseline must not be copied into Linux and treated as current
evidence. Linux starts with a fresh scan, Registry, reports, backup, and explicit stable-use baseline.

Backup manifests continue to record physical files and links separately. Restore continues to place
physical files only into an empty destination and reports link records for explicit review instead of
recreating machine-specific targets automatically.

## Test contract

The isolated fixture suite must run without Windows-only path or Junction assertions. It must prove:

1. the current host resolves non-empty activity, source, staging, Registry, and backup defaults;
2. same-path and containment comparisons follow the current host's case rules and reject sibling
   prefixes;
3. SOURCE and HYBRID installs create the host's expected link type;
4. scanning deduplicates link-backed aliases without lowercasing Linux identities;
5. update, backup, restore, stability, verification, and failed-install rollback retain their v1/v2
   behavior;
6. Windows runs the complete regression suite and keeps its established D-drive defaults.

Real Linux acceptance is separate from fixture portability. Before reporting Linux `PASS`, run the
complete suite and bounded CLI operations on Ubuntu, including symbolic-link resolution, file mode
handling, install rollback, link-aware backup, empty restore, Registry generation, stabilize, and
read-only health. Until then Linux runtime acceptance is `UNKNOWN`.

## Python decision gate

Python remains a possible future core, not a migration prerequisite. Reconsider it only after real
Ubuntu use establishes material PowerShell bootstrap cost, duplicated operating-system logic, or
Python-centric extension needs. If that gate is reached, replace commands incrementally behind the
same JSON and fixture contracts; do not create an independently evolving `skill-manager-next`.

## Rollback

- The design and implementation are separate local Git commits.
- The existing Windows Registry and frozen baseline are not rewritten by source-code tests.
- Every test artifact stays under one transaction-owned temporary directory.
- Reverting the implementation commit restores the Windows-only source behavior without deleting
  the preserved design record or any live Skill state.
