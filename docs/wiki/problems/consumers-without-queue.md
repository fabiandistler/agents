# Consumers without an implementer-queue caller

Issues the claim parks "in the implementer queue" in repo-maintenance and
dotfiles never start, because neither repo has a queue caller.

- 2026-11-25 [reported]: the maintainer filed repo-maintenance#205 ("issue
  waiting to be fixed never get picked up"), pointing at repo-maintenance#200.
  The repo's triage bot set `needs-info`: it cannot read the factory code in
  agents, so it could not trace the defect.
- 2026-11-25 [read, analyst sweep 06:20–06:40 UTC]: the shared claim posts
  `CAPACITY_COMMENT` ("keeps `ready-for-agent` and waits in the implementer
  queue") when it is blocked or at capacity, without checking for a queue
  (`scripts/implementer_claim.py:125-133,348-356`, prompt step
  `.github/workflows/factory-implementer.yml:234`, `fabiandistler/agents@8afe860`).
  Its `queue_workflow` input (`factory-implementer.yml:55-58`) is read only by
  the follow-up job (#863).
- 2026-11-25 [read]: `fabiandistler/repo-maintenance@228991b` and
  `fabiandistler/dotfiles@d00e8c6` have no `.github/workflows/implementer-queue.yml`
  and pass neither `queue_workflow` nor `fix_task_workflow`. Their follow-up job
  was skipped in every run that was read. In agents, the queue starts through
  `workflow_run` when an implementer run ends, through `issues: closed`, and on an
  hourly schedule (`.github/workflows/implementer-queue.yml:17-26`, `fabiandistler/agents@f5c2f16`).
- How it happened [read]: the consumers' first pin, 587c956 (2026-11-14),
  removed the label for blocked and at-capacity issues. The bump to f52621d on
  2026-11-15 (repo-maintenance 1c35050, dotfiles fe1ae13) brought the "keeps the
  label and waits" text, 32 minutes before agents#856 merged the queue
  workflows. No queue caller was rolled out with it. The agents onboarding
  check (`scripts/factory_onboarding_check.py:50-57`, `fabiandistler/agents@f5c2f16`)
  and both consumers' caller tests leave out the queue. dotfiles' test requires
  the callers to equal a list of six without it.
- Stuck on 2026-11-25 [read]: repo-maintenance#200 (since 2026-11-24 12:16 UTC,
  parked behind #201's run 45391843568), dotfiles#79 and #80 (since 06:22 UTC,
  parked behind #78's run 45559994647).
- Manual restart [read]: re-adding a label that is still present fires no
  event (`implementer_claim.py:244`, `fabiandistler/agents@8afe860`). Remove and re-add
  `ready-for-agent`, or dispatch `implementer.yml` with `issue`.
- Doc drift [read]: `docs/agents/triage-labels.md:25` in repo-maintenance
  still said the issue loses the label (true only at 587c956). Both consumers
  linked `#implementer-claim` in agents' `triage-labels.md`, a heading that
  no longer exists.
- Pin lag [read]: the consumers' pin 8afe860 (2026-11-19) predates #907
  (paging fix, 68dcf08), #908 and #910 (`fix_task_workflow`, 8f96040). A queue
  caller at that pin would have carried the
  [page-guard bug](implementer-queue-page-guard.md).

## Fix (2026-11-25)

- Maintainer chose option 2: queue callers in both consumers *and* a
  fail-closed claim in agents, so no future consumer inherits the gap. See
  [2026-11-25 decisions](../decisions/2026-11-25-decisions.md).
- PRs: agents#953 (opened 2026-11-25, head 497e2c4; `require_active_queue` in
  `scripts/implementer_waiting.py` GETs `actions/workflows/<queue_workflow>` on
  every claim and fails the run on a 404 or a state other than `active`; with no
  `queue_workflow`, blocked and at-capacity drop `ready-for-agent` and say when
  to re-add it; the onboarding check requires a queue caller; the 5000-token
  hook moved the input tables to `docs/agents/factory-inputs.md`;
  `check_all.sh` 25/25 [read, subagent report]); repo-maintenance#206 (opened 2026-11-25, `Closes #205`;
  pin f5c2f16 on all seven callers, queue caller, guard red on both conditions
  then green, baseline 8/8 locally; it split `tests/test_factory_callers.py`
  into `tests/test_factory_caller_inputs.py` to stay under the 5000-token hook
  limit; a GET-only dry run of agents' `start_next` at f5c2f16 would dispatch
  #200 [read, subagent report]); dotfiles#82 (opened 2026-11-25; pin
  f5c2f16 for every caller, queue caller, guard test red twice then green, CI
  green on 929cf62; #79/#80 still pass the contract check at f5c2f16 [read,
  subagent report]).
- 2026-11-25 [read, subagent report]: locally, 15 of 39 dotfiles Bats tests
  fail on unchanged main as well, each with `rm: command not found`: the cloud
  session's `rm` guard has no real `rm` on the tests' restricted PATH. The
  subagent pushed with `SKIP=bats`; the CI Bats job passed. No issue yet.

## Open (2026-11-25)

- agents#953 checks the queue on *every* claim, not only when it parks. A
  disabled queue then fails runs that have free capacity too. GitHub disables
  scheduled workflows in a public repository after 60 days without activity
  (docs.github.com, "Disabling and enabling a workflow", read 2026-11-25), and
  the queue has a schedule. agents is public. Raised with the maintainer; open.
- Three files are close to the 20 KB limit after #953 (subagent report):
  `docs/agents/factory-onboarding.md`, `.github/workflows/factory-implementer.yml`
  and `docs/factory/architecture.md`. The next edit to any of them will force
  a split. Two of the three fix subagents hit the 5000-token hook and split
  files they were not asked to touch.

- Triage in a consumer repo said it "can't read" agents, so it could not
  diagnose a bug that lives in the factory, and parked #205 as `needs-info`
  [read, #205 triage comment]. agents is public (REST `private=false`, read
  2026-11-25). [inferred] The limit is the triage run's tooling: its App token
  is sandboxed to the current repository
  ([cross-repo token exchange](cross-repo-token-exchange.md)), not the repo's
  visibility. No issue yet.

Related: [implementer-queue page guard](implementer-queue-page-guard.md),
[no agent consumer outside agents](no-agent-consumer-outside-agents.md),
[2026-11-11 factory rollout](../decisions/2026-11-11-factory-rollout.md).
