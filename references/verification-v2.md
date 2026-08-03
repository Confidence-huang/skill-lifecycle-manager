# Skill verification v2 design and migration plan

This document freezes the incremental v2 design before implementation. Version 2 extends the
existing inventory, Registry, baseline, transaction, and rollback system; it does not replace those
v1 capabilities or reinterpret their evidence.

## Outcome

The manager will distinguish three questions that previously shared one broad health label:

1. **Static health**: Is the Skill entry, source identity, manifest, and declared test layout valid?
2. **Runtime health**: Can the declared installed entry start in its real runtime?
3. **Behavior health**: Can the entry complete one bounded representative task and prove the result?

Every layer reports its own `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, or `NOT_RUN` state.
The overall result is `BLOCKED` when a required layer is blocked, `UNKNOWN` when a required layer
lacks evidence, and `PASS` only when every required layer passes.

The verifier never installs dependencies, edits a failing Skill, changes PATH, repairs Python, fetches
remotes, or retries with credentials. It executes only commands explicitly declared by the Skill's
manifest and reports the observed result.

## Compatibility boundary

- `skills-registry.json` remains the canonical v1 Registry and keeps `schemaVersion: 1`.
- Existing scan, governance, report, backup, restore, update, and stable-use semantics remain intact.
- A Skill without `skill.manifest.yaml` remains a legacy v1 asset: static entry validation still works;
  runtime and behavior are `NOT_CONFIGURED` rather than fabricated failures.
- The current immutable baseline is archived byte-for-byte before an explicit rebaseline. It is never
  deleted or silently overwritten.
- Install and update transactions keep their existing rollback rule: remove only paths created by the
  failed transaction, in reverse creation order.

## Manifest contract

Each opt-in Skill places `skill.manifest.yaml` beside `SKILL.md`. To avoid a new machine-wide YAML
dependency, version 1 of the contract uses JSON-compatible YAML: the file is valid YAML 1.2 and is
parsed with PowerShell's built-in JSON parser.

```yaml
{
  "schemaVersion": 1,
  "name": "example-skill",
  "requiredLayers": ["static", "runtime", "behavior"],
  "runtime": {
    "command": "pwsh",
    "arguments": ["-NoProfile", "-File", "{skillRoot}\\tests\\runtime.ps1"],
    "timeoutSeconds": 30,
    "runOnInstall": true,
    "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}}
  },
  "behavior": {
    "command": "pwsh",
    "arguments": ["-NoProfile", "-File", "{skillRoot}\\tests\\behavior.ps1"],
    "timeoutSeconds": 120,
    "runOnInstall": true,
    "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}}
  }
}
```

Supported placeholders are deliberately narrow:

- `{skillRoot}`: the verified physical Skill directory.
- `{tempRoot}`: a unique transaction-owned directory created for one test run.
- `{env:NAME}`: an already-present environment value; a missing value produces `UNKNOWN` and does
  not trigger environment repair.

Commands use an argument array, never a shell command string. Relative executable paths must stay
inside the Skill root. Named executables are resolved through the current process PATH and recorded
as evidence.

## Tests directory specification

An opt-in Skill uses this shape:

```text
skill-root/
├── SKILL.md
├── skill.manifest.yaml
└── tests/
    ├── runtime.ps1          # Starts the real installed entry without platform or hardware work.
    ├── behavior.ps1         # Performs one bounded representative task.
    ├── fixtures/            # Local deterministic inputs only.
    └── README.md            # States side effects, network policy, timeout, and acceptance evidence.
```

The runtime test proves import/command startup. The behavior test proves an outcome. Unit tests can
remain in their existing framework; these two files are stable lifecycle entrypoints, not a replacement
for the project's test suite.

## Verification flow

The new `verify` command follows one visible chain:

```text
explicit target -> static contract -> runtime command -> behavior command -> layered report
```

Preview validates the target and manifest but does not execute declared commands. `-Apply` runs the
declared tests, writes one timestamped JSON report under the Registry report directory, and removes
the unique temporary directory afterward. Raw secrets are not evidence: captured diagnostics are
bounded and redacted before display or persistence.

The existing `health` command remains read-only and continues checking the frozen global system. Its
output gains a v2 layer summary that does not launch Skill behavior implicitly. A targeted `verify`
report is the authoritative runtime/behavior evidence.

## Installation flow

The v1 transaction is extended only between activation and Registry publication:

```text
inspect -> static validate -> create physical asset -> create activation ->
run manifest layers marked runOnInstall -> publish Registry -> return installed result
```

If an install-time required layer fails, the manager:

1. writes the bounded failure report outside the transaction-owned Skill path;
2. removes only the activation and physical paths created by that transaction;
3. leaves the previous Registry untouched;
4. returns `BLOCKED` with the report path and exact failed layer.

This is transaction rollback, not automatic Skill repair.

## Migration plan

1. Add the parser, process runner, expectation checks, layered report object, and `verify` entrypoint.
2. Add isolated fixtures for missing manifests, invalid manifests, runtime failure, behavior failure,
   timeout, environment placeholders, successful reports, and install rollback.
3. Opt in `bilibili-video-learning` with a runtime test that imports the real installed module and an
   offline behavior test that normalizes an explicit Bilibili P2 URL.
4. Opt in `nuedc-stm32-mspm0-skill` with a runtime inspection test and a PC-only Project_22 Keil
   Rebuild behavior test. The project root comes from `STM32_BUILD_PROJECT_ROOT`; missing evidence is
   `UNKNOWN`. No Program, Flash, Verify, Reset, Run, serial, wiring, power, or hardware operation is
   allowed.
5. Run both cases, the manager fixture suite, official Skill validation, Registry generation, Codex
   discovery, and stable-use health.
6. Archive the existing baseline with its SHA256, regenerate Registry/reports after committed source
   changes, then create a new explicit baseline at the established canonical path.

## Case acceptance

### Bilibili video learning

- Static: manifest and both test entrypoints are valid.
- Runtime: the Skill-owned GPU Python can import and launch `cli_anything.video_learning` without
  `PYTHONPATH` or an editable source mapping.
- Behavior: offline normalization returns platform `bilibili`, BVID `BV1xx411c7mD`, and page `2`.
- Network, Cookie access, media download, and ASR remain outside this smoke test.

### STM32 build

- Static: the manifest and PC-only test entrypoint are valid.
- Runtime: Project_22 contains the frozen `LED.uvprojx` and PowerShell 7 build harness.
- Behavior: `validation/build-keil.ps1 -Mode Rebuild` returns success, the fresh log reports zero
  errors, and expected AXF/HEX artifacts exist with newly measured SHA256 values.
- The report is `BUILD_ONLY`; every physical and firmware-write layer remains `UNRUN`.

## Rollback

- Each source change is a separate local Git commit and can be reverted independently.
- The live video runtime is backed up before reinstalling the CLI package.
- Failed installs retain their v1 reverse-order cleanup behavior.
- The pre-v2 stability baseline is retained in baseline history with a verified SHA256.
- No Registry, report, baseline, Skill, source repository, or active entry is deleted automatically.
