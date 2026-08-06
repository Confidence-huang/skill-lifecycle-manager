# V5 Phase C isolated behavior plan

## Starting point

Phase C starts from the clean integrated candidate at git #20
`ea2c4291446e03b8986d6e6611beec5309d44304`. The formal Ubuntu source, activity symbolic link,
Registry, reports, backup, and stability baseline remain outside the test roots and are read-only
canaries for the closing verification.

The frozen V5 architecture authorizes Phase C only inside temporary HOME/XDG layouts. It does not
authorize a real capability lock, an approval decision for a live Skill, a formal activity switch,
Registry migration, baseline replacement, external scanner, or Phase D pilot.

## Outcome

Prove this bounded chain with synthetic Skills and repositories:

```text
explicit fixture trigger
  -> exact candidate operation or recovery command
  -> transaction-owned temporary path change
  -> structured PASS/BLOCKED/rollback evidence
```

Every scenario must hash or compare pre-existing canaries before and after the injected failure.
Phase C passes only when transaction-created paths are removed or restored and every unrelated
canary remains byte-identical.

## Failure matrix

| Scenario | Injection point | Required result |
|---|---|---|
| Process interruption | After install activation and before final Registry publication | A durable relative-path recovery plan is inspected first; explicit recovery removes only the created activation and preserves sibling canaries. |
| Registry final-write failure during install | `write_registry` raises after the entity exists | Install rolls back its entity/activity; the prior Registry and unrelated activity entries remain unchanged. |
| Registry final-write failure during update | Fast-forward succeeds, then `write_registry` raises | The clean fixture repository returns to its exact prior commit and the prior Registry bytes remain unchanged. |
| Activity-link collision | Existing activity path is observed during preview | The request is `BLOCKED` before destination, Registry, or recovery-plan creation; the existing link target is unchanged. |
| Stale approval | Decision ID refers to another artifact, is expired, or is superseded by revoke/expire | Admission is `BLOCKED`; no lock, transaction, source, activity, or Registry path is created. |
| Unsafe recovery path | Relative path escapes an owner root or names an unknown owner | Inspection is `BLOCKED` with `mutations: 0`; no path is removed. |

## Candidate implementation boundary

1. Add a small recovery module that reads a versioned relative-path plan, performs a zero-write
   inspection, and requires a separate explicit call before removing paths in reverse order.
2. Add a pure approval-selection function that binds one decision ID to one exact artifact, checks
   evidence, expiry, and later superseding decisions, and performs no writes.
3. Harden the existing candidate update rollback so a final Registry publication failure restores
   the previously clean commit inside the isolated fixture repository.
4. Add one subprocess fixture for a hard process exit after activation. The parent test must prove
   that automatic retry does not occur, inspect the durable plan, then apply bounded recovery.
5. Keep all new tests under temporary roots. Tests may not read or write the host's actual HOME,
   XDG roots, activity tree, Registry, baseline, or formal source.

No new public CLI command or live state directory is introduced in Phase C. The recovery and
approval functions remain candidate primitives until a separately authorized Phase D design binds
them to an artifact-approved transaction.

## Stop gates

Stop before Phase D if any of the following occurs:

- an interruption leaves an unclassified path with no recovery evidence;
- recovery follows a symbolic link, crosses an owner root, or removes a canary;
- update rollback cannot restore the exact pre-apply commit and clean status;
- an old, expired, revoked, or artifact-mismatched approval is accepted;
- preview or blocked paths create a Registry, lock, decision, transaction, source, or activity;
- the existing 4.1, Phase A, or Phase B regression suite changes semantics;
- Windows focused tests or the complete Ubuntu suite fail for a product reason.

## Acceptance

Phase C is green only after focused fault tests pass on Windows, the complete suite passes on the
inactive Ubuntu candidate, `compileall` and wheel/sdist build pass, the official Skill validator
passes, and a final formal `skill health` remains read-only with unchanged Registry/baseline hashes.
Even then the result authorizes only review of Phase D; it does not authorize a real pilot.
