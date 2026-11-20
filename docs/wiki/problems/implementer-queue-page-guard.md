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
- Nobody was told (2026-11-20): `.github/workflows/fix-task.yml:16`
  (`fabiandistler/agents@acbd1c9`) watches `implementer`, `skill-audit`,
  `issue-triage`, `pr-review`, `rework` and `retro`, not `implementer-queue`
  [read], so the failures filed no Fix issue [inferred]. The comment at
  `fix-task.yml:9-11` says the list equals `WATCHED_WORKFLOWS` in
  `scripts/factory_failure_policy.py` [read]. An issue search for "one page"
  found no tracking issue [read]; none was filed as of 2026-11-20.
- Reach (2026-11-20): `runs_working_ahead`
  (`scripts/agent_run_capacity.py:93`, same commit) also goes through
  `working_runs`; `scripts/rework_gate.py:173` calls it, and so does
  `scripts/implementer_claim.py:353` via `scripts/implementer_capacity.py:23`
  [read]. [inferred] So the guard can stop rework and the implementer's claim
  too. Rework since 2026-11-17: 9 successes, 30 skips, no failure [read].
- Where a fix belongs (2026-11-20): in the shared module
  `scripts/agent_run_capacity.py`, not in the queue, per the bug-fixing rule
  (`.claude/rules/agents-55-bug-fixing.md`).

Related: [2026-11-20 status sweep](../snapshots/2026-11-20-status.md),
[runs without a trace](runs-without-trace.md),
[runs stuck in `queued`](actions-runs-stuck-queued.md).
