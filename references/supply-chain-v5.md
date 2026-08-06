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
