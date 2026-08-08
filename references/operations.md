# Mutation and recovery boundaries

## Install transaction

1. Inspect or clone into a staging directory.
2. Locate eligible `SKILL.md` entries and validate frontmatter.
3. Resolve PACKAGE, SOURCE, or HYBRID mode.
4. Refuse an existing source or activity destination.
5. Copy or clone the physical entity.
6. Create the host-supported activity link only after the physical source passes validation.
7. Run manifest layers explicitly marked `runOnInstall` and retain their evidence report.
8. Publish the regenerated Registry only after required install probes pass.
9. Remove only source/activity paths created by the failed transaction when an error occurs; retain diagnostic evidence and the previous Registry.

The installer does not overwrite or merge an existing active Skill. Collision resolution is a separate review because equal names do not establish equal contents.

For PACKAGE mode, `.skill-lifecycle.json` preserves the installation input and optional immutable
Git evidence. Its optional `updates` object may configure a read-only stable-release channel:

```json
{
  "strategy": "git-tags",
  "repository": "https://github.com/github/spec-kit.git",
  "tagPrefix": "v",
  "baselineVersion": "0.13.0",
  "cli": {"command": "specify", "arguments": ["version"]}
}
```

`skill updates --name NAME` checks one exact Registry record; `skill updates --all` checks every
configured record. The command accepts only exact `MAJOR.MINOR.PATCH` tags under the literal prefix,
uses `git ls-remote --tags` without fetch, and reports the optional CLI as `INSTALLED`,
`NOT_INSTALLED`, `NOT_CONFIGURED`, or `UNKNOWN`. Comparison reports `CURRENT`,
`UPDATE_AVAILABLE`, `AHEAD`, `UNKNOWN`, or `NOT_CONFIGURED`. Every path reports `mutations: 0`.
GitHub CLI is neither invoked nor required.

Verification never repairs a missing module, executable, dependency, environment variable, or behavior result. `UNKNOWN` means the probe could not establish the fact; `BLOCKED` means the declared contract was executed or parsed and failed.

## Update transaction

1. Read the canonical JSON Registry.
2. Require one clean Git repository per selected asset.
3. Resolve the configured remote candidate with `ls-remote` and no fetch.
4. When `--apply` would change the commit, require an unexpired Guardian approval bound to the exact
   Skill, current commit, candidate commit, Registry fingerprint, policy identity, and immutable report.
5. Fetch `origin` only after approval passes.
6. Require the local commit to be an ancestor of the candidate.
7. Create a detached temporary worktree at the candidate commit.
8. Validate every eligible candidate Skill entry.
9. Remove the temporary worktree.
10. Fast-forward the managed repository only after validation passes.
11. Regenerate the Registry.

No worktree change occurs before the final fast-forward. A fetch or validation failure therefore needs cleanup, not history rewriting.
V5.2 requires both `--approval` and `--evaluated-at` for a changing source update. Preview remains
zero-write and needs neither value.

## Backup transaction

- Copy physical files into a timestamped backup directory.
- Do not follow directory links or file symlinks; record their source path and target instead.
- Hash every copied file with SHA256.
- Write the manifest last. A missing manifest means the backup is incomplete.

## Restore transaction

- Require a readable version-1 manifest.
- Require an empty destination.
- Verify every backup file against the manifest before copying.
- Restore physical files under destination subdirectories.
- Emit filesystem-link records for manual review instead of recreating machine-specific links automatically.

This restore target is deliberately separate from the live environment. Switching a restored tree into production remains a distinct, explicit operation.
