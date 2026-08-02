# Registry schema

The JSON Registry is the canonical machine-readable state. The YAML file beside it is a generated human-readable mirror.

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
| `entryCount` | Eligible `SKILL.md` entries in the containing Git repository. |
| `issues` | Exact reasons for `BLOCKED` or `UNKNOWN`, never hidden behind a generic health score. |

## Inventory count fields

`summary.total` remains a compatibility alias for `summary.inventory.physicalEntries`; it never means Codex Desktop rows.

| Field | Meaning |
|---|---|
| `physicalEntries` | Resolved physical `SKILL.md` entities after junction aliases are deduplicated. |
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
