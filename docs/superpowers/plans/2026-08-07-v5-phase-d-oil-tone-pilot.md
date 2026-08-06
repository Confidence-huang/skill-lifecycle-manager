# V5 Phase D oil-tone pilot runbook

## Status

`PREPARED_NOT_APPLIED`

This document selects one pilot and freezes its live-test boundary. It does not approve the
artifact, create a capability lock, write a transaction, publish an activity link, regenerate the
Registry, replace the stable baseline, or authorize the candidate manager to govern itself.

## Outcome and flow

Phase D must prove one complete, reversible capability-governance chain on Ubuntu:

```text
explicit user confirmation
  -> artifact-bound approval decision
  -> host-local ACTIVE lock revision
  -> preview with zero mutations
  -> durable IN_PROGRESS transaction
  -> temporary activity symbolic link and Registry publication
  -> deterministic Skill probes and expected old-baseline drift detection
  -> explicit rollback and INACTIVE lock revision
  -> exact Registry/report restoration and formal 22/22 health
```

The successful pilot ends with `oil-tone` inactive. Persistent adoption and baseline migration are
separate decisions after the rollback evidence is reviewed.

## Selected artifact

| Field | Frozen value |
|---|---|
| Skill | `oil-tone` |
| Canonical source | `https://github.com/oil-oil/oil-tone.git` |
| Ubuntu source repository | `/home/a/.local/share/skill-lifecycle-manager/reviewed-sources/oil-oil-oil-tone` |
| Skill path | `skills/oil-tone` |
| Commit | `24c9713765eac11f510a39cc55fdae4e5474fe4a` |
| Content SHA256 | `d94bd2ea481c2ee833f71dad9f5eb0812d84fcaf8447c72fd7976442324f4105` |
| Artifact ID | `sha256:f29bbec144b0e75514b6f0b7f22842bbcd9428d7e0087f50d0b812f02d0c6b2e` |
| Provenance evidence | `evidence-bc7ac42e-7ccb-5de3-8efd-573739603854` |
| Lifecycle and scope | `SOURCE`, `USER`, target Agent `CODEX` |
| Temporary activity path | `/home/a/.agents/skills/oil-tone` |
| Activity target | `/home/a/.local/share/skill-lifecycle-manager/reviewed-sources/oil-oil-oil-tone/skills/oil-tone` |

The full repository is the artifact identity boundary. Phase D activates the existing clean checkout
in place; it does not copy, rename, fetch, pull, or create a second physical Skill entity.

## Why this pilot

All eight reviewed-only oil sources were checked at their exact commits. Each checkout was clean,
its remote and HEAD matched the frozen source set, and its Skill name was absent from the formal
Registry. The selection minimizes behavioral and rollback risk, not only file count.

| Candidate | Static boundary | Pilot decision |
|---|---|---|
| `oil-tone` | Seven committed files; one standard-library Python lint script; explicit positive and negative probes | Selected: narrow, deterministic, and easy to roll back. |
| `explore` | Six files and no scripts | Deferred: changes broad codebase-reading and subagent coordination behavior. |
| `team-mode` | Executable Python plus tests and multiple references | Deferred: coordination and model-routing blast radius. |
| `git-ship` | Direct Git commit, push, and PR workflow | Rejected for first pilot: external and repository mutations. |
| `html-doc` | 38 files, executable JavaScript renderer, generated documents | Deferred: larger runtime and file-write surface. |
| `oil-cover` | Python generator and multi-megabyte image assets | Deferred: image-generation and asset surface. |
| `oil-ppt` | 99 files and a broad Python/HTML/PPTX toolchain | Deferred: largest runtime and output surface. |
| `vibehub` | Node package and scripts with external-link behavior | Deferred: runtime and network-facing behavior. |

`oil-tone` is not treated as trusted merely because its checks pass. The fixed source, commit,
logical tree, evidence, user decision, host lock, observed Registry state, and rollback result remain
separate facts.

## Verified preparation evidence

The following read-only checks passed on `project22-ubuntu` on 2026-08-07:

- the repository is clean and its `origin`, HEAD, Skill entry name, and full logical tree match the
  artifact manifest;
