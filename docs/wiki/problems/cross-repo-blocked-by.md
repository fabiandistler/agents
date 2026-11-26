# Cross-repo `Blocked by` URLs stop the implementer until removed

- 2026-11-11: PR #785 (closing #770, open) makes the implementer's blocker
  gate read `Blocked by <URL>`. A same-repo issue URL becomes `#<n>` and
  clears when that issue is closed as completed. Another repository's URL,
  or any pull-request URL, stays unresolved and returns `blocked`: it fails
  closed by design, because the gate cannot check it.
- Consequence (2026-11-11): such a line blocks the implementer
  permanently, even after the blocker is done, until a person removes it.
  The blocked comment from #785 says so.
- Where it bites (2026-11-11): the onboarding issues dotfiles#61 and
  repo-maintenance#153 list their blockers as agents issue URLs. Both are
  `ready-for-human` and note that the list must be rewritten before either
  is handed to the implementer. *Superseded 2026-11-20, see below.*
- 2026-11-20 (supersedes "Where it bites") [read]: dotfiles#61 and
  repo-maintenance#153 closed completed 2026-11-14 20:01 UTC without the
  implementer; their Blocked-by lists had been rewritten to agents#794 only
  that day. The 2026-11-11 claims about the mechanism are not affected.
  Source: [2026-11-20 status sweep](../snapshots/2026-11-20-status.md).
- 2026-11-26 (#964): a native "blocked by" dependency into a private
  repository was invisible to the claim and the queue: their repo-scoped
  tokens get an empty dependency list, so agents#956 stopped `at-capacity`
  and would have been dispatched before fabiandistler/repo-maintenance#208
  closed. The fix counts the open blockers in the issue's
  `issue_dependencies_summary.blocked_by` that the list does not show; they
  block until GitHub counts them closed. A native dependency is now the
  supported cross-repo wait, and a `Blocked by <URL>` line still fails
  closed. Not planned clears a hidden blocker, unlike a visible one. Probe:
  with the App token, agents#956 reported `total_blocked_by: 1` and an
  empty dependency list, so the summary counts the hidden edge.

Related: [rollout](../decisions/2026-11-11-factory-rollout.md).
