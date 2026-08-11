# Plugin Lifecycle Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-write `skill plugins` command that inventories Codex plugins and marketplaces without claiming connector authentication or runtime capability evidence.

**Architecture:** Put the Codex CLI subprocess and evidence normalization behind one deep `scan_plugins()` module interface. The CLI adapter invokes only documented JSON read commands, while callers and tests receive one stable result containing normalized marketplace, installation, path-topology, authentication, and runtime evidence.

**Tech Stack:** Python 3.12 standard library, `argparse`, `subprocess` argument arrays, `unittest`, uv, GitHub Actions on Ubuntu and Windows.

## Global Constraints

- Run repository Python only through `uv run python` and the committed lock file.
- The new command is read-only: no add, remove, enable, disable, upgrade, refresh, repair, authentication, Registry write, or baseline write.
- Treat `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_RUN` literally.
- Accept an exact `--codex-command` so a Desktop-bundled CLI is not conflated with another CLI on `PATH`.
- Invoke subprocesses with argument arrays, `shell=False`, bounded output, and a timeout.
- Keep plugin evidence separate from the Skill Registry and immutable Skill baseline in this release.
- Do not infer runtime injection or connector authorization from installed/enabled metadata.

---

### Task 1: Plugin observation module

**Files:**
- Create: `src/skill_lifecycle/diagnostics.py`
- Create: `src/skill_lifecycle/plugin_inventory.py`
- Modify: `src/skill_lifecycle/verification.py`
- Test: `tests/test_plugin_inventory.py`

**Interfaces:**
- Consumes: a Codex command string and `include_available: bool`.
- Produces: `scan_plugins(codex_command: str = "codex", include_available: bool = False) -> dict[str, Any]`.
- Reuses: `redact(text: str, limit: int = 4000) -> str` for bounded external-process diagnostics.

- [x] **Step 1: Write failing interface tests**

```python
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "marketplace"
    source = root / "plugins" / "sites"
    source.mkdir(parents=True)
    installed = {"installed": [{
        "pluginId": "sites@local", "name": "sites", "marketplaceName": "local",
        "version": "1.0.0", "installed": True, "enabled": True,
        "source": {"source": "local", "path": str(source)},
        "installPolicy": "AVAILABLE", "authPolicy": "ON_INSTALL",
    }], "available": []}
    marketplaces = {"marketplaces": [{"name": "local", "root": str(root)}]}
    responses = [
        subprocess.CompletedProcess([], 0, "codex-cli 0.146.0\n", ""),
        subprocess.CompletedProcess([], 0, json.dumps(installed), ""),
        subprocess.CompletedProcess([], 0, json.dumps(marketplaces), ""),
    ]
    with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="/opt/codex"), patch(
        "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
    ):
        result = scan_plugins("/opt/codex")
self.assertEqual(result["action"], "PLUGINS_SCANNED")
self.assertEqual(result["plugins"][0]["runtimeStatus"], "NOT_RUN")
self.assertEqual(result["plugins"][0]["authenticationStatus"], "UNKNOWN")
self.assertEqual(result["mutations"], 0)
```

Add cases for a missing CLI, nonzero command with credential redaction, malformed JSON, missing marketplace, missing local source path, a normalized path escape outside its marketplace root, available-plugin inclusion, and exact subprocess argument arrays.

- [x] **Step 2: Run the focused test and confirm RED**

Run: `uv run python -m unittest discover -s tests -p 'test_plugin_inventory.py' -v`

Expected: FAIL because `skill_lifecycle.plugin_inventory` does not exist.

- [x] **Step 3: Implement the deep observation module**

```python
def scan_plugins(codex_command: str = "codex", include_available: bool = False) -> dict[str, Any]:
    executable = _resolve_codex(codex_command)
    version = _run_text(executable, ["--version"])
    list_arguments = ["plugin", "list"]
    if include_available:
        list_arguments.append("--available")
    list_arguments.append("--json")
    plugin_payload = _run_json(executable, list_arguments)
    marketplace_payload = _run_json(executable, ["plugin", "marketplace", "list", "--json"])
    installed = _required_array(plugin_payload, "installed", "plugin list")
    marketplaces = [_normalize_marketplace(item) for item in _required_array(
        marketplace_payload, "marketplaces", "plugin marketplace list"
    )]
    marketplace_index = {item["name"]: item for item in marketplaces if item["name"]}
    plugins = [_normalize_plugin(item, marketplace_index) for item in installed]
    return {
        "status": "PASS",
        "codexVersion": version,
        "plugins": plugins,
        "runtimeEvidence": "NOT_RUN",
        "mutations": 0,
    }
```

