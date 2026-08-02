---
name: skill-lifecycle-manager
description: Manage the complete lifecycle of Codex and cross-agent Skills on Windows with PowerShell 7. Use when Codex needs to inventory or classify Skills, generate the canonical Skill Registry, install a local or Git-backed Skill, update source-managed Skills through fetch and candidate validation, create an AI capability backup, or restore a backup into an empty destination. Distinguishes SYSTEM, USER, PROJECT, and UNKNOWN asset scope from PACKAGE, SOURCE, HYBRID, and UNKNOWN lifecycle mode.
---

# Skill Lifecycle Manager

Manage Skill assets as a small software supply chain instead of treating every `SKILL.md` as a copied folder.

Keep two classifications separate:

- Asset scope answers who owns activation: `SYSTEM`, `USER`, `PROJECT`, or `UNKNOWN`.
- Lifecycle mode answers how the asset is acquired and maintained: `PACKAGE`, `SOURCE`, `HYBRID`, or `UNKNOWN`.

## Operating rules

1. Load the governing workspace and project rules before changing global Skill state.
2. Run commands with PowerShell 7 through `pwsh -NoProfile`.
3. Use `scan` or `registry` before install/update work so decisions start from live evidence.
4. Treat output labels literally: `PASS` is verified, `BLOCKED` prevents the requested mutation, and `UNKNOWN` needs more evidence.
5. Use the default preview first when the target or effect is not already explicit. Add `-Apply` to perform the exact reported mutation.
6. Never replace an existing active entry. Resolve or remove the collision as a separate, explicitly scoped task.
7. Preserve one physical active entity. Use a junction for SOURCE/HYBRID activation and a physical directory for PACKAGE activation.
8. Pin Git-backed installations to the resolved full commit SHA. A branch is only an update channel.
9. Update with `fetch -> compare -> detached candidate validation -> fast-forward`, never with an unchecked `git pull`.
10. Keep backup and restore targets explicit. Restore only into an empty destination.

## Command entry

Use [scripts/skill.ps1](scripts/skill.ps1) as the single entrypoint:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command help
```

The command reports JSON so both a human and another agent can inspect exact paths, modes, commits, and stop reasons.

## Scan and build the Registry

Preview the live inventory:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command scan
```

Generate the canonical JSON Registry plus a readable YAML mirror:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command registry -Apply
```

Default Registry location:

```text
D:\CodexProjects\_skills\registry\skills-registry.json
D:\CodexProjects\_skills\registry\skills-registry.yaml
```

The JSON file is canonical. The YAML file is a generated mirror and must not be edited independently. Read [references/registry-schema.md](references/registry-schema.md) before consuming fields programmatically.

## Install

Install a self-contained local package:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" `
  -Command install `
  -Source "D:\incoming\my-skill" `
  -Mode Package `
  -Apply
```

Install a complete Git repository as a source-managed Skill:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" `
  -Command install `
  -Source "https://github.com/owner/repository.git" `
  -Mode Source `
  -Apply
```

Install one Skill from a multi-Skill repository:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" `
  -Command install `
  -Source "https://github.com/owner/repository.git" `
  -Mode Hybrid `
  -SkillPath "skills\chosen-skill" `
  -Apply
```

`Auto` mode classifies a local or cloned source from evidence. If a repository contains multiple eligible Skill entries, installation is `BLOCKED` until `-SkillPath` names the intended entry.

## Update

Preview one source-managed update:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command update -Name hop
```

Apply validated fast-forward updates to every eligible Registry entry:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command update -Name all -Apply
```

An update stops for dirty worktrees, missing remotes/upstreams, non-fast-forward history, invalid candidate Skill entries, or duplicate Registry names. See [references/operations.md](references/operations.md) for mutation and rollback boundaries.

## Backup and restore

Create a backup from explicitly supplied roots:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" `
  -Command backup `
  -Path "D:\CodexProjects\_skills\agents\skills","D:\CodexProjects\_skills\sources","D:\CodexProjects\_skills\registry" `
  -Apply
```

Preview restore into an empty destination, then repeat with `-Apply`:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" `
  -Command restore `
  -BackupPath "D:\CodexProjects\_skills\backups\ai-capabilities-YYYYMMDD-HHMMSS" `
  -DestinationRoot "D:\Restored-AI-Capabilities"
```

Backups copy physical files once and record junctions separately. Restore recreates files and reports junctions as link records; it does not silently recreate absolute machine-specific links.

## Completion checks

After any implementation or environment change:

1. Run `scripts/test-skill.ps1`.
2. Run the bundled `quick_validate.py` against this Skill directory.
3. Regenerate the live Registry.
4. Confirm the activity path is a junction to the clean source repository.
5. Confirm Codex discovery returns `skill-lifecycle-manager` exactly once.
6. Review the exact Git diff, stage only this Skill's files, and commit the verified atomic change.
