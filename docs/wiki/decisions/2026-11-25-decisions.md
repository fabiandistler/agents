# 2026-11-25 decisions

- repo-maintenance#205 (waiting issues never start): the maintainer chose
  option 2 out of two. Option 1 was to add queue callers to repo-maintenance
  and dotfiles and bump their pin. Option 2 adds to that a claim in agents that
  promises the queue only when the caller configures one (`queue_workflow`), and
  an onboarding check that requires a queue caller next to the implementer.
  Reason given by the session: the defect sits in shared code that makes a
  promise it never checks, so a per-consumer fix leaves the next consumer
  exposed (`.claude/rules/agents-55-bug-fixing.md`). See
  [consumers without a queue caller](../problems/consumers-without-queue.md).
- The workflow changes are done in this interactive session, not by the
  implementer, because the implementer cannot write `.github/workflows/`
  ([implementer write limits](../problems/implementer-write-limits.md)).
- The session did not dispatch repo-maintenance#200 or dotfiles#79/#80 by
  hand (its own call, not the maintainer's): once the callers merge, the hourly
  queue schedule is expected to start them [inferred].