- the official `quick_validate.py` reports `Skill is valid!`;
- `tone_lint.py --self-test` passes using only Python's standard library;
- a neutral sentence returns `PASS  no known oil-tone failures`;
- a known prohibited ending returns exit code 1 and the expected diagnostic;
- the Registry contains no `oil-tone` record and `/home/a/.agents/skills/oil-tone` is absent;
- the formal Registry SHA256 remains
  `0cb0710bf1b7bfc43ea5688a759531071ed684f3171fa583dd22b2304c41c4a7`;
- the formal baseline SHA256 remains
  `43c29cc1cff0323c9278f59d4d236a6f8d7946e1801bf04e3b9cd0149bb0f4d4`;
- `/home/a/.local/bin/skill health` reports 22/22 PASS, no collisions or broken links, and
  `mutations: 0`.

The absolute manager command is mandatory. A bare `skill` must not be used in the runbook because
`type -a skill` also exposes the unrelated procps commands at `/usr/bin/skill` and `/bin/skill`.

## Mandatory implementation prerequisite

The Phase C candidate cannot execute this runbook yet. It intentionally exposes no public command
that joins the approval journal, capability lock, durable transaction, activity activation, Registry
publication, and rollback primitives.

Before any formal path changes, a separately reviewed Phase D implementation must provide all of
these behaviors:

1. Consume the exact Phase B manifest and provenance evidence without recomputing approval from
   Registry presence.
2. Append an `APPROVED` decision bound to the exact artifact ID and evidence ID only after explicit
   user confirmation. Preview must report the proposed record and write zero bytes.
3. Publish a host-local lock revision whose desired state is `ACTIVE`, with the exact decision ID,
   Agent, scope, lifecycle mode, and no inferred rollback artifact.
4. Preview one activation transaction and list every created or modified path. Preview must hash the
   Registry, generated reports, baseline, source checkout, and activity tree before returning.
5. Write a durable `IN_PROGRESS` transaction before creating the activity link or replacing any
   Registry/report byte. Publication must use atomic writes.
6. Activate only the frozen symbolic link, run required probes, and publish one Registry record that
   preserves the exact Git source, commit, physical path, scope, and lifecycle mode.
7. Roll back only from the reviewed transaction: remove the created link, restore the exact prior
   Registry and generated-report bytes, append the rollback result, append a decision that
   supersedes the pilot approval, and publish an `INACTIVE` lock revision.
8. Retain decisions, locks, transaction evidence, probe output, and backup references after rollback.
   These audit records may not be used as a second observed Registry.

Ad hoc JSON creation, direct `ln -s`, direct Registry editing, and unjournaled file removal are not
acceptable substitutes. Until this interface and its fault tests pass, Phase D stops at
`BLOCKED_MISSING_PHASE_D_TRANSACTION_INTERFACE`.

## Frozen execution runbook

### Gate D0: explicit authority

Require one user confirmation that names `oil-tone`, the full commit, the artifact ID, the temporary
activate-verify-rollback outcome, and the no-rebaseline boundary. A generic "continue" does not
authorize live mutation after this document is frozen.

### Gate D1: implementation acceptance

Implement and test the missing Phase D transaction interface only in the inactive candidate. Its
focused tests must cover:

- decision/artifact/evidence mismatch and expiry;
- preview hash invariance;
- physical and symbolic-link activity collisions;
- interruption before link creation, after link creation, and before Registry publication;
- probe failure after Registry publication;
- exact Registry/report restoration;
- a rollback retry that is idempotent and preserves unrelated canaries.

Run the focused suite, the full Ubuntu suite, `compileall`, wheel/sdist build, and the official Skill
validator against one clean candidate commit. Transfer only that exact commit to a new inactive
Ubuntu candidate. Formal source and activity still remain unchanged.

### Gate D2: before-state freeze and backup

Use only `/home/a/.local/bin/skill`. Recheck the selected source identity, activity absence, Registry
absence, current Registry/baseline hashes, and 22/22 formal health. Then preview and create a complete
link-aware backup of the activity tree and formal manager source:

```bash
/home/a/.local/bin/skill backup \
  --path /home/a/.agents/skills \
  --path /home/a/.local/share/skill-lifecycle-manager/sources/skill-lifecycle-manager

/home/a/.local/bin/skill backup \
  --path /home/a/.agents/skills \
  --path /home/a/.local/share/skill-lifecycle-manager/sources/skill-lifecycle-manager \
  --apply
```

The Phase D transaction must also retain exact private preimages and SHA256 values for the canonical
Registry, YAML mirror, capability report, and governance report. Those preimages are used only for
bounded rollback; they are not a second Registry or a new baseline.

