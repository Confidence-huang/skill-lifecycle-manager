# V5 formal promotion readiness and rollback runbook

Status: `P0_IMPLEMENTED_EXACT_ARTIFACT_AND_APPLY_AUTHORIZATION_PENDING`

This runbook freezes the evidence, stop gates, mutation order, and rollback obligations for a
possible future promotion of the inactive V5 candidate. It does not authorize a formal manager
replacement, Registry regeneration, baseline archival, rebaseline, historical evidence repair, or
another `oil-tone` activation.

## Outcome

The Phase D rollback serialization fix remains accepted. The inactive successor now implements the
release-identity, offline upgrade-entry, and isolated manager-rollback gates below. Formal promotion
remains on hold until full acceptance produces the final successor commit and carrier SHA256, and a
new external promotion plan explicitly binds those post-commit identities to the formal mutation.

The candidate fixes future `transaction-rollback-start.json` events. Promotion cannot make the two
already retained invalid events valid, and those files must never be rewritten or presented as a
green historical Phase D acceptance.

## Frozen identities

| Item | Frozen value |
| --- | --- |
| Formal manager source | `/home/a/.local/share/skill-lifecycle-manager/sources/skill-lifecycle-manager` |
| Formal manager commit | `564215ba6c82927fc8ba2a9fc8943a6adef2e3ee` |
| Formal activity entry | `/home/a/.agents/skills/skill-lifecycle-manager` |
| Formal activity target | `/home/a/.local/share/skill-lifecycle-manager/sources/skill-lifecycle-manager` |
| Formal user CLI | `/home/a/.local/bin/skill` |
| Formal uv receipt source | editable formal manager source above |
| Inactive candidate | `/home/a/.local/share/skill-lifecycle-manager/candidates/skill-lifecycle-manager-v5-phase-d-schema-fix-f028d98` |
| Candidate commit / git number | `fe2efa25eb7de500b60bc3c3a2dbb7e1efd06105` / git #28 |
| Candidate carrier SHA256 | `69b60319ebfbc63313581d129256b7e36fa50c5a97742b2ad6ec6127045cbe3a` |
| Candidate relation | formal commit is an ancestor of candidate commit |
| Candidate package metadata | `skill-lifecycle-manager 4.1.0` |
| Formal package metadata | `skill-lifecycle-manager 4.1.0` |

The shell's bare `skill` name resolves to `/usr/bin/skill` because `/home/a/.local/bin` is absent
from the non-interactive PATH used during review. Every manager probe in this runbook therefore uses
the absolute `/home/a/.local/bin/skill` entry. A bare `skill` command is never identity evidence.

## Frozen formal state

The 2026-08-07 read-only review produced formal health `PASS`, 22/22 assets, zero broken links, and
`mutations: 0`. The formal state bytes were:

| Evidence | SHA256 |
| --- | --- |
| `skills-registry.json` | `0cb0710bf1b7bfc43ea5688a759531071ed684f3171fa583dd22b2304c41c4a7` |
| `skills-registry.yaml` | `0cb0710bf1b7bfc43ea5688a759531071ed684f3171fa583dd22b2304c41c4a7` |
| `skill-capability-report.md` | `dca076c01b90cce554895007c6f33fa3a08145ffcf4eb939d51fe0e58998ea61` |
| `skill-governance-report.md` | `68b276363a1ef5ed77a828fee7e67cc95504da9949903b91f0005bfce1ff3c56` |
| `skill-stability-baseline.json` | `43c29cc1cff0323c9278f59d4d236a6f8d7946e1801bf04e3b9cd0149bb0f4d4` |

The baseline records manager commit `564215ba6c82927fc8ba2a9fc8943a6adef2e3ee`. A future formal
promotion must archive this baseline before replacing it. Running `stabilize --apply` without
`--archive-existing` is forbidden.

## Historical Phase D evidence boundary

Offline Draft 2020-12 validation found seven valid transaction events and exactly two invalid
rollback-start events:

| Transaction | Rollback-start SHA256 | Frozen defect |
| --- | --- | --- |
| `transaction-557379d9-b092-495c-a3ed-7d4f7cd39226` | `0549c3cfb6a259d87db0f0a00acc25a1281e4795cebd751354f38c3796b582ff` | `finalStatus=IN_PROGRESS` with non-null `endedAt` |
| `transaction-91758fae-0a26-448a-832c-7eb943c6b1f6` | `382fbe29bd4a06cbaf1b2d0694b074490ce2c37dc0b1e80f3ac8b95038f0b79f` | `finalStatus=IN_PROGRESS` with non-null `endedAt` |

The files remain append-only historical evidence. Do not edit, replace, normalize, delete, or
rebaseline them. The accurate acceptance label remains `HISTORICAL_PHASE_D_SCHEMA_BLOCKED` even
after future code promotion. New disposable fixtures must prove the fixed serialization separately.

## Apply blockers

These three blockers are the frozen acceptance criteria. Successor code now implements them, but
formal promotion still stops until its final clean commit, carrier and external plan pass acceptance.

### 1. Release identity is ambiguous

The formal manager and V5 candidate both report package metadata `4.1.0`, and the CLI has no
`--version` option. A formal upgrade therefore cannot be proven from package metadata alone.

Required closure:

1. Assign one reviewed successor version consistently in `pyproject.toml`,
   `skill_lifecycle.__version__`, and generated identity fields that intentionally expose the
   manager version.
2. Add a zero-write `--version` entry that reports both the package version and resolved source
   commit, or publish an equally deterministic structured identity command.
3. Test installed-entry identity without relying on PATH order.

### 2. Bootstrap is install-only, not an explicit upgrade transaction

`bootstrap.sh` currently calls `uv tool install --editable` without an upgrade flag. The formal uv
tool is already installed, so the script does not express an idempotent, offline, exact-source
upgrade contract.

Required closure:

1. Add a separate explicit upgrade mode; keep fresh install and upgrade distinguishable.
2. Require the absolute uv entry `/home/a/.local/bin/uv`, offline resolution, an exact clean Git
   commit, and an explicit reinstall/force boundary.
3. Refuse a source path whose commit differs from the frozen candidate or whose worktree/index is
   not clean.
4. Prove retry behavior and preserve the prior uv receipt as rollback evidence.

### 3. Manager self-promotion rollback is not rehearsed

The Phase D tests prove a non-manager Skill pilot. They do not prove replacement and restoration of
the manager's own source, editable uv tool, Registry views, or stable baseline.

Required closure:

1. Rehearse the complete manager upgrade in disposable Linux roots with no live path overrides.
2. Inject failures before source publication, after CLI publication, after Registry regeneration,
   and after baseline archival.
3. At every interruption, restore the prior source commit, uv receipt/source, four generated state
   files, baseline bytes, and activity resolution.
4. Require exact preimage SHA256 equality and a final zero-mutation health pass.

## Future authorization text boundary

A later apply authorization must explicitly name all of the following. A generic `continue`, a
successful test run, or approval to modify the inactive candidate is insufficient.

- old and new full manager commits;
- the exact offline carrier and SHA256;
- formal source publication and user uv-tool reinstall;
- Registry/report regeneration;
- archival of the existing baseline and one deliberate rebaseline;
- automatic rollback authority for the exact failed promotion transaction;
- permission to retain failure evidence without repairing historical Phase D records.

It must still forbid network access, unrelated package updates, another Skill activation,
`oil-tone` persistence, history rewriting outside the exact promotion transaction, and deletion of
the prior source or recovery material.

The repository intentionally does not write its own future commit or carrier SHA256 into itself.
After the last candidate commit, create the carrier, hash it, and publish those exact values in the
external Schema-valid promotion plan. The CLI must prove that plan before any live path changes.

## Successor P0 implementation evidence

- Package, `skill_lifecycle.__version__`, uv lock and structured identity report `5.0.0`.
- `skill --version` reports full commit, Git tree, deterministic identity SHA256, source cleanliness
  and `mutations: 0`; new baselines preserve and health-check the same identity while reading V4
  baselines compatibly during the hold.
