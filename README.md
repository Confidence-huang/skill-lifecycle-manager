# Skill Lifecycle Manager

[![CI](https://github.com/Confidence-huang/skill-lifecycle-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/Confidence-huang/skill-lifecycle-manager/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://www.python.org/)

> An evidence-first CLI for governing the lifecycle of Codex Skills and plugins across Windows and Linux.

The manager makes host-changing work inspectable: mutating commands preview by default, applied operations require `--apply`, and verification reports distinguish `PASS`, `BLOCKED`, `UNKNOWN`, `NOT_CONFIGURED`, and `NOT_RUN`.

## Start here

Install [uv](https://docs.astral.sh/uv/), then clone and verify the repository with its isolated Python 3.12 environment:

```bash
git clone https://github.com/Confidence-huang/skill-lifecycle-manager.git
cd skill-lifecycle-manager
uv sync --frozen
uv run skill --version
uv run python -m unittest discover -s tests -v
```

For a host installation, use the platform bootstrap and then verify the installed command:

Linux:

```bash
./bootstrap.sh install
skill --version
```

Windows PowerShell 7:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 install
skill --version
```

## What it manages

- physical Skill inventory and alias deduplication;
- read-only Codex plugin and marketplace inventory with honest auth/runtime evidence gaps;
- canonical Registry plus generated governance reports;
- explicit Static, Runtime, and Behavior verification;
- transactional PACKAGE, SOURCE, and HYBRID installation;
- validated fast-forward source updates plus Linux uv-tool PACKAGE transactions with exact Git identities;
- scan-only daily Guardian reports with declared dependency and compatibility probes;
- exact, expiring human approvals required before source updates are applied;
- link-aware backups, verified restores, immutable baselines, and zero-write health checks;
- isolated V5 artifact, approval, evidence, lock, and transaction contracts.

## Platform support

| Capability | Linux | Windows |
|---|---:|---:|
| Scan, Registry, reports, governance | ✅ | ✅ |
| Read-only plugin and marketplace evidence | ✅ | ✅ |
| Verify and portable `{python}` probes | ✅ | ✅ |
| Install/update | ✅ symbolic link | ✅ directory junction |
| Backup/restore and stable health | ✅ | ✅ |
| V5 contract and shadow validation | ✅ | ✅ |
| Daily Guardian scan/report scheduling | ✅ systemd user timer | ✅ Task Scheduler |
| Guardian approval-gated source updates | ✅ | ✅ |
| Guardian approval-gated `uv-tool-git` PACKAGE updates | ✅ | Explicitly blocked |
| Reviewed Phase D pilot activation | ✅ | Not yet verified |
| Offline manager self-promotion/rehearsal | ✅ | Not yet verified |

The Linux-only rows are blocked explicitly on Windows. They need a separate Windows-native recovery rehearsal before they can be promoted to supported status.

## Core workflow

```text
skill scan
skill registry
skill registry --apply
skill governance --apply
skill plugins
skill plugins --available
skill plugins --codex-command /exact/path/to/codex
skill verify --target-skill PATH --apply
skill install SOURCE --mode source
skill install SOURCE --mode source --apply
skill package-configure --name NAME --contract CONTRACT.json --apply
skill update --name NAME
skill guardian policy --file guardian-policy.json --apply
skill guardian scan --apply
skill guardian schedule --time 03:00 --apply
skill guardian approve --report REPORT.json --name NAME ... --apply
skill update --name NAME --approval APPROVAL.json --evaluated-at TIMESTAMP --apply
skill backup --path PATH --apply
skill stabilize --apply
skill health
```

Preview and applied operations return structured JSON. Read [SKILL.md](./SKILL.md) for the agent workflow and [plugin governance](./references/plugin-governance.md) for the installation/source/auth/runtime evidence split. The other `references/` documents cover Registry, verification, mutation, governance, stability, and V5 supply-chain contracts.

## Safety model

- no implicit overwrite, merge, deletion, repair, or activation;
- Git state is pinned to full commits and updates must prove fast-forward ancestry;
- scheduled Guardian work publishes reports but cannot enter an install or update transaction;
- compatibility stays `UNKNOWN` unless a declared bounded probe supplies direct evidence;
- no risk tier permits unattended production updates in V5.4;
- PACKAGE apply supports only reviewed Linux `uv-tool-git` contracts and restores adapter, tool, executable link, shared uv metadata, Registry, and reports from a verified snapshot on failure;
- verification uses argument arrays, bounded output, timeouts, and credential redaction;
- backups do not follow activity links and restores do not silently recreate host-specific links;
- stable health never fetches, installs, updates, or writes;
- host-local Registry and baseline evidence must be regenerated after migration.

## Contributing and security

See [CONTRIBUTING.md](./CONTRIBUTING.md) before opening a change. Report vulnerabilities through the private process in [SECURITY.md](./SECURITY.md), not a public issue.

Licensed under the [Apache License 2.0](./LICENSE).
