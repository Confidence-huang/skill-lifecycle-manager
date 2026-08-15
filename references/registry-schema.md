# Registry schema

The JSON Registry is the canonical machine-readable state. The YAML file beside it is a generated human-readable mirror.

Registry paths describe one live host. Generate fresh Registry and stability evidence after moving
between Windows and Linux; paths or link types from the previous host are historical input only.

## Top-level fields

| Field | Meaning |
|---|---|
| `schemaVersion` | Registry contract version. Version 1 is produced by this release. |
| `generatedAt` | ISO 8601 timestamp for the completed scan. |
| `generator` | Skill and script version that created the file. |
| `roots` | Existing activation roots included in the scan. |
| `summary` | Explicit inventory units plus counts by verification status, asset scope, and lifecycle mode. |
| `skills` | Deduplicated Skill asset records. |

## Skill fields

| Field | Meaning |
|---|---|
| `name` | Frontmatter name, or the directory name when frontmatter is invalid. |
| `description` | Frontmatter description when readable. |
| `status` | `PASS`, `BLOCKED`, or `UNKNOWN`. |
| `scope` | `SYSTEM`, `USER`, `PROJECT`, or `UNKNOWN`. |
| `lifecycleMode` | `PACKAGE`, `SOURCE`, `HYBRID`, or `UNKNOWN`. |
| `activePaths` | Every scanned activation path that resolves to the same physical entry. |
| `physicalPath` | Resolved Skill directory used for file and Git checks. |
| `origin` | User-supplied installation source recorded by a managed PACKAGE; otherwise null. |
| `sourceRepository` | Git top-level directory for SOURCE/HYBRID assets; otherwise null. |
| `remote` | Git origin URL when available. |
| `branch` | Current local branch when available. |
| `commit` | Full local commit SHA when available. |
| `lifecycleSHA256` | Hash of optional `.skill-lifecycle.json` PACKAGE provenance; null when absent. |
| `updates` | Validated PACKAGE release contract; optional `baselineCommit` and `packageTransaction` enable exact Linux `uv-tool-git` transactions. |
| `entryCount` | Eligible `SKILL.md` entries in the containing Git repository. |
| `issues` | Exact reasons for `BLOCKED` or `UNKNOWN`, never hidden behind a generic health score. |
| `isTopLevel` | Whether any activation path is a direct child of a scanned root. |
| `capabilityDomains` | Lexically inferred navigation domains; not semantic-equivalence claims. |
| `capabilityEvidence` | Rule meanings that explain each domain assignment. |
| `governanceState` | `AVAILABLE`, `SYSTEM_MANAGED`, `MANAGED_WITH_PARENT`, or `REVIEW_REQUIRED`. |
| `evidenceReadinessScore` | 0–100 completeness of metadata, activation, lifecycle, provenance, and collision evidence. |
| `evidenceTier` | `READY_EVIDENCE`, `PARTIAL_EVIDENCE`, or `REVIEW_EVIDENCE`. |
| `qualityEvidence` | Behavioral-quality evidence state; currently UNKNOWN without uniform evaluations. |
| `usageEvidence` | Invocation-evidence state; currently UNKNOWN without authorized telemetry. |
| `securityEvidence` | Audit-evidence state; currently UNKNOWN without a per-Skill audit. |
| `overallGrade` | `UNRATED` until quality, usage, and security evidence exists. |
| `recommendedAction` | Non-destructive suggestion derived from the observed governance state. |
| `governanceGaps` | Exact evidence still required before stronger lifecycle decisions. |

## Inventory count fields

`summary.total` remains a compatibility alias for `summary.inventory.physicalEntries`; it never means Codex Desktop rows.

| Field | Meaning |
|---|---|
| `physicalEntries` | Resolved physical `SKILL.md` entities after activity-link aliases are deduplicated. |
| `uniqueNames` | Exact frontmatter names; no semantic-equivalence inference is made. |
| `topLevelEntries` | Entries directly below a scanned activation root. |
| `nestedEntries` | Entries nested inside parent Skills, system directories, or plugin packages. |
| `activationAliases` | Extra discovery paths already excluded from `physicalEntries`. |
| `nameCollisionGroups` | Names backed by more than one physical entity. |
| `sameNamePhysicalExtras` | Physical entries beyond one representative per collision name. |

## Identity and duplicate rules

- Deduplicate aliases by the resolved physical `SKILL.md` path.
- Keep all activation aliases in `activePaths`.
- Treat equal names with different physical paths as a name collision, not as proven duplicates.
- Do not infer publisher identity from matching SHA256 values.
- Do not treat a branch name as an immutable version.
- Treat an adapter `baselineVersion` as reviewed compatibility evidence, not proof that its companion CLI is installed.
- Keep release checks separate from offline health and applied source updates; freshness probes never rewrite Registry state.
- Treat capability domains as a navigation graph, not proof that two Skills are duplicates.
- Treat evidence readiness as evidence completeness, not quality, safety, popularity, or business value.
- Keep overall grades UNRATED when behavior, usage, or security evidence is missing.