### Gate D3: approval and ACTIVE lock

Preview the exact `APPROVED` decision first. It must reference only artifact
`sha256:f29bbec144b0e75514b6f0b7f22842bbcd9428d7e0087f50d0b812f02d0c6b2e` and evidence
`evidence-bc7ac42e-7ccb-5de3-8efd-573739603854`, include a bounded expiry, name the confirming user,
and use the frozen Phase D policy version.

After the preview returns `mutations: 0`, append the decision and publish an `ACTIVE` lock revision.
Immediately reread both documents through their Schemas and require the Phase C approval gate to
accept the exact artifact at the current time.

### Gate D4: activation preview and apply

The reviewed Phase D command must preview one transaction with this exact intended mutation set:

- create `/home/a/.agents/skills/oil-tone` as a symbolic link to the frozen Skill directory;
- replace only the four canonical Registry/report files through atomic publication;
- leave the source repository, formal manager source/activity, existing 22 Skill activities, and
  stability baseline unchanged.

Require the preview to return `mutations: 0`, the exact target and preimage hashes, and no collision.
On apply, persist `IN_PROGRESS` before the first mutation and stop on any identity or hash drift.

### Gate D5: temporary active verification

After activation, require all of the following:

Use the committed artifact-bound plan
`docs/superpowers/plans/2026-08-07-v5-phase-d-oil-tone-probe-plan.json`; do not reconstruct its
commands at the shell prompt.

1. the activity path is exactly one symbolic link to the frozen Skill directory;
2. Registry generation records exactly one `oil-tone` asset with SOURCE/USER/PASS and the exact
   repository, commit, Skill path, and activity path;
3. official validation, lint self-test, neutral positive probe, and known negative probe reproduce
   the preparation results;
4. Codex discovery reports `oil-tone` exactly once;
5. no existing Skill identity, activity link, or Registry record changes unexpectedly;
6. the old formal health check returns `BLOCKED` only for the expected inventory/Registry drift.

The last result is an intentional canary. Do not archive or replace the stable baseline merely to
turn this temporary pilot green.

### Gate D6: explicit rollback

Rollback from the durable transaction, never from a newly reconstructed path list. The rollback must:

1. inspect the transaction and current hashes with zero writes;
2. remove only the created `oil-tone` activity link;
3. restore the exact prior Registry, YAML, capability report, and governance report bytes;
4. preserve the reviewed source repository at its exact clean commit;
5. record `finalStatus: ROLLED_BACK` and a PASS rollback result;
6. append a superseding `REVOKED` or `EXPIRED` decision and publish an `INACTIVE` lock revision;
7. retain all audit and backup evidence.

### Gate D7: closing acceptance

Phase D is green only if:

- `oil-tone` is absent from activity and Registry again;
- the four restored Registry/report hashes equal their D2 preimages;
- the baseline hash is still
  `43c29cc1cff0323c9278f59d4d236a6f8d7946e1801bf04e3b9cd0149bb0f4d4`;
- `/home/a/.local/bin/skill health` returns 22/22 PASS, zero collisions, zero broken links, and
  `mutations: 0`;
- the formal manager source remains clean at its pre-pilot commit;
- the Phase D candidate remains an inactive, clean, exact Git commit;
- the approval, ACTIVE/INACTIVE lock revisions, transaction, probes, and rollback evidence are
  readable and Schema-valid.

## Stop and recovery gates

Stop immediately without automatic retry if any exact commit, artifact, evidence, source, activity,
Registry, report, baseline, or backup identity differs from this runbook. Also stop if a preview
writes bytes, approval is missing or stale, an activity collision exists, a probe is UNKNOWN, the
Registry loses an existing record, rollback cannot name every changed path, or formal health does not
return to its original PASS state.

If interruption leaves an `IN_PROGRESS` transaction, run only the reviewed zero-write recovery
inspection. Apply recovery only when every residual path is declared beneath its frozen owner root
and every preimage needed for restoration is present and hash-valid. Otherwise preserve evidence and
report `BLOCKED`; do not repair the live tree manually.

## Non-goals

- no persistent `oil-tone` adoption or stable-baseline migration;
- no activation of another oil Skill;
- no update, fetch, pull, copy, or relocation of the selected source;
- no external security scanner, marketplace, telemetry, automatic grading, or routing;
- no self-pilot of `skill-lifecycle-manager`;
- no change to the Windows fallback manager or its Registry.
