# Package Release Update Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dependency-free, zero-write update checker that reports configured PACKAGE/CLI release freshness, beginning with the local Spec Kit adapter.

**Architecture:** Extend the existing `.skill-lifecycle.json` PACKAGE provenance record with an optional `updates` contract. Inventory validates and publishes that contract; a focused freshness module reads the canonical Registry, resolves stable semantic-version Git tags with `git ls-remote`, probes an optional CLI, compares versions, and returns structured feedback without fetching or writing. The existing `update --apply` source transaction and offline `health` command remain unchanged.

**Tech Stack:** Python 3.12 standard library, `argparse`, `subprocess`, `unittest`, Git CLI, uv.

## Global Constraints

- Do not require or invoke GitHub CLI.
- `skill updates` is read-only and always reports `mutations: 0`.
- Do not install or upgrade Spec Kit and do not modify any project `.specify/` content.
- Only stable `MAJOR.MINOR.PATCH` tags under the configured prefix are candidates.
- Preserve literal `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_INSTALLED` evidence states.
- Keep `skill health` offline and keep applied source updates behind `skill update --apply`.
- Use `.skill-lifecycle.json` schema version 1 for backward-compatible PACKAGE provenance plus an optional `updates` object.

---

### Task 1: PACKAGE provenance and update contract

**Files:**
- Modify: `src/skill_lifecycle/inventory.py`
- Modify: `src/skill_lifecycle/operations.py`
- Modify: `tests/support.py`
- Modify: `tests/test_inventory.py`
- Modify: `tests/test_install.py`

**Interfaces:**
- Consumes: an optional `<skillRoot>/.skill-lifecycle.json` JSON object.
- Produces: `read_package_record(skill_root: Path) -> tuple[dict[str, Any] | None, list[str]]` and Registry fields `origin`, `remote`, `commit`, `lifecycleSHA256`, and `updates`.

- [ ] **Step 1: Write failing inventory tests**

```python
def test_package_provenance_and_updates_are_published(self) -> None:
    record = {
        "schemaVersion": 1,
        "lifecycleMode": "PACKAGE",
        "origin": "/reviewed/package",
        "remote": None,
        "commit": None,
        "updates": {
            "strategy": "git-tags",
            "repository": "https://github.com/github/spec-kit.git",
            "tagPrefix": "v",
            "baselineVersion": "0.13.0",
            "cli": {"command": "specify", "arguments": ["version"]},
        },
    }
    write_lifecycle_record(skill, record)
    observed = scan_skills([activity])["skills"][0]
    self.assertEqual(observed["origin"], "/reviewed/package")
    self.assertEqual(observed["updates"]["baselineVersion"], "0.13.0")
    self.assertIsNotNone(observed["lifecycleSHA256"])
```

- [ ] **Step 2: Run focused tests and prove RED**

Run: `uv run python -m unittest tests.test_inventory tests.test_install -v`

Expected: failure because Python inventory does not yet read `.skill-lifecycle.json` and package install does not publish it.

- [ ] **Step 3: Implement strict backward-compatible PACKAGE record reading**

```python
def read_package_record(skill_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    record_path = skill_root / ".skill-lifecycle.json"
    if not record_path.is_file():
        return None, []
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"Installed-package provenance is unreadable: {error}"]
    if record.get("schemaVersion") != 1 or record.get("lifecycleMode") != "PACKAGE":
        return None, ["Installed-package provenance uses an unsupported schema."]
    return record, []
```

Inventory copies only validated scalar provenance and a validated `updates` object into the record. `inventory_fingerprint()` includes `lifecycleSHA256`, so metadata drift is health-visible.

- [ ] **Step 4: Make Python PACKAGE installation publish provenance**

After the copied package passes path validation, write `.skill-lifecycle.json` with `schemaVersion`, `lifecycleMode`, exact `origin`, inspected Git `remote`/`commit` when present, selected relative path, and UTC `installedAt`. Preserve a candidate's valid `updates` object so a packaged adapter keeps its checked update channel.

