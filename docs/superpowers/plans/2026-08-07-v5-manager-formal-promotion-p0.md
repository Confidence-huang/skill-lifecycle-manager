# V5 Manager Formal Promotion P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three frozen V5 promotion blockers with deterministic manager identity, one explicit offline promotion transaction, and an exact isolated self-promotion rollback rehearsal.

**Architecture:** `skill_lifecycle.manager_promotion` is the deep module. Its interface accepts one Schema-valid plan and optional rehearsal failure point; its implementation owns carrier inspection, preimage capture, source publication, uv-tool replacement, generated-view publication, rebaseline, acceptance, and reverse-order rollback. `skill --version`, `skill manager-upgrade`, `skill manager-rehearse`, and `bootstrap.sh` are thin callers at the same seam.

**Tech Stack:** Python 3.12 standard library, existing `jsonschema`, Git, absolute `/home/a/.local/bin/uv`, uv offline tool installation, Bash bootstrap, `unittest` integration tests.

## Global Constraints

- The frozen old formal commit is `564215ba6c82927fc8ba2a9fc8943a6adef2e3ee`.
- The implementation starts from inactive candidate `5ecfd304a66dd6aaa2e986bcb9b70f1ff344149b`; the final successor commit is created only after all code gates pass.
- The successor package version is exactly `5.0.0` in `pyproject.toml`, `skill_lifecycle.__version__`, the structured identity, and the stable baseline.
- Preview and identity paths are zero-write and report `mutations: 0`.
- Applied promotion is offline, requires an absolute executable uv path, exact clean old/new Git commits, a verified carrier SHA256, and an explicit `--apply`.
- Formal and rehearsal commands share the same transaction implementation; rehearsal additionally requires every mutable path beneath one disposable `sandboxRoot`.
- The four failure points are `before-source-publication`, `after-cli-publication`, `after-registry-regeneration`, and `after-baseline-archival`.
- Rollback restores the old source commit, uv receipt/source, four generated state files, baseline bytes, and activity resolution; final health must be `PASS` with `mutations: 0`.
- Historical Phase D events remain immutable and `HISTORICAL_PHASE_D_SCHEMA_BLOCKED`.
- No network, unrelated package update, another Skill activation, `oil-tone` persistence, or history rewrite is allowed.

---

## File Structure

- `src/skill_lifecycle/manager_identity.py`: deterministic package/source/tree identity and identity hash.
- `src/skill_lifecycle/manager_promotion.py`: promotion plan validation, preview, apply, failure injection, acceptance, and rollback.
- `schemas/manager-promotion-plan.schema.json`: exact FORMAL/REHEARSAL transaction input contract.
- `tests/test_manager_identity.py`: installed-entry and CLI identity behavior.
- `tests/test_manager_promotion.py`: preview, collision/refusal, retry, four rollback points, and success behavior.
- `scripts/rehearse_manager_promotion.py`: exact-commit offline rehearsal using disposable uv tool roots.
- `bootstrap.sh`: explicit `install` and `upgrade --plan ... [--apply]` modes.
- `src/skill_lifecycle/cli.py`: `--version`, `manager-upgrade`, and `manager-rehearse` adapters.
- `src/skill_lifecycle/stability.py`: include the same structured manager identity in generated baselines.
- `pyproject.toml`, `src/skill_lifecycle/__init__.py`, `uv.lock`: consistent `5.0.0` metadata.
- `README.md`, `SKILL.md`, `references/supply-chain-v5.md`: operator interface and authority boundaries.
- `docs/superpowers/plans/2026-08-07-v5-formal-promotion-readiness-and-rollback.md`: successor evidence and new exact authorization gate.

### Task 1: Deterministic Manager Identity

**Files:**
- Create: `src/skill_lifecycle/manager_identity.py`
- Create: `tests/test_manager_identity.py`
- Modify: `src/skill_lifecycle/cli.py`
- Modify: `src/skill_lifecycle/stability.py`
- Modify: `pyproject.toml`
- Modify: `src/skill_lifecycle/__init__.py`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: an optional exact source repository path.
- Produces: `manager_identity(source_root: Path | None = None) -> dict[str, Any]` and structured `skill --version` JSON.

- [ ] **Step 1: Write the failing public-interface test**

