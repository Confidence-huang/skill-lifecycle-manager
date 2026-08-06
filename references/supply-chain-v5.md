# V5 supply-chain contract candidate

Phase A turns the frozen V5 architecture into machine-valid, offline-testable contracts. It does not
activate a new lifecycle workflow and does not migrate the canonical Registry.

## Authority boundaries

| Data | Authority |
|---|---|
| Artifact manifest | Immutable source and content identity |
| Capability lock | Host-local desired and approved state |
| `skills-registry.json` | Existing observed host state; remains the only Registry |
| Evidence | Facts produced by one named probe for one artifact |
| Approval decision | Append-only human or future policy decision bound to one artifact |
| Transaction | Append-only record of an explicitly applied mutation and rollback result |

The lock is not a second Registry. It contains no observed physical path and cannot become active
without a valid decision for the same `artifactID`. The Registry cannot approve its own observations.

## Phase A contents

- `schemas/` contains Draft 2020-12 Schemas for the six documents above.
- `skill_lifecycle.contracts` normalizes logical paths, hashes logical trees, builds artifact identity,
  and encodes one canonical JSON Lines record.
- `tests/fixtures/contracts/` contains synthetic positive and negative examples only.
- `tests/test_contracts.py` checks the Schemas, identity invariants, traversal rejection, mutation-zero
  preview rule, and one-record-per-line journal encoding.

Git-backed content must be described from the resolved commit's logical content, not host checkout
paths. Slash variants may normalize to one logical path; different authoritative file bytes remain
different content. Phase A does not decide trust from a matching hash.

## Explicit stop gates

- No CLI command reads or writes these documents in Phase A.
- No live lock, evidence, decision, preview, or transaction directory is created.
- Registry schema version 1 remains unchanged.
- No baseline is archived or regenerated.
- No activity link, source repository, installed tool, PATH, or external scanner is changed.
- The formal manager is not the first live pilot of its own V5 mutation path.

Continue to shadow generation only after all Schemas pass their meta-schema, every valid fixture
passes, every negative fixture fails, full v4 regression passes on Ubuntu, and two host-style inputs
produce the same artifact identity from the same logical source facts.

## Phase B shadow contract

Phase B reads one frozen Registry v1 snapshot plus an explicit source-set document. The source set
pins the exact Registry file SHA256 so preview and apply cannot silently use different observations. Every source pins
its canonical remote, full commit, Skill path, role, suggested lifecycle mode, activity, and scopes.
Artifact content comes from the full committed Git tree, not mutable working-tree bytes. This broad
tree policy conservatively includes root-level shared resources; LFS pointers and submodules block the
run because their complete bytes are not present in the parent commit tree.

Preview creates no directory and reports exact output hashes. `--apply` may publish only a new named
child below `data-root/shadows`; an existing destination is a collision. The output contains artifact
manifests, provenance evidence, a host-local comparison report, and lock candidates. It contains no
decision and no valid capability lock: every candidate has `approvalDecisionID: null` and
`eligibility: BLOCKED_MISSING_APPROVAL`.

For a 4.1 Registry, the shadow projection also preserves `lifecycleSHA256` and the normalized
`updates` freshness contract. Shadow generation never executes that contract and never fetches
release data; the fields remain observed host evidence only.

An active Registry record without a real lock is reported as `UNMANAGED`, even when its observed
source facts match the pinned artifact. A reviewed-only source that remains absent is
`NOT_EVALUATED`; absence alone is not approval or convergence. Any name collision, physical-path
misclassification, commit/lifecycle mismatch, dirty source, missing required Registry field, LFS pointer, or
submodule stops the complete shadow run before publication.

## Phase C isolated behavior contract

Phase C runs only under temporary HOME/XDG-style roots. It exercises the real candidate install and
update paths plus pure approval and recovery primitives; it does not add a public command or write
formal V5 state.

The accepted fixture matrix proves:

- a hard child-process exit after PACKAGE activation leaves a declared residual path, requires a
  zero-write recovery inspection, and removes only that path after explicit recovery;
- an install Registry-publication failure removes only the new entity while preserving prior
  Registry and activity canary bytes;
- an update Registry-publication failure returns the clean managed repository to its exact prior
  commit while preserving Registry and unrelated canary bytes;
- physical and symbolic-link activity collisions stop before destination or Registry creation;
- an approval is effective only for its exact artifact while unexpired and not revoked or expired
  by a superseding append-only decision;
- parent traversal and link-backed recovery owners stop before deletion.

`skill_lifecycle.recovery` accepts only an `IN_PROGRESS` transaction with
`REMOVE_CREATED_PATHS`, no modified paths, and portable relative created paths. Its inspection and
apply calls remain separate. The durable transaction file is retained as evidence after recovery.

Phase C passing only opens review of Phase D. It does not authorize a real capability lock,
decision journal, transaction journal, activity switch, Registry migration, baseline change, or a
pilot using `skill-lifecycle-manager` itself.
