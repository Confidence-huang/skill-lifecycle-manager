# Mutation and recovery boundaries

## Install transaction

1. Inspect or clone into a staging directory.
2. Locate eligible `SKILL.md` entries and validate frontmatter.
3. Resolve PACKAGE, SOURCE, or HYBRID mode.
4. Refuse an existing source or activity destination.
5. Copy or clone the physical entity.
6. Create a junction only after the physical source passes validation.
7. Regenerate the Registry.
8. Remove only paths created by the failed transaction when an error occurs.

The installer does not overwrite or merge an existing active Skill. Collision resolution is a separate review because equal names do not establish equal contents.

## Update transaction

1. Read the canonical JSON Registry.
2. Require one clean Git repository per selected asset.
3. Fetch `origin` and resolve the configured candidate ref or current upstream.
4. Require the local commit to be an ancestor of the candidate.
5. Create a detached temporary worktree at the candidate commit.
6. Validate every eligible candidate Skill entry.
7. Remove the temporary worktree.
8. Fast-forward the managed repository only after validation passes.
9. Regenerate the Registry.

No worktree change occurs before the final fast-forward. A fetch or validation failure therefore needs cleanup, not history rewriting.

## Backup transaction

- Copy physical files into a timestamped backup directory.
- Do not follow reparse points; record their source path and target instead.
- Hash every copied file with SHA256.
- Write the manifest last. A missing manifest means the backup is incomplete.

## Restore transaction

- Require a readable version-1 manifest.
- Require an empty destination.
- Verify every backup file against the manifest before copying.
- Restore physical files under destination subdirectories.
- Emit junction records for manual review instead of recreating absolute links automatically.

This restore target is deliberately separate from the live environment. Switching a restored tree into production remains a distinct, explicit operation.