```python
def test_version_reports_package_commit_tree_and_zero_mutations(self) -> None:
    completed = subprocess.run([sys.executable, "-m", "skill_lifecycle", "--version"], text=True, capture_output=True)
    identity = json.loads(completed.stdout)
    self.assertEqual(identity["managerVersion"], "5.0.0")
    self.assertRegex(identity["sourceCommit"], r"^[0-9a-f]{40}$")
    self.assertRegex(identity["sourceTree"], r"^[0-9a-f]{40}$")
    self.assertRegex(identity["identitySHA256"], r"^[0-9A-F]{64}$")
    self.assertEqual(identity["mutations"], 0)
```

- [ ] **Step 2: Run RED**

Run: `uv run python -m unittest tests.test_manager_identity -v`

Expected: FAIL because `--version` and `manager_identity` do not exist and metadata is still `4.1.0`.

- [ ] **Step 3: Implement the minimal identity module**

```python
def manager_identity(source_root: Path | None = None) -> dict[str, Any]:
    repository = resolve_repository(source_root)
    commit = git_output(repository, "rev-parse", "HEAD")
    tree = git_output(repository, "rev-parse", "HEAD^{tree}")
    clean = git_output(repository, "status", "--porcelain=v1") == ""
    stable = {"managerVersion": __version__, "sourceCommit": commit, "sourceTree": tree}
    digest = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest().upper()
    return {"status": "PASS", "action": "MANAGER_IDENTITY", **stable,
            "sourcePath": str(repository), "sourceClean": clean,
            "identitySHA256": digest, "mutations": 0}
```

- [ ] **Step 4: Publish the same fields in `collect_baseline` and run GREEN**

Run: `uv lock --offline && uv run python -m unittest tests.test_manager_identity tests.test_stability -v`

Expected: PASS; the baseline manager object contains `version`, `sourceTree`, and `identitySHA256` from the same function.

### Task 2: Explicit Offline Upgrade Entry

**Files:**
- Create: `schemas/manager-promotion-plan.schema.json`
- Create: `src/skill_lifecycle/manager_promotion.py`
- Create: `tests/test_manager_promotion.py`
- Modify: `src/skill_lifecycle/cli.py`
- Modify: `bootstrap.sh`

**Interfaces:**
- Consumes: `manager-upgrade --plan /home/a/.local/state/skill-lifecycle-manager/v5/manager-promotion/plan.json [--apply]`.
- Produces: `preview_manager_promotion(plan_path, host) -> dict` and `execute_manager_promotion(plan_path, host, apply, failure_point=None) -> dict`.

- [ ] **Step 1: Write one preview RED test**

```python
def test_upgrade_preview_proves_exact_identity_without_writes(self) -> None:
    before = snapshot_tree(self.sandbox)
    result = preview_manager_promotion(self.plan_path, self.host)
    self.assertEqual(result["action"], "MANAGER_PROMOTION_PREVIEW")
    self.assertEqual(result["oldCommit"], self.old_commit)
    self.assertEqual(result["newCommit"], self.new_commit)
    self.assertEqual(result["mutations"], 0)
    self.assertEqual(snapshot_tree(self.sandbox), before)
```

- [ ] **Step 2: Run RED**

Run: `uv run python -m unittest tests.test_manager_promotion.ManagerPromotionTests.test_upgrade_preview_proves_exact_identity_without_writes -v`

Expected: FAIL because the plan Schema and promotion module do not exist.

- [ ] **Step 3: Implement plan validation and preflight**

The preflight validates Draft 2020-12 Schema, carrier SHA256, old source commit/cleanliness, carrier new head, ancestry, activity symlink, exact uv executable, receipt editable source, five preimage files, expected inventory count, and FORMAL versus REHEARSAL path policy. It returns facts only and creates no path.

- [ ] **Step 4: Run preview GREEN and add retry RED→GREEN**

```python
def test_completed_upgrade_retry_is_zero_write(self) -> None:
    first = execute_manager_promotion(self.plan_path, self.host, apply=True)
    before = snapshot_tree(self.sandbox)
    second = execute_manager_promotion(self.plan_path, self.host, apply=True)
    self.assertEqual(first["status"], "PASS")
    self.assertEqual(second["action"], "MANAGER_PROMOTION_ALREADY_COMPLETE")
    self.assertEqual(second["mutations"], 0)
    self.assertEqual(snapshot_tree(self.sandbox), before)
```

- [ ] **Step 5: Make bootstrap modes explicit**

