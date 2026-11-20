# Runs that end without a trace

Three runs found by the [2026-11-20 status sweep](../snapshots/2026-11-20-status.md)
ended without the artifact they were meant to produce, and nothing in the
repositories recorded the miss.

- **repo-maintenance weekly maintenance run, 2026-11-16: no repo trace; push
  notification sent.** Scheduled task `trig_01XPRmF1GFqjd1qFoWGvCi1G`
  ("repo-maintenance weekly maintenance run", Mondays 08:32 Europe/Berlin;
  [schedules](../schedules.md)).
  - In the repo [read, 2026-11-20 sweep]: no `maintenance/*-2026-11-16`
    branch, no PR, no issue, no run record, and no Actions run in
    repo-maintenance between 2026-11-15 08:05 and 2026-11-19 07:37 UTC. The
    last `maintenance/` PR is repo-maintenance#122 (2026-11-07), the newest
    run record 2026-11-07 `error-edges`. `maintenance-pr-review` has never
    reviewed a `maintenance/` PR; every run of it is `skipped`.
  - The run [read, 2026-11-20 diagnosis of the scheduled task and its
    session transcript]: the task fired 07:32:42 UTC; session
    `cse_0154VwoYH6snGir8pi7WAc75` ran 07:32:42–07:35:05 UTC. Setup passed:
    checkout present, `git push --dry-run` worked, main at
    `fabiandistler/repo-maintenance@0bf606c`, the first four Bash calls
    succeeded. From 07:33:12, seven Bash calls in a row got "auto mode
    classifier gave no verdict (error)"; Read, Glob, Grep and the GitHub MCP
    reads kept working. The run stopped, sent a push notification starting
    "RUN FAILED" at 07:34:59 UTC, and wrote nothing to the repo.
  - Status fields hid it [read]: the task's `last_run.status` reads
    `SUCCEEDED` (the session ran), and the session's result record says
    `is_error: false`, with 7 Bash permission denials.
  - The job choice was right [read]: `maintenance-runs.py due --today
    2026-11-16` gave `deps-audit` 1.43 and `doc-drift` 1.14, and the run named
    `deps-audit`.
  - No repo record, by design [read]: a run record reaches `main` only with
    its merged PR (`MAINTENANCE.md:159` at
    `fabiandistler/repo-maintenance@bacc59d`), so a run that aborts leaves
    only the push notification and the session transcript.
  - Cause [inferred]: a transient outage of the auto-mode classifier, not the
    repo, the prompt or the task. Bash calls of the same kind passed seconds
    earlier, the message calls the failure transient, and the same skill path
    passed the check in an auto-mode routine session on dotfiles on
    2026-11-15. Not corroborated: no other session from those minutes was
    read.
  - Consequence (2026-11-20): repo-maintenance#137 still waits. Between
    `0bf606c` and `bacc59d` nothing the run depends on changed [read], and
    `due --today 2026-11-23` names `deps-audit` (2.43) next [read].
  - Idea from the diagnosis (2026-11-20, not decided): a model-free scheduled
    workflow in repo-maintenance, some hours after the Monday slot, that opens
    one issue when a job is due and no `maintenance/*-<today>` PR was opened.
- **Retro on PR #873, run 44544546644, 2026-11-19 14:30 UTC** [read,
  2026-11-20]:
  - the gate selected #873 and labelled it `retro:done` at 14:31:10;
  - the model job ran 8.3 s and 6 turns, with `is_error: false`;
  - branch `agent/retro-873` does not exist (404), and no retro PR exists;
  - the prompt allows "at most one" PR.

  [inferred] 8 s is short for reading `docs/agents/retro.md` plus a 23.7 kB
  context file, so this may be a silent early stop rather than a considered
  "nothing to propose". The job log carries no result text; the step summary
  was not read. The gate labels before the model job starts, so the retro does
  not come back to #873 on its own. Retry path, `docs/agents/retro.md:39-45`
  (`fabiandistler/agents@acbd1c9`): remove `retro:done` from #873 and dispatch
  `retro` by hand.
- **Session-bound scheduled check `trig_0159BdYMZ82Lzb9o2aTGk19Y`** ("Verify
  #763 during pr-review brownout") [read, 2026-11-20]: it fired 2026-11-16
  17:41:50 UTC with status FAILED and `ended_reason:
  auto_disabled_session_gone`, so the brownout verification never ran. No wiki
  page recorded the outcome before 2026-11-20; a `git grep brownout` in
  `docs/` found no result entry. Result recorded in
  [schedules](../schedules.md).
- Common pattern (2026-11-20, the chief-of-staff's inference, not read): each
  run's success was an artifact (a maintenance PR, a retro PR, a
  verification), each ended without it, and nothing in the repositories said
  so: no failed check, no Fix issue, no comment. The only signals sat outside
  the repos (a push notification, a FAILED status on a scheduled task), and
  two status fields read as success (`SUCCEEDED`, `is_error: false`). Each
  miss surfaced only in a later status sweep, one to four days on. Where a
  run's output is optional ("at most one" PR, a maintenance run that may find
  nothing due), "nothing to do" and "did nothing" look the same from outside.

- 2026-11-20, later the same day: repo-maintenance#174, merged as
  `fabiandistler/repo-maintenance@9a5c5e3`, covers the classifier outage for
  the repo-maintenance routine. On "gave no verdict (error)" a run keeps doing
  read-only steps and retries. After the 9th such answer in a row it stops
  with a `RUN FAILED` push
  ([2026-11-20 decisions](../decisions/2026-11-20-decisions.md)). That
  routine's bootstrap reads the `## Prompt` block from `main` at run start,
  so the rule is live from its next run [read: PR body]. The agents and
  dotfiles routines get the rule only once their stored prompts are switched
  to the bootstrap. That is a hand step, decided the same day, and was not
  read as done ([schedules](../schedules.md)). The PR also notes a gap: an
  outage during the bootstrap's own setup Bash calls is not covered [read].
- 2026-11-20, scheduled Actions runs [read: draft spec, F5, citing GitHub's
  "Events that trigger workflows" page, `schedule`]: they can be delayed
  under load and may be dropped. A dropped run leaves no failed run, so the
  Fix task cannot file it. This was one reason to keep the maintenance runs
  as routines
  ([parked spec, findings](../specs/2026-11-20-maintenance-runs-on-actions-draft-findings.md)).
  Late starts in agents: [schedules](../schedules.md), 2026-11-20.

Related: [implementer-queue page guard](implementer-queue-page-guard.md) (a
failure the Fix task does not watch),
[2026-11-14 decisions](../decisions/2026-11-14-decisions.md).
