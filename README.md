# Skill Lifecycle Manager

Python 3.12 and uv native Skill lifecycle tooling for Ubuntu. It preserves the established Registry,
governance, verification, transaction, recovery, and stable-health contracts while removing
PowerShell from the normal Linux runtime.

## Development

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run skill --help
uv run skill --version
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
skill shadow --registry-path PATH --source-set PATH --output-root PATH [--apply]
skill manager-upgrade --plan PATH [--apply]
skill manager-rehearse --plan PATH --failure-point POINT [--apply]
skill health [--project-root PATH]
```

`skill updates` reads optional PACKAGE release metadata from `.skill-lifecycle.json`, compares exact
stable Git tags, and probes an optional companion CLI. It never fetches, installs, upgrades, writes
state, or invokes GitHub CLI. `skill update --apply` remains the separate SOURCE/HYBRID mutation.

`./bootstrap.sh install` is the fresh-install entry. `./bootstrap.sh upgrade --plan PATH [--apply]`
is the distinct offline manager-promotion entry; it delegates to the exact plan, preserves the prior
uv receipt and state preimages, and uses `uv tool install --offline --force --editable` only after
preview passes. A completed exact retry is zero-write.

## V5 Phase A contract candidate

The `schemas/` directory and `skill_lifecycle.contracts` module define the isolated V5 supply-chain
contract candidate. They validate synthetic artifacts, desired locks, evidence, approval decisions,
zero-write update previews, and transaction journals without reading or changing live lifecycle state.

```bash
uv run python -m unittest tests.test_contracts -v
```

Phase A is not CLI activation. It does not create a lock, approval, evidence report, transaction,
Registry migration, or baseline. Read `references/supply-chain-v5.md` before extending this candidate.

## V5 manager promotion candidate

`skill --version` reports package version, full source commit, Git tree, deterministic identity
SHA256, source path/cleanliness, and `mutations: 0`. A manager promotion plan pins old/new commits,
candidate source, carrier path/SHA256, formal source/activity/CLI, uv tool roots/receipt, five state
preimages, and the expected inventory count.

`skill manager-upgrade` previews by default. Applied FORMAL promotion captures recovery material,
publishes the source and CLI offline, regenerates the four observed-state views, archives/replaces
the baseline once, and requires final health `PASS` with zero mutations. `manager-rehearse` accepts
failure injection only for a REHEARSAL plan whose mutable paths remain below one sandbox root.
Rollback restores the old commit, receipt, views, baseline, activity resolution, and old health
while retaining failure evidence and any baseline-history artifact.

## V5 Phase B shadow candidate

`skill shadow` reads one frozen Registry v1 file and explicitly pinned Git sources. Preview returns
exact planned file hashes with `mutations: 0`; `--apply` may publish only a new named child below
`data-root/shadows`. Every proposed lock entry remains `BLOCKED_MISSING_APPROVAL`, so shadow output
cannot become desired state or authorize activation.