```text
./bootstrap.sh install
./bootstrap.sh upgrade --plan /home/a/.local/state/skill-lifecycle-manager/v5/manager-promotion/plan.json
./bootstrap.sh upgrade --plan /home/a/.local/state/skill-lifecycle-manager/v5/manager-promotion/plan.json --apply
```

`install` remains fresh-install only. `upgrade` uses absolute uv with `uv run --offline --frozen skill manager-upgrade`; the transaction itself invokes `uv tool install --offline --force --editable` and retains the previous receipt first.

### Task 3: Self-Promotion Rollback Fault Matrix

**Files:**
- Modify: `src/skill_lifecycle/manager_promotion.py`
- Modify: `tests/test_manager_promotion.py`
- Create: `scripts/rehearse_manager_promotion.py`

**Interfaces:**
- Consumes: `manager-rehearse --plan /tmp/skill-manager-rehearsal/plan.json --failure-point before-source-publication --apply` for a Schema-declared REHEARSAL sandbox.
- Produces: a retained transaction directory and either terminal `PROMOTED` evidence or `ROLLED_BACK` evidence with exact preimage comparisons.

- [ ] **Step 1: Add the first failure RED test**

```python
def test_failure_before_source_publication_restores_exact_preimages(self) -> None:
    result = execute_manager_promotion(self.plan_path, self.host, True, "before-source-publication")
    self.assertEqual(result["action"], "MANAGER_PROMOTION_ROLLED_BACK")
    self.assertExactOldState()
    self.assertEqual(result["health"]["status"], "PASS")
    self.assertEqual(result["health"]["mutations"], 0)
```

- [ ] **Step 2: Run RED, implement reverse-order rollback, then GREEN**

The implementation writes preimages before publication, moves the old source under the transaction root, installs the new editable tool offline, regenerates four views, archives/replaces the baseline, and accepts only exact identity/health. Any exception restores source, reinstalls the old tool offline, restores five exact files, preserves failure evidence, and verifies old health.

- [ ] **Step 3: Add one vertical RED→GREEN cycle for each remaining point**

Run separately for `after-cli-publication`, `after-registry-regeneration`, and `after-baseline-archival`. Each test asserts old commit, old receipt source, four state SHA256 values, baseline SHA256, activity resolution, inventory count, `health=PASS`, and `mutations=0`.

- [ ] **Step 4: Add success and unsafe-path tests**

Success must report new commit/version, archive the old baseline, produce `health=PASS`, and accept an exact retry without writes. FORMAL rehearsal flags and REHEARSAL paths outside `sandboxRoot` must block before mutation.

### Task 4: Exact Candidate Acceptance and Successor Identity

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `references/supply-chain-v5.md`
- Modify: `docs/superpowers/plans/2026-08-07-v5-formal-promotion-readiness-and-rollback.md`

**Interfaces:**
- Consumes: the committed successor repository and locally created Git bundle.
- Produces: exact regression, validator, distributions, rehearsal, successor commit, carrier SHA256, and formal authorization text.

- [ ] **Step 1: Run all source gates**

```text
uv sync --frozen --offline
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests scripts
python3 /home/a/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
uv build --offline
git diff --check
```

- [ ] **Step 2: Commit the reviewed successor**

Stage only the candidate repository files, review `git diff --cached`, and commit with `feat: add transactional manager self-promotion`.

- [ ] **Step 3: Create and hash the offline carrier**

Create a full Git bundle under the lifecycle manager carrier directory, verify it, copy it into a fresh staging clone, and record its uppercase SHA256 without editing the committed tree.

- [ ] **Step 4: Run exact-commit isolated rehearsal**

```text
uv run python scripts/rehearse_manager_promotion.py \
  --old-commit 564215ba6c82927fc8ba2a9fc8943a6adef2e3ee \
  --new-commit "$(git rev-parse HEAD)" \
  --carrier /home/a/.local/share/skill-lifecycle-manager/carriers/skill-lifecycle-manager-v5.0.0.bundle \
  --uv /home/a/.local/bin/uv
```

Expected: all four injected failures restore exact preimages and health; the success case promotes to `5.0.0`, rebaselines once, and returns health `PASS`.

- [ ] **Step 5: Freeze the final apply gate**

Update the runbook with the new full commit, exact carrier path/SHA256, test counts, distribution hashes, rehearsal evidence, and the still-required formal mutation list. Do not change formal source, CLI, Registry, baseline, or activity until the authorization check names these newly generated identities.
