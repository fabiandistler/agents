# implementer-queue `start-next` fails on the one-page guard

- 2026-11-18 and -19 [read, 2026-11-20 sweep]: four implementer-queue runs
  failed in job `start-next`, step "Start the next waiting issue", each with
  the outcome
  `{"outcome": "failed", "reason": "GitHub API listed more items than one page holds for /repos/fabiandistler/agents/actions/workflows/implementer.yml/runs"}`:
  - 44387046433, 2026-11-18 20:04 UTC (`workflow_run`);
  - 44475342609, 2026-11-19 06:52 UTC;
  - 44477947672, 2026-11-19 07:13 UTC;
  - 44480055480, 2026-11-19 07:29 UTC.
- Where it is raised, at `fabiandistler/agents@acbd1c9` [read]: `_single_page`
  in `scripts/agent_run_capacity.py:30-41` fails when a listing's
  `total_count` exceeds the items on the page. `working_runs`
  (`scripts/agent_run_capacity.py:114-125`) reaches it at line 120, listing
  the implementer's runs with `status=in_progress` and `per_page` 100
  (`PER_PAGE`, `scripts/pr_github_client.py:27`). The queue's `start_next`
  calls `working_runs` (`scripts/implementer_queue.py:219`).
- 2026-11-20 [read]: the same listing returned `total_count` 0.
- Cause unknown as of 2026-11-20. [inferred] More than 100 in-progress
  implementer runs is implausible under `MAX_WORKING_RUNS=1`; a `total_count`
  above the returned items for a status-filtered listing is the likelier
  explanation. The failures coincide with the Handoff 2/5–5/5 tickets
  (#887–#890) waiting in line. The past API response cannot be replayed, and
  the logs carry only the outcome line.
- Effect (2026-11-20): the tickets still landed, as PRs #892–#895 [read].
  [inferred] The bug is latent: it bites whenever an issue waits in the queue.
  *Superseded 2026-11-20: fixed by #907, see below.*
- Nobody was told (2026-11-20): `.github/workflows/fix-task.yml:16`
  (`fabiandistler/agents@acbd1c9`) watches `implementer`, `skill-audit`,
  `issue-triage`, `pr-review`, `rework` and `retro`, not `implementer-queue`
  [read], so the failures filed no Fix issue [inferred]. The comment at
  `fix-task.yml:9-11` says the list equals `WATCHED_WORKFLOWS` in
  `scripts/factory_failure_policy.py` [read]. An issue search for "one page"
  found no tracking issue [read]; none was filed as of 2026-11-20.
  *Superseded the same day: #905, #908 and #909, see below.*
- Reach (2026-11-20): `runs_working_ahead`
  (`scripts/agent_run_capacity.py:93`, same commit) also goes through
  `working_runs`; `scripts/rework_gate.py:173` calls it, and so does
  `scripts/implementer_claim.py:353` via `scripts/implementer_capacity.py:23`
  [read]. [inferred] So the guard can stop rework and the implementer's claim
  too. Rework since 2026-11-17: 9 successes, 30 skips, no failure [read].
- Where a fix belongs (2026-11-20): in the shared module
  `scripts/agent_run_capacity.py`, not in the queue, per the bug-fixing rule
  (`.claude/rules/agents-55-bug-fixing.md`).

- 2026-11-20, later the same day [read: issues, PR bodies, merge commits]:
  - #905, filed by the maintainer at 09:15 UTC (`ready-for-agent`), lists
    every caller of `_single_page`. Its hypothesis is unverified: the
    status-filtered listing's `total_count` may not match its array while an
    implementer run is ending.
  - Fixed: the implementer's PR #907, merged 10:49 UTC as
    `fabiandistler/agents@68dcf08`, closed #905. The fix sits in the shared
    helper only, which is now `_all_pages`. It reads page after page and stops
    at `total_count` items or at a short or empty page. So a `total_count`
    that overstates the listing returns the items that were listed. Every
    caller keeps its signature. The cause is still unknown.
  - #908, merged 10:49 UTC as `fabiandistler/agents@77f4ee8`:
    `implementer-queue` joins the `workflow_run` list in
    `.github/workflows/fix-task.yml` and `WATCHED_WORKFLOWS` in
    `scripts/factory_failure_policy.py`. Only run 44387046433 of the four
    started through `workflow_run`. The other three were `workflow_dispatch`
    runs by `github-actions[bot]`: the implementer's follow-up job dispatched
    them with `GITHUB_TOKEN`, so they start no `workflow_run` (#858).
  - Dispatch gap: #909, filed `ready-for-human` at 10:56 UTC, covers those
    token-dispatched runs. PR #910 (opened 11:59 UTC, merged 12:11 UTC as
    `fabiandistler/agents@8f96040`) closed it. It adds a `report-failure` job
    and a `fix_task_workflow` input to
    `.github/workflows/factory-implementer-queue.yml`, and
    `implementer-queue.yml` passes `fix-task.yml`.
  - Decisions: [2026-11-20 decisions](../decisions/2026-11-20-decisions.md).

Related: [2026-11-20 status sweep](../snapshots/2026-11-20-status.md),
[runs without a trace](runs-without-trace.md),
[runs stuck in `queued`](actions-runs-stuck-queued.md).
