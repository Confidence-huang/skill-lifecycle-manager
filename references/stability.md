# Stable operation and health

Stable operation begins only after inventory, governance, tests, Git, activity-link, report, and backup evidence all exist.

## Freeze the current local baseline

Preview first, then write one immutable baseline:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command stabilize
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command stabilize -Apply
```

The command creates `skill-stability-baseline.json` beside the canonical Registry. It records:

- the clean manager commit and activity junction;
- canonical Registry and generated-report hashes;
- a deterministic physical-inventory fingerprint; Registry-file hashes separately protect scope and governance labels;
- local commits and status fingerprints for SOURCE/HYBRID repositories;
- the newest complete version-1 backup manifest;
- explicit stable-use boundaries that keep automatic install, update, deletion, grading, and Phase 3 routing disabled.

It does not tag Git, create a branch, copy Skills, or alter the Registry schema. An existing baseline is never overwritten implicitly.

## Run routine health

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command health
```

Add `-ProjectRoot` to validate a project's `PROJECT_LOG.md` and `project-skill-profile.json` against the same global baseline:

```powershell
pwsh -NoProfile -File "<skill-root>\scripts\skill.ps1" -Command health -ProjectRoot "D:\CodexProjects\Project_25 学习东西"
```

Health is always read-only. It scans live Skill identity, compares local Git and file evidence, checks the frozen recovery manifest, and returns structured JSON. It does not fetch remotes; therefore upstream freshness is reported as `UNKNOWN_NOT_FETCHED`, never as “no updates.”

## Working-set boundary

Project tiers express task roles, not quality grades or observed frequency. A project may declare `CORE_WORKFLOW`, a domain-specific layer, and `ON_DEMAND` capabilities. The profile does not install, activate, route, freeze, archive, or delete any Skill.

Automatic capability routing remains a future Phase 3 decision. Real project use should accumulate evidence before the stable baseline or working set is redesigned.
