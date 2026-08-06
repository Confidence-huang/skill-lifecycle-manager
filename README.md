# Skill Lifecycle Manager

Python 3.12 and uv native Skill lifecycle tooling for Ubuntu. It preserves the established Registry,
governance, verification, transaction, recovery, and stable-health contracts while removing
PowerShell from the normal Linux runtime.

## Development

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run skill --help
uv build
```

The normal command surface is:

```text
skill scan
skill registry [--apply]
skill report [--apply]
skill governance [--apply]
skill verify (--name NAME | --target-skill PATH) [--apply]
skill install SOURCE --mode auto|package|source|hybrid [--skill-path PATH] [--apply]
skill update --name NAME [--apply]
skill updates (--name NAME | --all)
skill backup --path PATH [--path PATH ...] [--apply]
skill restore --backup-path PATH --destination PATH [--apply]
skill stabilize [--apply] [--archive-existing]
skill health [--project-root PATH]
```

`skill updates` reads optional PACKAGE release metadata from `.skill-lifecycle.json`, compares exact
stable Git tags, and probes an optional companion CLI. It never fetches, installs, upgrades, writes
state, or invokes GitHub CLI. `skill update --apply` remains the separate SOURCE/HYBRID mutation.

Run `./bootstrap.sh` only after the checkout is clean and acceptance passes. It installs the reviewed
checkout as the user-level `skill` command through `uv tool install --editable`.

## V5 Phase A contract candidate

The `schemas/` directory and `skill_lifecycle.contracts` module define the isolated V5 supply-chain
contract candidate. They validate synthetic artifacts, desired locks, evidence, approval decisions,
zero-write update previews, and transaction journals without reading or changing live lifecycle state.

```bash
uv run python -m unittest tests.test_contracts -v
```

Phase A is not CLI activation. It does not create a lock, approval, evidence report, transaction,
Registry migration, or baseline. Read `references/supply-chain-v5.md` before extending this candidate.
