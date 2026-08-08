# Layered Skill verification

Verification separates three questions that must not share one vague health label:

1. **Static:** Is the Skill entry and declared manifest readable and valid?
2. **Runtime:** Can the declared installed entry start in its real runtime?
3. **Behavior:** Can it complete one bounded representative task and prove the result?

Each layer reports `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, or `NOT_RUN`. The verifier never
installs dependencies, edits a failing Skill, changes PATH, fetches remotes, or retries credentials.

## Manifest contract

Place `skill.manifest.yaml` beside `SKILL.md`. Version 1 uses JSON-compatible YAML so the runtime can
parse it without a machine-wide YAML dependency.

```json
{
  "schemaVersion": 1,
  "name": "example-skill",
  "requiredLayers": ["static", "runtime", "behavior"],
  "runtime": {
    "command": "{python}",
    "arguments": ["{skillRoot}/tests/runtime.py"],
    "timeoutSeconds": 30,
    "runOnInstall": true,
    "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}}
  },
  "behavior": {
    "command": "{python}",
    "arguments": ["{skillRoot}/tests/behavior.py"],
    "timeoutSeconds": 120,
    "runOnInstall": true,
    "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}}
  }
}
```

Supported placeholders are deliberately narrow:

- `{python}`: the current Python interpreter on Windows or Linux;
- `{skillRoot}`: the verified physical Skill directory;
- `{tempRoot}`: one unique transaction-owned work directory;
- `{env:NAME}`: an already-present environment value; missing evidence produces `UNKNOWN`.

Commands use an argument array, never a shell command string. Relative executables must remain
inside the Skill root. Named executables resolve through the current PATH and are recorded.

## Execution and evidence

Preview validates the target and manifest but does not execute probes. `--apply` runs configured
layers, bounds and redacts output, writes one timestamped JSON report, and removes the temporary
directory afterward. A timeout or failed required expectation reports `BLOCKED`.

A Skill without a manifest retains Static verification; Runtime and Behavior report
`NOT_CONFIGURED`. The global `health` command never launches these probes implicitly.

## Install boundary

Install runs only layers marked `runOnInstall`. If a required layer fails, the manager retains the
bounded report, removes only transaction-created activation/source paths, leaves the previous
Registry untouched, and returns the exact failed layer. This is rollback, not automatic repair.