- `bootstrap.sh install` and `bootstrap.sh upgrade --plan ... [--apply]` are distinct. Upgrade runs
  the candidate with absolute uv, `--offline`, `--frozen`, and no development dependency resolution.
- The promotion plan pins candidate/carrier/formal/tool/state identities. Preview is byte-proven
  zero-write; applied uv replacement uses explicit `--force --editable` and preserves the prior
  receipt first; exact completed retry is zero-write.
- Real old/new manager fixtures inject all four frozen failure points. Each restores the old commit,
  uv receipt/tool source, four generated views, baseline bytes and activity resolution, then returns
  old-manager health `PASS / mutations=0`. Baseline history remains retained after the final fault.
- The exact-carrier rehearsal script refuses dirty or mismatched inputs and reruns the same public
  integration matrix in disposable uv/XDG roots. Final counts and carrier identity are recorded only
  after the last candidate commit.

## Promotion sequence after blockers close

This order is frozen. Every step is a stop gate; later steps do not run after a mismatch.

1. **Identity preflight** — prove the formal source/activity/CLI/baseline still match the frozen old
   state; prove the successor is clean, exact, fully tested, and carried by the authorized offline
   SHA256.
2. **Recovery capture** — create a fresh link-aware manager backup plus exact preimages of the uv
   receipt, four generated state files, and baseline. Perform a restore preview into an absent
   destination and hash every recovery artifact.
3. **Isolated staging** — materialize the successor beside the formal source, verify its Git history,
   source remote, commit, worktree, lock file, tests, validator, build, and structured identity.
4. **Source publication** — retain the old physical source under a transaction-owned recovery name
   and publish the staged source at the unchanged canonical formal path. The activity symlink must
   continue resolving to that canonical path.
5. **CLI publication** — use only the reviewed offline upgrade entry, then prove the absolute user
   CLI imports from the new canonical source and reports the successor commit.
6. **Generated views** — regenerate the single Registry and its YAML/capability/governance views.
   Reject any collision, broken link, blocked asset, unexpected count, or unrelated source drift.
7. **Baseline migration** — archive the exact old baseline, then and only then run one deliberate
   `stabilize --apply --archive-existing` against the verified new formal state.
8. **Acceptance** — require formal health `PASS`, 22/22 expected assets, zero mutations from the
   final read-only health, absolute CLI identity, Codex discovery, and unchanged absence of
   `oil-tone`.

## Rollback sequence

Rollback begins immediately after any failed gate following source publication. Do not continue
forward to make the new state look healthy.

1. Freeze the failed promoted source, CLI receipt, generated views, and diagnostics under the
   transaction evidence directory.
2. Restore the retained old physical source to the unchanged canonical formal path.
3. Reinstall the user CLI offline from that restored old source and prove its import path and old
   commit.
4. Restore the exact four generated preimages and the old baseline bytes. Preserve any newly created
   baseline-history item as failed-promotion evidence; do not claim it was part of the old state.
5. Prove the formal activity symlink again resolves to the restored source and that `oil-tone`
   remains absent.
6. Require all five frozen state SHA256 values above, formal health `PASS`, 22/22 assets, zero broken
   links, and `mutations: 0`.
7. Retain the failed promotion transaction and both historical invalid rollback-start events without
   editing their bytes.

If any rollback equality check fails, stop with `ROLLBACK_BLOCKED`, preserve all paths, and request
new explicit recovery authority. Never rebaseline around a failed rollback.

## Readiness evidence for git #28

- Formal commit is an ancestor of candidate commit: `PASS`.
- Windows and Ubuntu inactive candidate commit/clean identity: `PASS`.
- Ubuntu full regression: 64/64 `PASS`.
- Ubuntu `compileall`: `PASS`.
- Candidate read-only health against the formal host state: `PASS`, 22/22, `mutations: 0`.
- Future rollback-start Schema fixture added by git #28: `PASS`.
- Formal source/activity/Registry/baseline mutations during this review: zero.
- Formal promotion authorization: absent.
- Final readiness: `HOLD` until the three apply blockers close.
