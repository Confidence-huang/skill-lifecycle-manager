# V5 Schema bundle

These Draft 2020-12 files describe the isolated V5 Phase A documents. Their `$id` values are stable
offline identifiers; validators must register the local files and must not fetch those identifiers.

| Schema | Responsibility |
|---|---|
| `artifact-manifest.schema.json` | Immutable source and complete logical-tree identity |
| `capability-lock.schema.json` | Host-local desired state backed by artifact-bound approval |
| `evidence.schema.json` | One probe's bounded evidence for one artifact |
| `approval-decision.schema.json` | One append-only approval, rejection, revocation, or expiry |
| `update-preview.schema.json` | Structured candidate difference with `mutations: 0` |
| `transaction.schema.json` | One applied mutation, rollback plan, and final result |
| `shadow-source-set.schema.json` | Explicit host, time, Git pins, roles, and suggestions for Phase B |
| `shadow-report.schema.json` | Host-local Registry/source comparison with `mutations: 0` |
| `lock-candidates.schema.json` | Non-authoritative candidates blocked by missing approvals |
| `pilot-probe-plan.schema.json` | Artifact-bound no-shell commands and exact expectations for one reviewed pilot |
| `pilot-probe-evidence.schema.json` | Bounded transaction-owned output from the reviewed probe plan |
| `common.schema.json` | Shared IDs, paths, timestamps, hashes, scopes, and tree entries |

The schemas intentionally reject unknown properties. A future additive field therefore requires a
new Schema version instead of silently changing the meaning of a signed or approved document.
JSON Schema validates each document's structure; `compute_artifact_id()` separately proves that an
artifact ID equals the canonical artifact identity rather than merely matching the ID's shape.

Run all meta-schema, positive-fixture, and negative-fixture checks with:

```bash
uv run python -m unittest tests.test_contracts -v
```
