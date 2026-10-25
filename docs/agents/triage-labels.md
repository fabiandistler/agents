# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Canonical role      | Label in our tracker | Meaning                                  |
| ------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`      | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`        | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`   | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`   | `ready-for-human`    | Requires human implementation            |
| `wontfix`           | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

## Blocked issues

`ready-for-agent` marks the frontier: an issue an agent can start now and
finish without waiting on anyone. An issue with an open blocker gets
`ready-for-human` instead, even when its spec is complete. A blocker is any of:

- an unmerged PR the work builds on, draft or open;
- an open issue the work builds on: a native blocked-by edge, an open issue in
  the body's `Blocked by` line (see [issue-tracker.md](issue-tracker.md)), or,
  for a parent spec, its open sub-issues;
- a maintainer decision the work waits on.

Check all three before applying `ready-for-agent`. This rule binds every skill
that sets the label: `triage`, `to-spec`, and `to-tickets`, whose default
`ready-for-agent` applies only to tickets on the frontier. Those skills are
vendored by `scripts/vendor_mattpocock_skills.py`, so the rule lives here.

Name each blocker in the `ready-for-human` comment: the PR or issue number, or
the open question. When the last blocker clears (the PR merges, the issue
closes, the decision is recorded on the issue), swap `ready-for-human` for
`ready-for-agent`.
