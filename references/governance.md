# Capability governance

Phase 2 governance extends the canonical Registry; it does not create a second active tree or another Registry.

## Capability graph

Each physical record receives one or more `capabilityDomains` by matching explicit terms in its frontmatter name and description. `capabilityEvidence` records the matched rule meaning. When no rule matches, the domain is `unclassified`.

This is a lexical navigation aid. It does not prove that two Skills are interchangeable, redundant, or safe to merge.

## Evidence readiness score

`evidenceReadinessScore` measures whether a record has enough asset evidence for later governance:

| Evidence | Maximum |
|---|---:|
| Valid name and description | 25 |
| Observed activation path | 15 |
| Known PACKAGE/SOURCE/HYBRID mode | 20 |
| System ownership or recorded source/commit provenance | 25 |
| Collision-free exact name | 15 |

The score does not measure task quality, usage frequency, security, popularity, or business value.

Evidence tiers are:

- `READY_EVIDENCE`: 90–100
- `PARTIAL_EVIDENCE`: 75–89
- `REVIEW_EVIDENCE`: below 75

## Observed lifecycle states

- `AVAILABLE`: top-level PASS entry. Keep available until real usage evidence supports another decision.
- `SYSTEM_MANAGED`: PASS entry owned by Codex or a plugin version.
- `MANAGED_WITH_PARENT`: nested PASS entry whose parent Skill or repository owns its lifecycle.
- `REVIEW_REQUIRED`: Registry issues, missing provenance, or a name collision require review.

These states are observations and non-destructive recommendations. `FROZEN` and `ARCHIVED` require an explicit human decision and a separate mutation workflow.

## Unrated dimensions

Every record remains `overallGrade: UNRATED` until the inventory has all of the following:

1. Representative behavioral evaluations for quality.
2. Explicit, privacy-bounded invocation telemetry for frequency and last use.
3. Per-Skill instruction, script, dependency, and network audits for security.
4. Human confirmation of semantic overlap and business criticality.

Do not convert missing evidence into a low score, and do not use the Registry to authorize deletion, merging, freezing, or upgrading.