- [ ] **Step 5: Run focused tests and prove GREEN**

Run: `uv run python -m unittest tests.test_inventory tests.test_install -v`

Expected: all inventory and install tests pass.

### Task 2: Read-only release freshness engine and CLI trigger

**Files:**
- Create: `src/skill_lifecycle/freshness.py`
- Create: `tests/test_freshness.py`
- Modify: `src/skill_lifecycle/cli.py`
- Modify: `src/skill_lifecycle/lifecycle.py`

**Interfaces:**
- Consumes: canonical Registry records containing a validated `updates` contract.
- Produces: `check_updates(layout: HostLayout, name: str | None) -> dict[str, Any]` and CLI triggers `skill updates --name NAME` / `skill updates --all`.

- [ ] **Step 1: Write failing freshness tests**

```python
def test_missing_cli_uses_adapter_baseline_and_reports_update(self) -> None:
    result = check_updates(host, "spec-kit")
    update = result["updates"][0]
    self.assertEqual(update["cliStatus"], "NOT_INSTALLED")
    self.assertEqual(update["currentVersionSource"], "ADAPTER_BASELINE")
    self.assertEqual(update["latestVersion"], "0.16.0")
    self.assertEqual(update["updateStatus"], "UPDATE_AVAILABLE")
    self.assertEqual(result["mutations"], 0)
```

Use a local bare Git fixture with tags `v0.13.0`, `v0.15.2`, `v0.16.0`, and ignored prerelease/non-semver tags.

- [ ] **Step 2: Run the focused test and prove RED**

Run: `uv run python -m unittest tests.test_freshness -v`

Expected: import failure because `skill_lifecycle.freshness` does not exist.

- [ ] **Step 3: Implement stable tag and CLI evidence collection**

```python
def check_updates(layout: HostLayout, name: str | None) -> dict[str, Any]:
    registry = read_registry(layout)
    selected = select_configured_records(registry, name)
    updates = [check_record(record) for record in selected]
    return {
        "status": "PASS",
        "action": "UPDATES_CHECKED",
        "summary": summarize_updates(updates),
        "updates": updates,
        "mutations": 0,
    }
```

`check_record()` invokes `git ls-remote --tags <repository>` through an argument array with a timeout, accepts only exact stable semantic-version refs, probes the configured CLI through `shutil.which`, extracts one stable semantic version, and compares integer tuples. Network and parse failures become per-record `UNKNOWN` evidence instead of writes or retries.

- [ ] **Step 4: Add the CLI route**

```python
updates = commands.add_parser("updates", help="Check configured release freshness without writes")
updates_target = updates.add_mutually_exclusive_group(required=True)
updates_target.add_argument("--name")
updates_target.add_argument("--all", action="store_true")
```

`execute()` calls `check_updates(host, arguments.name)`; `health` remains the final offline branch.

- [ ] **Step 5: Run freshness and complete unit tests**

Run: `uv run python -m unittest tests.test_freshness -v`

Expected: all freshness cases pass.

Run: `uv run python -m unittest discover -s tests -v`

Expected: the complete suite passes.

### Task 3: Public contract, live Spec Kit metadata, and release evidence

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `references/operations.md`
- Modify: `references/registry-schema.md`
- Modify: `src/skill_lifecycle/__init__.py`
- Modify: `src/skill_lifecycle/inventory.py`
- Modify: `pyproject.toml`
- Modify outside repository after backup: `/home/a/.agents/skills/spec-kit/.skill-lifecycle.json`

**Interfaces:**
- Consumes: the tested CLI and Spec Kit's verified upstream URL/baseline.
- Produces: public v4.1.0 documentation and a live configured Spec Kit update record.

- [ ] **Step 1: Document the read-only command and schema**

Document `skill updates (--name NAME | --all)`, the `updates` fields, stable-tag rules, CLI evidence states, zero-write guarantee, and the separation from `skill update --apply` and offline health.

- [ ] **Step 2: Bump package and Registry generator versions**

