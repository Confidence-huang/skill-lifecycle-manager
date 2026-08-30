# PACKAGE Transaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` and execute this plan inline task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux-native, fail-closed `uv-tool-git` PACKAGE transaction to the existing `skill update` workflow and use it to install exact Spec Kit v0.16.4 with verified rollback.

**Architecture:** Keep `skill update` as the small external interface. Route SOURCE/HYBRID records through the existing fast-forward implementation and PACKAGE records through one new deep `PackageTransaction` module. The only production Adapter is `uv-tool-git`; command execution and filesystem state are internal seams used by isolated tests, not new CLI concepts.

**Tech Stack:** Python 3.12 standard library, uv 0.11+, Git argument arrays, JSON Registry/Guardian evidence, unittest, jsonschema.

## Global Constraints

- Linux/POSIX execution only for PACKAGE apply; no PowerShell or Windows paths.
- Candidate identity is exact `MAJOR.MINOR.PATCH` plus a peeled 40-character Git commit.
- Preview and discovery write nothing.
- Apply requires one unexpired Guardian approval bound to the exact version pair and Registry fingerprint.
- No snapshot means no apply; no complete restore plan means BLOCKED.
- Existing SOURCE/HYBRID update behavior and all existing tests remain compatible.
- Implement only the proven `uv-tool-git` package type required by `spec-kit`.

---

### Task 1: PACKAGE contract and exact release identity

**Files:**
- Modify: `src/skill_lifecycle/inventory.py`
- Modify: `src/skill_lifecycle/freshness.py`
- Modify: `src/skill_lifecycle/guardian.py`
- Modify: `schemas/update-approval.schema.json`
- Test: `tests/test_freshness.py`
- Test: `tests/test_guardian.py`

**Interfaces:**
- Consumes: `.skill-lifecycle.json` `updates` metadata.
- Produces: normalized `packageTransaction` metadata and exact release `{version, tag, commit}` evidence.

- [ ] **Step 1: Write one failing freshness test**

```python
def test_package_release_resolves_annotated_tag_to_exact_commit(self):
    result = check_record(record)
    self.assertEqual(result["latestVersion"], "0.16.4")
    self.assertRegex(result["candidateCommit"], r"^[0-9a-f]{40}$")
```

- [ ] **Step 2: Run the focused test and confirm RED**

```bash
uv run python -m unittest tests.test_freshness.FreshnessTests.test_package_release_resolves_annotated_tag_to_exact_commit -v
```

- [ ] **Step 3: Implement normalized `uv-tool-git` fields and peeled-tag resolution**

```python
def resolve_release(repository: str, tag_prefix: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Return stable version, exact tag, peeled commit, and issue without fetching."""
```

- [ ] **Step 4: Extend Guardian approval to exact PACKAGE version pairs**

```json
{"lifecycleMode": {"enum": ["SOURCE", "HYBRID", "PACKAGE"]}}
```

- [ ] **Step 5: Run freshness, inventory, Guardian and schema tests**

```bash
uv run python -m unittest tests.test_freshness tests.test_inventory tests.test_guardian tests.test_contracts -v
```

### Task 2: Preview, lock, snapshot and transaction journal

**Files:**
- Create: `src/skill_lifecycle/package_transaction.py`
- Modify: `src/skill_lifecycle/paths.py`
- Create: `tests/test_package_transaction.py`

**Interfaces:**
- Consumes: one exact PACKAGE Registry record.
- Produces: `preview_package_update(layout, record)` and `update_package(layout, record, apply, approval_path, evaluated_at)`.

- [ ] **Step 1: Write the preview/snapshot/lock RED tests**

```python
def test_preview_lists_exact_uv_tool_paths_and_commands(self):
    self.assertEqual(preview["installMethod"], "uv-tool-git")

def test_snapshot_failure_blocks_before_install(self):
    with self.assertRaisesRegex(LifecycleBlocked, "snapshot"):
        update_package(host, record, True, approval, evaluated_at)

def test_existing_lock_blocks_duplicate_transaction(self):
    lock_path.write_text("occupied", encoding="utf-8")
    with self.assertRaisesRegex(LifecycleBlocked, "transaction lock"):
        update_package(host, record, True, approval, evaluated_at)
```

- [ ] **Step 2: Implement one small external interface**

```python
def preview_package_update(layout: HostLayout, record: dict[str, Any]) -> dict[str, Any]:
    return PackageTransaction.discover(layout, record).preview()

def update_package(layout: HostLayout, record: dict[str, Any], apply: bool, approval_path: Path | None, evaluated_at: str | None) -> dict[str, Any]:
    transaction = PackageTransaction.discover(layout, record)
    return transaction.apply(approval_path, evaluated_at) if apply else transaction.preview()
```

- [ ] **Step 3: Persist an exclusive lock and append-only event files**

```text
state/v5/package-transactions/transaction-11111111-1111-4111-8111-111111111111/events/000-PREVIEWED.json
state/v5/package-transactions/transaction-11111111-1111-4111-8111-111111111111/events/010-SNAPSHOTTED.json
state/v5/package-locks/spec-kit.lock
```

- [ ] **Step 4: Snapshot package bytes, tool directory, bin entry and Registry/report preimages**

```json
{"transactionID":"transaction-11111111-1111-4111-8111-111111111111","package":"spec-kit","oldVersion":"0.13.0","candidateVersion":"0.16.4","restoreManifest":[]}
```

- [ ] **Step 5: Run focused tests GREEN**

```bash
uv run python -m unittest tests.test_package_transaction -v
```

### Task 3: Apply, verify, commit and real rollback

