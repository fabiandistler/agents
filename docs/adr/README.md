# Architecture Decision Records

Each ADR records one decision about this repository's own structure, with the
evidence and the options that were rejected. Read the ADR for the reasoning;
this index only points and shows the status.

Status values: **Proposed** (recorded, not decided), **Accepted**, **Amended**
(the decision stands with a later correction), **Superseded** (no longer
governs; the replacement ADR or current record is named).

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-refactoring-skill-scope.md) | Accepted (2026-09-05) | Reduce `refactoring` to finding refactoring targets: one auto skill with the churn script and two discipline notes. |
| [0002](0002-keep-architecture-router.md) | Accepted (2026-09-13) | Keep the `architecture` category behind one router with its sub-skills as members. |
| [0003](0003-looks-easy-trigger-floor.md) | Accepted (2026-09-13) | Accept the auto-trigger floor for requests that look easy; stop chasing them with description rewrites. |
| [0004](0004-distribution-channels-per-surface.md) | Superseded in part (2026-10-22) by [0010](0010-claude-marketplace-hybrid.md) | One distribution channel per install surface. The `claude` row stands; the `codex` and `opencode` rows do not. |
| [0005](0005-release-pr-version-model.md) | Accepted (2026-09-19) | `release-pr` uses a corrected per-PR version bump and stops at the PR, or tags after the merge. |
| [0006](0006-skill-eval-prompts.md) | Accepted (2026-09-27); strict CI since 2026-10-19 | Every auto or router skill ships `skills/<name>/evals.json`; command skills are exempt. |
| [0007](0007-ai-ml-router-recall.md) | Accepted (2026-10-30) | Keep the `ai-ml` router: routed reached the expected member 61/70 against flat 45/70. |
| [0008](0008-fork-improve-codebase.md) | Accepted (2026-10-13); A/B gate passed | Fork `improve-codebase` into the catalogue instead of patching the vendored command. |
| [0009](0009-fork-pr-description.md) | Superseded (2026-10-20); amended same day | Fork `pr-description` instead of patching `pr`. The skill was removed; Pocock's `pr` is vendored again. |
| [0010](0010-claude-marketplace-hybrid.md) | Accepted (2026-10-22); amended for `secret-guard`; supersedes [0004](0004-distribution-channels-per-surface.md) in part | `claude` gets plugins from the marketplace only; `codex` and `opencode` keep `install.sh`. |
| [0011](0011-pr-review-merge-exception.md) | Accepted (2026-10-28); not yet active (#635) | One model-free CI publisher may enable native auto-merge for gated docs-only PRs; interactive agents still never merge. |

## Supersession

- **0004 ↔ 0010:** 0010 supersedes the `codex` and `opencode` rows of 0004 and
  its "`install.sh` stops linking skills entirely". The `claude` row of 0004
  still stands.
- **0009:** superseded. The catalogue ships no PR-description skill; the
  decision text is kept as history. The current position is recorded in
  [`.out-of-scope/pr-description-skill.md`](../../.out-of-scope/pr-description-skill.md).
- **0008:** the A/B gate passed. The runs and their verdict are in
  [`docs/evals/improve-codebase-ab.md`](../evals/improve-codebase-ab.md).
- **0010:** amended for the `secret-guard` plugin, which follows the same
  split as the merge guard, and for `install.sh` installing both guard
  plugins through the `claude` CLI.
