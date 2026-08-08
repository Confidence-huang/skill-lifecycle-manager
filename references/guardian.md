# Daily Guardian contract

## Authority model

`skills-registry.json` remains the only observed-state authority. Guardian policy is desired
monitoring state, reports are observations, and approvals are narrow mutation credentials. None of
those files replaces the Registry, Capability Lock, transaction journal, or baseline.

```text
daily schedule -> guardian scan -> JSON/Markdown report -> human review
human review -> exact approval -> explicit source update -> existing rollback transaction
```

The scheduled command ends after report publication. It cannot install, fetch, merge, activate,
upgrade, repair dependencies, or edit a project's `PROJECT_LOG.md`.

## Policy

```json
{
  "schemaVersion": 1,
  "documentType": "SKILL_GUARDIAN_POLICY",
  "policyVersion": "workstation-2026-08-08",
  "skills": [
    {
      "name": "easyeda-agent",
      "enabled": true,
      "riskTier": "HIGH",
      "updatePolicy": "REQUIRE_APPROVAL",
      "dependencies": [
        {"name": "easyeda", "command": "easyeda", "arguments": ["--version"]}
      ],
      "compatibilityProbe": null
    }
  ]
}
```

```text
skill guardian policy --file /exact/guardian-policy.json
skill guardian policy --file /exact/guardian-policy.json --apply
```

`riskTier` may be `UNKNOWN`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. `updatePolicy` may be `NOTIFY`
or `REQUIRE_APPROVAL`; both remain notification-only for scheduled work. V5.2 deliberately has no
automatic production update tier.

Every dependency and compatibility probe is an executable plus a literal argument array. Probes
have a ten-second limit, do not use a shell, do not repair anything, and do not retain raw output.
Dependency state is `PRESENT`, `MISSING`, or `UNKNOWN`. Compatibility is `PASS`, `BLOCKED`, or
`UNKNOWN`; absence of a probe is always `UNKNOWN`.

After the first completed report, the Guardian compares each declared dependency's observed stable
version with `latest.json` and reports `CHANGED`, `UNCHANGED`, or `UNKNOWN`. This is host dependency
drift evidence; candidate repository dependency-file changes remain unknown until the later detached
candidate validation step.

Skills absent from policy are still scanned with `riskTier: UNKNOWN` and
`updatePolicy: REQUIRE_APPROVAL`. Setting `enabled: false` keeps the Registry record visible but
suppresses its remote and local probes.

## Scan and reports

```text
skill guardian scan
skill guardian scan --apply
```

Preview reads the canonical Registry, uses Git `ls-remote` for SOURCE/HYBRID branches, reuses the
stable-tag PACKAGE checker, and writes nothing. It never fetches Git objects. Apply writes exactly
four files beneath the Guardian state root: immutable JSON/Markdown history plus replaceable
`latest.json` and `latest.md` views. Registry, sources, activity links, baseline, and project files
remain unchanged.

`UPDATE_AVAILABLE` means the remote identity differs from current observed state. It does not prove
fast-forward ancestry or compatibility; those facts require later candidate validation.

## Daily schedule

```text
skill guardian schedule --time 03:00
skill guardian schedule --time 03:00 --apply
```

Linux installs a systemd user service/timer. Windows installs one Task Scheduler entry. Both embed
the exact activity/data/state/cache roots and run only `guardian scan --apply`. Installation refuses
an existing schedule instead of overwriting it. Time uses the host's local 24-hour `HH:MM` value.

## Human approval and update

After reviewing one immutable report row, publish a bounded approval:

```text
skill guardian approve --report /exact/guardian/reports/guardian-...json --name easyeda-agent \
  --decision-id approval-11111111-1111-4111-8111-111111111111 \
  --requested-by USER --requested-at 2026-08-08T01:00:00Z \
  --decided-by USER --decided-at 2026-08-08T01:05:00Z \
  --expires-at 2026-08-09T01:05:00Z \
  --reason "Reviewed exact candidate and evidence." --apply

skill update --name easyeda-agent --approval /exact/guardian/approvals/approval-...json \
  --evaluated-at 2026-08-08T02:00:00Z --apply
```

The update re-resolves the remote candidate and rejects missing, expired, edited, stale, or
mismatched approval evidence before fetch. PACKAGE release checks remain reports only because the
manager does not yet implement a transactional PACKAGE upgrader.
