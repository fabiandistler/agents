# Git Rebase

Rebase replays your branch's commits on top of another base, creating a linear
history. Compare with merge, which preserves the branch shape via a merge commit.

## Basic
```bash
git switch feature
git rebase main
```
This rewrites each commit on `feature` as if it were started from current `main`.

## Interactive rebase
```bash
git rebase -i HEAD~5
```
Lets you `pick`, `reword`, `squash`, `fixup`, `drop`, or reorder the last 5 commits.

## Rebase vs Merge
- **Rebase**: linear history, no merge commits, but rewrites SHAs.
- **Merge**: preserves true history, easier on shared branches.

## Golden rule
Never rebase commits that have been pushed to a shared branch — it forces
collaborators into a painful recovery. Rebase your private branch before
opening a PR; merge after review.

## Recovery
If a rebase goes wrong: `git rebase --abort`. Even after finishing, the old tip
is reachable via `git reflog`.