Set `pyproject.toml`, `skill_lifecycle.__version__`, and `inventory.GENERATOR` to `4.1.0`.

- [ ] **Step 3: Scan and back up live Spec Kit before metadata mutation**

Run: `skill scan`

Expected: scan succeeds with zero mutations.

Run: `skill backup --path /home/a/.agents/skills/spec-kit`

Expected: preview succeeds with zero mutations.

Run: `skill backup --path /home/a/.agents/skills/spec-kit --apply`

Expected: a complete version-1 backup manifest is created before the package record changes.

- [ ] **Step 4: Add the reviewed Spec Kit update contract**

```json
"updates": {
  "strategy": "git-tags",
  "repository": "https://github.com/github/spec-kit.git",
  "tagPrefix": "v",
  "baselineVersion": "0.13.0",
  "cli": {"command": "specify", "arguments": ["version"]}
}
```

Keep the existing migration origin and installation timestamp unchanged.

- [ ] **Step 5: Regenerate Registry and prove the live result**

Run: `skill registry --apply`

Expected: the `spec-kit` record contains provenance plus the validated `updates` object.

Run: `skill updates --name spec-kit`

Expected: `cliStatus=NOT_INSTALLED`, `currentVersion=0.13.0`, `latestVersion=0.16.0`, `updateStatus=UPDATE_AVAILABLE`, and `mutations=0`.

### Task 4: Acceptance, publication, and stable evidence

**Files:**
- Verify all changed manager files.
- Refresh host-local generated evidence under `/home/a/.local/state/skill-lifecycle-manager`.

**Interfaces:**
- Consumes: completed implementation and live Spec Kit metadata.
- Produces: tested v4.1.0 command, clean Git commit, refreshed backup/Registry/reports/baseline, and final health evidence.

- [ ] **Step 1: Run frozen dependency sync, complete tests, validation, and build**

Run: `uv sync --frozen`

Run: `uv run python -m unittest discover -s tests -v`

Run the official `quick_validate.py` against the manager root.

Run: `uv build`

Expected: every command succeeds and both wheel and source distribution are produced.

- [ ] **Step 2: Prove preview paths do not write**

Hash the isolated Registry/state roots before and after `skill updates --name spec-kit` and `skill updates --all`; hashes and file counts must remain identical, and both results must report `mutations: 0`.

- [ ] **Step 3: Review, stage, and commit only manager repository changes**

Run: `git diff --check`

Run: `git diff --stat && git diff`

Stage only reviewed files in this repository and commit with `feat: check package release updates`.

- [ ] **Step 4: Publish the reviewed local command**

Run: `./bootstrap.sh`

Expected: `skill --help` exposes `updates` and resolves to this repository without requiring `pwsh` or `gh`.

- [ ] **Step 5: Refresh governance, recovery, and the immutable baseline**

Run preview/write pairs for Registry, report, governance, and backup. Then run `skill stabilize --apply --archive-existing` so the prior baseline bytes are preserved before the new v4.1.0 baseline is published.

- [ ] **Step 6: Run final health and discovery checks**

Run: `skill health --project-root "/home/a/CodexProjects/Project_44 AI学习"`

Expected: local integrity PASS, zero mutations, one `skill-lifecycle-manager` discovery entry, and upstream freshness still explicitly separated from offline health.

Run: `skill updates --name spec-kit`

Expected: the live release result remains `UPDATE_AVAILABLE` with zero mutations.

## Self-Review

- Spec coverage: PACKAGE provenance, explicit upstream metadata, Git-tag lookup, CLI absence, semantic comparison, batch/single checks, zero-write proof, docs, live Spec Kit evidence, publication, backup, and rebaseline are each assigned to a task.
- Placeholder scan: no deferred implementation or unspecified error-handling step remains.
- Type consistency: `updates` is the Registry contract field; `check_updates(layout, name)` is the business entry; CLI uses `--name` or `--all`; result rows use `cliStatus`, `currentVersion`, `currentVersionSource`, `latestVersion`, and `updateStatus` consistently.
