# Shared usage limit

The implementer, the chief-of-staff session with its subagents, and the
cloud sessions it starts all draw on one Claude subscription.

- 2026-11-13: implementer run 43503284321 (issue #782) ended
  `failure` at 20:50:21 UTC after 56 turns and $3.64, with no commit on
  `agent/issue-782`. In the same minute a chief-of-staff subagent stopped
  with HTTP 429 "You've hit your 5-hour limit". The run's transcript is
  hidden (`show_full_output: false`), so the cause is inferred from the
  timing, not read from the log.
- 2026-11-13: the triage that day used about 1.6M subagent tokens across
  eight subagents, plus two cloud sessions (#797, #767), while the
  implementer worked on #783 and #782.
- 2026-11-14: re-adding `ready-for-agent` to #782 at 05:17 UTC started run
  43560802532; the claim took over the empty branch and the run opened
  #809 at 05:32 UTC.
- 2026-11-14: open question to the user: keep the chief-of-staff session
  lean (no fan-out subagents while an implementer run works) or feed the
  queue only outside interactive hours. Until answered, the session stays
  lean.

Related: [no agent consumer outside agents](no-agent-consumer-outside-agents.md),
[merge plan](../merge-plan.md) (2026-11-14 section).
