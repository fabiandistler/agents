# 2026-11-11 — Expand the software factory: brakes first, then new tasks, then rollout

- **Decision (user, 2026-11-11, chief-of-staff session):** expand the
  software factory in this order: (1) the brakes, (2) new tasks, (3)
  rollout to other repositories once the brakes have merged.
- Brakes, as filed and opened on 2026-11-11:
  - #763 — `pr-review` depends on `pull_request_target`, which GitHub
    blocks by default in public repositories unless an Actions event policy
    allows it. PR #781 (refs #763) documents the policy; the policy itself
    is a manual repository setting. Dates per #763/#781: brownout
    2026-11-16 16:00–18:00 UTC, default block from 2026-12-02.
  - #770 — the implementer's blocker gate missed real Agent Briefs.
    PR #785 (closes #770) finds the brief heading anywhere in a trusted
    comment, parses `Blocked by <URL>` for same-repo issue URLs, and fails
    closed for other repositories' URLs and for pull-request URLs.
  - #764 — merges wait neither for the PR review nor for `bats`. PR #791
    (refs #764) sets a `pr-review/verdict` commit status; requiring it and
    `bats` in the ruleset is a manual step.
- Merge state and the order of the manual steps:
  [merge plan](../merge-plan.md), 2026-11-11 section.
- The rollout's dependency on the brakes is also written into the spec,
  #786 ("waits until the brakes #763, #764 and #770 are merged").

Related: [new tasks](2026-11-11-new-factory-tasks.md),
[rollout](2026-11-11-factory-rollout.md),
[goal](../goal.md) (improve before extend, 2026-10-19).