The private implementation validates the documented top-level arrays, checks local roots without following or repairing them, records issues per plugin, and always leaves runtime evidence at `NOT_RUN`.

- [x] **Step 4: Run the focused test and confirm GREEN**

Run: `uv run python -m unittest discover -s tests -p 'test_plugin_inventory.py' -v`

Expected: all plugin-inventory tests PASS.

### Task 2: CLI and release contract

**Files:**
- Modify: `src/skill_lifecycle/cli.py`
- Modify: `src/skill_lifecycle/__init__.py`
- Modify: `pyproject.toml`
- Test: `tests/test_plugin_inventory.py`

**Interfaces:**
- Consumes: `skill plugins [--available] [--codex-command COMMAND]`.
- Produces: the unchanged structured JSON renderer and normal CLI exit semantics.

- [x] **Step 1: Add failing parser and dispatch tests**

```python
parsed = parser().parse_args(["plugins", "--available", "--codex-command", "/opt/codex"])
self.assertTrue(parsed.available)
self.assertEqual(parsed.codex_command, "/opt/codex")
```

Patch `skill_lifecycle.cli.scan_plugins` and assert that `execute()` passes both values unchanged.

- [x] **Step 2: Run the focused test and confirm RED**

Run: `uv run python -m unittest discover -s tests -p 'test_plugin_inventory.py' -v`

Expected: parser rejects `plugins`.

- [x] **Step 3: Add the command and bump the release to 5.3.0**

```python
plugins = commands.add_parser("plugins", help="Read Codex plugin and marketplace evidence without writes")
plugins.add_argument("--available", action="store_true")
plugins.add_argument("--codex-command", default="codex")
```

Dispatch to `scan_plugins()`, update `__version__` and `pyproject.toml` to `5.3.0`, and refresh `uv.lock` with uv.

- [x] **Step 4: Run the focused test and confirm GREEN**

Run: `uv run python -m unittest discover -s tests -p 'test_plugin_inventory.py' -v`

Expected: parser, dispatch, and observation tests PASS.

### Task 3: Public documentation and live read-only pilot

**Files:**
- Create: `references/plugin-governance.md`
- Modify: `README.md`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: users and agents deciding what `skill plugins` proves.
- Produces: explicit evidence meanings, Windows CLI selection guidance, and deferred mutation scope.

- [x] **Step 1: Document the evidence ladder**

Document inventory, enabled state, source topology, authentication, runtime injection, and representative behavior as distinct layers. State that only the first three are observed by this command and that installed/enabled is not runtime PASS.

- [x] **Step 2: Add command examples**

```text
skill plugins
skill plugins --available
skill plugins --codex-command /exact/path/to/codex
```

- [x] **Step 3: Run the worktree command against the live Linux CLI**

Run: `uv run skill plugins`

Expected: installed `sites` and `visualize` are inventoried with `mutations: 0`, local source topology `PASS`, and runtime `NOT_RUN`.

### Task 4: Completion and GitHub publication

**Files:**
- Review: all changed files and built distributions.

**Interfaces:**
- Consumes: the complete v5.3 change.
- Produces: a reviewed Git commit, GitHub branch, pull request, and cross-platform CI evidence.

- [x] **Step 1: Run all required checks**

Run:

```text
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run python tests/runtime.py
uv run python tests/behavior.py
uv run python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
uv build
```

Expected: all commands PASS and wheel/sdist both contain `skill_lifecycle/plugin_inventory.py` plus `references/plugin-governance.md` in the source distribution where packaging permits.

- [x] **Step 2: Review publication safety**

Run `git diff --check`, inspect the exact diff, and search tracked changes for credentials, host-specific absolute personal paths, private keys, authorization headers, and tokens.

- [ ] **Step 3: Commit and push**

```text
git add README.md SKILL.md pyproject.toml uv.lock src tests references docs/superpowers/plans
git commit -m "feat: add read-only plugin lifecycle evidence"
git push -u github codex/plugin-lifecycle-v5.3
```

- [ ] **Step 4: Open the pull request and require both CI jobs**

Open a PR linked to issue #2, wait for Ubuntu and Windows jobs, and merge only if both pass and the branch still matches the reviewed commit.

## Self-Review

- Spec coverage: issue #2 scope is covered by Tasks 1–4; plugin mutations and runtime repair remain explicit non-goals.
- Placeholder scan: the plan contains no deferred implementation placeholders; non-goals are deliberate release boundaries.
- Type consistency: `scan_plugins(codex_command: str, include_available: bool)` is used consistently by the module, CLI dispatch, tests, and docs.
