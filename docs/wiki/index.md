# Wiki

Historical record kept by the chief-of-staff sessions working on the goal
"improve and extend this repo". Every claim is dated or pinned to a commit;
nothing here describes the present. See [conventions](conventions.md).

## Goal and plan

- [goal](goal.md) — the long-running goal, its scope, and the ordering decision (improve before extend).
- [merge plan](merge-plan.md) — open PRs and their merge-order constraints; on 2026-11-20 none open; on 2026-11-25 three queue-fix PRs, no order.
- [schedules](schedules.md) — recurring scheduled tasks and their setup; the #763 brownout check failed (read 2026-11-20); the three maintenance routines as read 2026-11-20, agents cannot edit them (`http_api`), the dotfiles test reverts by hand before 2026-12-16, evaluation task due 2026-12-10.

## Decisions

- [2026-10-19 wiki location](decisions/2026-10-19-wiki-location.md) — why the wiki lives in `docs/wiki/`.
- [2026-10-19 router references](decisions/2026-10-19-router-references.md) — option A: rewrite to router form, enforce in CI.
- [2026-11-11 factory expansion order](decisions/2026-11-11-factory-expansion-order.md) — brakes (#763, #764, #770) first, then new tasks, then rollout.
- [2026-11-11 new factory tasks](decisions/2026-11-11-new-factory-tasks.md) — Rework (#782), Fix (#783), Retro (#784) filed `ready-for-human`.
- [2026-11-11 factory rollout](decisions/2026-11-11-factory-rollout.md) — dotfiles and repo-maintenance via reusable workflows, spec #786.
- [2026-11-14 decisions](decisions/2026-11-14-decisions.md) — #802, #822, #823 option 1; repo-maintenance#150; YAML tickets stay interactive; #764 done.
- [2026-11-13 triage decisions](decisions/2026-11-13-triage-decisions.md) — reopen #783, queue issue #801, #769 script-only, YAML tickets in interactive sessions.
- [2026-11-18 decisions](decisions/2026-11-18-decisions.md) — `PR_AUTO_MERGE=true`; high-risk zones already in `pr_risk.py`, no issue; #877 lists all repos.
- [2026-11-19 tools decisions](decisions/2026-11-19-tools-decisions.md) — tools gallery: deploy gate first, line limit reframed, fix high+med, skill rules, one branch per package.
- [2026-11-25 decisions](decisions/2026-11-25-decisions.md) — repo-maintenance#205: option 2, queue callers in both consumers plus a claim that promises the queue only when one is configured; queue check only where the claim parks (option B).
- [2026-11-20 decisions](decisions/2026-11-20-decisions.md) — #905/#907, #908, #909/#910, repo-maintenance#174; Opus and bootstrap on the agents and dotfiles routines; dotfiles twice a week for three weeks; maintenance stays in routines (option B); routine edits by hand.

## Recurring problems

- [router cross-references](problems/router-cross-references.md) — skills naming router members as standalone skills; the main source of audit errors.
- [unrunnable commands in skills](problems/unrunnable-skill-commands.md) — shell snippets in SKILL.md that fail when an agent follows them.
- [unlinked PRs](problems/unlinked-prs.md) — merged work left its issue open; caused a wasted worker run.
- [Dependabot on private repos](problems/dependabot-private-repos.md) — update jobs wait for a `dependabot`-labelled runner and are cancelled after 24 h; fixed in dotfiles and repo-maintenance on 2026-11-14 (read 2026-11-20).
- [private repos without rulesets](problems/private-repos-no-rulesets.md) — rollout targets cannot require checks; weaker brakes, push guard #789.
- [cross-repo token exchange](problems/cross-repo-token-exchange.md) — claude-code-action#443 may break the App token in a called workflow; 2026-11-12 probe: the exchange works, token rights unverified; *superseded* 2026-11-20: the App token is sandboxed to the current repository (claude-code-action `4fa93a8`, ADR-0019).
- [Actions runs stuck in `queued`](problems/actions-runs-stuck-queued.md) — 2026-11-11 stall during GitHub incidents; runs with zero jobs, cancel refused; fresh runs via "Update branch"; 28 left in agents and 5 in dotfiles on 2026-11-20.
- [cross-repo `Blocked by` URLs](problems/cross-repo-blocked-by.md) — fail closed after #785 and stop the implementer until removed.
- [closing keyword in quoted text](problems/closing-keyword-in-quotes.md) — a quoted task list in PR #795 made GitHub mark #783 completed; the implementer claim reads the same body; check gap #802.
- [no agent consumer outside agents](problems/no-agent-consumer-outside-agents.md) — no implementer workflow and no enabled sweep in repo-maintenance and dotfiles (2026-11-13); *superseded*: callers landed 2026-11-14 (read 2026-11-20).
- [implementer lint rounds](problems/implementer-lint-rounds.md) — 2026-11-13 retro: the stop rule spent three rounds on prek lint; follow-ups #806–#808.
- [shared usage limit](problems/shared-usage-limit.md) — implementer, chief-of-staff subagents and cloud sessions share one 5-hour budget; #782 run lost on 2026-11-13.
- [implementer write limits](problems/implementer-write-limits.md) — no writes to `.github/workflows/`, `.claude/`, `.pre-commit-config.yaml`; Rework/Retro inactive until YAML is committed.
- [missing pull_request runs](problems/missing-pull-request-runs.md) — #826: no `pull_request` run, so required `secrets` never reported (2026-11-14).
- [review model inputs](problems/review-model-inputs.md) — review saw no rebuttals or briefs and stripped HTML comments; #822/#823.
- [dry run in the review's concurrency group](problems/dry-run-cancels-review.md) — a manual dry run shares `pr-review-<n>` and can cancel a review (2026-11-18); fix #882.
- [tools gallery had no checks](problems/tools-no-checks.md) — `tools` deployed straight to Pages; data-workflow broken since 2026-04-19, XSS; smoke suite tools#17 (2026-11-19).
- [subagent tool overhead](problems/subagent-tool-overhead.md) — ~92k tokens of unused tool definitions per subagent, 45–57 % of its cost (retro 2026-11-19); three browser-worker runs on 2026-11-20 reported 119k–186k, not like-for-like, starting context unmeasured; *superseded* 2026-11-20: start context ~14.0k for browser-worker vs 82.5k and 83.4k for general-purpose.
- [Playwright revision mismatch](problems/playwright-revision-mismatch.md) — cloud image Chromium ≠ Python Playwright's; use `--browser-channel chrome` (2026-11-19).
- [fix-agent test time](problems/fix-agent-test-time.md) — fix runs spent most time on full-suite reruns; `-k` trap fixed, xdist in CI (2026-11-19).
- [implementer-queue page guard](problems/implementer-queue-page-guard.md) — four queue runs failed on the one-page guard in `agent_run_capacity.py` (2026-11-18/19); cause unknown, the Fix task does not watch the queue, no issue (2026-11-20); *superseded* the same day: #905 fixed by #907, the queue's failures reach the Fix task (#908, #910).
- [runs without a trace](problems/runs-without-trace.md) — the 2026-11-16 maintenance run, the retro on PR #873 and the #763 check ended with no artifact and no trace in the repos; status fields read success (2026-11-20); repo-maintenance#174 retries the classifier outage, agents and dotfiles only after their bootstrap switch; dropped Actions schedules leave no failed run.
- [listing-tool cost](problems/listing-tool-cost.md) — on 2026-11-20 `list_triggers` returned 34 stored prompts (+101k tokens) and `list_pull_requests` 8 pages (+120k); use `get_trigger` with known ids and one `gh api search/issues` query; an `analyst` agent type is planned, PR pending.
- [consumers without a queue caller](problems/consumers-without-queue.md) — repo-maintenance and dotfiles parked issues "in the queue" with no queue caller since 2026-11-15; #200, dotfiles#79/#80 stuck on 2026-11-25; fixes agents#953, repo-maintenance#206, dotfiles#82.
- [rm guard and restricted PATH](problems/rm-guard-restricted-path.md) — Claude Code's `rm` guard fails 15 dotfiles Bats tests locally with a fake `command not found`; no repo fix, CI passes (2026-11-25).

## User preferences

- [dictation](preferences/dictation.md) — a dictated "dort Files" meant dotfiles; ask before re-scoping when a phrase looks like a garbled repo or tool name (2026-11-20).

## Parked specs

- [2026-11-20 maintenance runs on Actions](specs/2026-11-20-maintenance-runs-on-actions-draft.md) — parked draft of option A, never filed; overview, problem, solution, user stories.
  - [decisions](specs/2026-11-20-maintenance-runs-on-actions-draft-decisions.md) — its implementation and testing decisions, out of scope.
  - [findings](specs/2026-11-20-maintenance-runs-on-actions-draft-findings.md) — findings F1–F5 (App token sandboxed; dropped schedules), risks, test seams.
  - [tickets](specs/2026-11-20-maintenance-runs-on-actions-draft-tickets.md) — open questions and the 12-ticket sketch.

## Snapshots

- [2026-10-19 backlog](snapshots/2026-10-19-backlog.md) — open issues, audit state, leverage ranking at session start.
- [2026-10-19 CI health](snapshots/2026-10-19-ci-health.md) — all runnable checks green; warn-only gaps and unverifiable steps.
- [2026-10-19 env gaps](snapshots/2026-10-19-env-gaps.md) — missing guardrails for agents, ranked.
- [2026-10-20 skill candidates](snapshots/2026-10-20-skill-candidates.md) — ranked proposals for new skills.
- [2026-11-10 ready-for-human](snapshots/2026-11-10-ready-for-human.md) — four human issues across three repos and their recommended order.
- [2026-11-13 triage](snapshots/2026-11-13-triage.md) — verdicts on all open issues in three repos, the agent queue order, manual steps with deadlines; follow-up 2026-11-20.
- [2026-11-19 tools audit](snapshots/2026-11-19-tools-audit.md) — 13 files, 104 bugs, 94 rule violations; issues tools#11–#16.
- [2026-11-20 status](snapshots/2026-11-20-status.md) — agents, repo-maintenance, dotfiles: human items with deadlines 2026-11-22 to 2026-12-02, broken items, no agent work queued.
- [2026-11-20 maintenance cadence](snapshots/2026-11-20-maintenance-cadence.md) — capacity 1 slot a week against demand 2.2–3.4 runs, yield per job, cost per run by model, five levers.
- [2026-11-25 retro of #953](snapshots/2026-11-25-retro-953.md) — issues #954–#958 from the retro, plus #959 (triage cannot read the factory) and #960 (partial review: base-content cap in path order).