**Files:**
- Modify: `src/skill_lifecycle/package_transaction.py`
- Modify: `tests/test_package_transaction.py`

**Interfaces:**
- Consumes: exact candidate commit and complete snapshot.
- Produces: `COMMITTED`, `ROLLED_BACK`, `FAILED`, or explicit `BLOCKED` transaction evidence.

- [ ] **Step 1: Add normal update RED test**

```python
def test_uv_tool_package_updates_exact_commit_and_commits(self):
    self.assertEqual(result["finalState"], "COMMITTED")
    self.assertEqual(result["candidateCommit"], candidate_commit)
```

- [ ] **Step 2: Install through exact argument arrays and an exact commit**

```python
[uv, "tool", "install", distribution, "--force", "--from", f"git+{repository}@{candidate_commit}"]
```

- [ ] **Step 3: Verify executable, version, help, receipt, Skill, links and Registry**

```python
def verify_uv_tool_package(plan: PackagePlan) -> list[dict[str, str]]:
    return [verify_executable(plan), verify_version(plan), verify_receipt(plan), verify_help(plan)]
```

- [ ] **Step 4: Add apply-failure and verify-failure rollback RED tests**

```python
def test_apply_failure_restores_absent_tool_and_registry(self):
    self.assertEqual(read_live_state(), before)

def test_verify_failure_restores_previous_tool_symlink_config_and_registry(self):
    self.assertEqual(read_live_state(), before)
```

- [ ] **Step 5: Implement reverse restore and verify restored hashes/state**

```text
ROLLING_BACK -> restore manifest in reverse -> verify restore -> ROLLED_BACK
```

- [ ] **Step 6: Run all package transaction tests GREEN**

```bash
uv run python -m unittest tests.test_package_transaction -v
```

### Task 4: Preserve the existing update interface

**Files:**
- Modify: `src/skill_lifecycle/operations.py`
- Modify: `src/skill_lifecycle/cli.py`
- Modify: `tests/test_update.py`
- Modify: `tests/test_phase_c.py`

**Interfaces:**
- Consumes: existing `skill update --name NAME` CLI.
- Produces: routing by lifecycle mode without changing SOURCE/HYBRID callers.

- [ ] **Step 1: Add CLI routing RED test**

```python
def test_update_routes_package_record_to_package_transaction(self):
    self.assertEqual(update_skill(host, "package", False)["type"], "PACKAGE")
```

- [ ] **Step 2: Route PACKAGE records and retain existing source update function**

```python
if record["lifecycleMode"] == "PACKAGE":
    return update_package(layout, record, apply, approval_path, evaluated_at)
return update_source(layout, record, apply, approval_path, evaluated_at)
```

- [ ] **Step 3: Re-run SOURCE rollback and approval tests**

```bash
uv run python -m unittest tests.test_update tests.test_phase_c tests.test_guardian -v
```

### Task 5: Product documentation, version and complete regression

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/operations.md`
- Modify: `references/guardian.md`
- Modify: `references/supply-chain-v5.md`
- Modify: `pyproject.toml`
- Modify: `src/skill_lifecycle/__init__.py`

- [ ] **Step 1: Document exact supported and blocked PACKAGE cases**

```text
Supported: PACKAGE + git-tags + uv-tool-git + exact rollback coverage.
Blocked: unknown version/source, unpeeled tag, unknown path, incomplete snapshot, unsupported driver, system-level side effects.
```

- [ ] **Step 2: Set version 5.4.0 and run package/build validation**

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -p 'test_*.py' -v
uv run python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
uv build
```

- [ ] **Step 3: Commit the reviewed manager implementation**

```bash
git add -- SKILL.md README.md references schemas src tests pyproject.toml uv.lock docs/superpowers/plans/2026-08-15-package-transaction.md
git commit -m "feat: add transactional package updates"
```

### Task 6: Promote manager and transact Spec Kit v0.16.4

**Files:**
- Modify at runtime: formal manager source/tool through `manager-upgrade` only.
- Modify at runtime: `~/.agents/skills/spec-kit`, uv tool root/bin, Registry/report/baseline and transaction evidence through lifecycle commands only.
- Modify: the selected project's `PROJECT_LOG.md`

- [ ] **Step 1: Build an exact offline carrier and rehearse promotion rollback**

```bash
git bundle create ~/.local/share/skill-lifecycle-manager/carriers/skill-lifecycle-manager-v5.4.0-formal.bundle codex/package-transaction-v5.4
skill manager-rehearse --plan ~/.local/state/skill-lifecycle-manager/manager-promotion-v5.4.0-rehearsal.json --failure-point after-registry-regeneration --apply
```

- [ ] **Step 2: Apply the exact formal manager promotion**

```bash
skill manager-upgrade --plan ~/.local/state/skill-lifecycle-manager/manager-promotion-v5.4.0-formal.json --apply
```

- [ ] **Step 3: Add the reviewed `uv-tool-git` contract to spec-kit and publish fresh Registry/Guardian evidence**

```text
repository=https://github.com/github/spec-kit.git
candidateVersion=0.16.4
candidateCommit=d1f50fcbe684a4222059c4ba7f2d7eabcca87402
```

- [ ] **Step 4: Run the real PACKAGE transaction and isolated Spec Kit init smoke**

```bash
skill update --name spec-kit --approval "$APPROVAL_PATH" --evaluated-at "$EVALUATED_AT" --apply
specify version
specify --help
specify init --here --integration codex --integration-options='--skills' --script sh --ignore-agent-tools
```

- [ ] **Step 5: Rebaseline intentionally, run health/Guardian and update project continuity**

```bash
skill governance --apply
skill stabilize --archive-existing --apply
skill health
skill guardian scan --apply
```
