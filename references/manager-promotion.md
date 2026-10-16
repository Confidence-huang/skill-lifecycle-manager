# Manager self-promotion

The manager cannot update itself through the generic path: `skill update` routes every other
SOURCE/HYBRID Skill through its own transaction, but the manager replaces the very source it is
running from, so `skill update --name skill-lifecycle-manager --apply` is blocked on purpose. Its
releases move through one exact, offline promotion instead. Both commands are Linux-only; rule 13
of `SKILL.md` keeps Windows out of Phase D and manager promotion until a Windows-native rollback
rehearsal is verified.

## Artifacts

A promotion needs three operator-supplied artifacts and one host state that already exists.

| Artifact | How it is produced | Constraint |
|---|---|---|
| Carrier bundle | `git bundle create <data-root>/carriers/<newCommit>.bundle main` | Must publish `newCommit`; the transaction records its SHA256 |
| Candidate source | A clean checkout at `newCommit` | HEAD must equal `newCommit` and `git status --porcelain` must be empty |
| Promotion plan | Written by hand as JSON | Key set must match the contract exactly |

The plan keys are exactly:

```text
schemaVersion documentType mode transactionID sandboxRoot oldCommit newCommit newManagerVersion
candidateSource carrierPath carrierSHA256 formalSource activityEntry formalCLI uvPath uvToolDir
uvToolBinDir uvReceipt recoveryRoot expectedInventoryCount stateSHA256 authorizedBy authorizedAt
```

Field rules worth checking before an apply:

- `mode` is `FORMAL` for `manager-upgrade` and `REHEARSAL` for `manager-rehearse`; a `FORMAL` plan
  must keep `sandboxRoot` null, and a `REHEARSAL` plan must keep every mutable path below
  `sandboxRoot`, including the activity and state roots passed on the command line.
- `transactionID` matches `transaction-<uuid>`; `recoveryRoot` must not exist yet.
- `newManagerVersion` must equal the running release, and `oldCommit` the current `formalSource`
  HEAD. `newCommit` must be a fast-forward descendant of `oldCommit`.
- `stateSHA256` pins exactly five preimages: `skills-registry.json`, `skills-registry.yaml`,
  `skill-capability-report.md`, `skill-governance-report.md`, `skill-stability-baseline.json`.
- `expectedInventoryCount` must equal the Registry `summary.inventory.physicalEntries` that is
  current when the promotion runs, so regenerate the Registry before authoring the plan if the
  inventory moved.

## Flow

```text
skill manager-upgrade  --plan PLAN            # preview: proves identity, zero writes
skill manager-upgrade  --plan PLAN --apply    # capture preimages -> stage -> publish -> verify
skill manager-rehearse --plan PLAN --failure-point POINT --apply   # disposable sandbox only
```

Apply runs `capture-preimages`, `stage-source` (clone the carrier into the recovery root),
`publish-source`, `publish-cli` (offline editable `uv tool install`), `publish-generated-state`
(`registry`/`report`/`governance --apply`), `archive-and-rebaseline`
(`stabilize --apply --archive-existing`), and `accept` (health must pass with zero mutations). Any
failure restores the previous source, receipt, state bytes, activity link, and health from the
recovery root and records the outcome in `manager-promotion.json`.

Failure injection points are `before-source-publication`, `after-cli-publication`,
`after-registry-regeneration`, and `after-baseline-archival`.

## Update-channel invariants

Publication replaces `formalSource` with a clone of the carrier, and a bundle clone names the bundle
as `origin`. The Registry derives `remote` and `branch` from the checkout, so a promotion that
leaves either wrong publishes `branch: null` or a bundle path as the update channel, and the generic
update preview degrades from `UPDATE_AVAILABLE` to `NOT_CONFIGURED` without an error. Promotion
therefore:

- keeps the outgoing `origin` update remote and re-applies it after publication;
- refuses a source whose `origin` is missing, already points at the promotion carrier, or resolves
  to a local file (a bundle is not an update channel);
- refuses a detached source, then reattaches the declared branch at `newCommit` after publication;
- rechecks both invariants on a completed-promotion retry, so a retry cannot accept a source that
  lost its channel since the promotion.

## Bootstrap ordering

The running manager is an editable install of the very source a promotion replaces, so a promotion
executes the **outgoing** code. A change to the promotion path itself therefore takes effect only
from the next promotion onward. When the promoted commit contains such a change, expect exactly one
manual finish-up:

```bash
git -C <formalSource> checkout <declared branch>
skill registry --apply && skill report --apply && skill governance --apply
skill stabilize --apply --archive-existing
skill health
```

## Keep the candidate source durable

A plan pins `candidateSource`, and a preview fails when that path is gone. Materialize it somewhere
durable next to the carrier so an old plan stays reviewable:

```bash
git clone <data-root>/carriers/<newCommit>.bundle ~/.local/share/skill-lifecycle-manager/candidates/<newCommit>
git -C ~/.local/share/skill-lifecycle-manager/candidates/<newCommit> checkout --detach <newCommit>
```

`/tmp` copies disappear with a reboot, while the carrier bundle in the data root is the durable
artifact that reproduces them.

## After a promotion

```text
skill --version                                -> sourceCommit = newCommit, sourceClean true
skill health                                   -> PASS with the new baseline
skill updates --name skill-lifecycle-manager   -> CURRENT
registry record                                -> remote = declared channel, branch = declared branch, commit = newCommit
baseline-history/                              -> the previous baseline preserved byte for byte
```

Carrier bundles are audit material: each transaction records the `carrierSHA256` it verified, so a
bundle can be re-verified later with `sha256sum` and `git bundle verify`.
