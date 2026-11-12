# Wiki

Historical record kept by the chief-of-staff sessions working on the goal
"improve and extend this repo". Every claim is dated or pinned to a commit;
nothing here describes the present. See [conventions](conventions.md).

## Goal and plan

- [goal](goal.md) — the long-running goal, its scope, and the ordering decision (improve before extend).
- [merge plan](merge-plan.md) — open PRs and their merge-order constraints.
- [schedules](schedules.md) — recurring scheduled tasks and their setup.

## Decisions

- [2026-10-19 wiki location](decisions/2026-10-19-wiki-location.md) — why the wiki lives in `docs/wiki/`.
- [2026-10-19 router references](decisions/2026-10-19-router-references.md) — option A: rewrite to router form, enforce in CI.
- [2026-11-11 factory expansion order](decisions/2026-11-11-factory-expansion-order.md) — brakes (#763, #764, #770) first, then new tasks, then rollout.
- [2026-11-11 new factory tasks](decisions/2026-11-11-new-factory-tasks.md) — Rework #782, Fix #783, Retro #784 filed `ready-for-human`.
- [2026-11-11 factory rollout](decisions/2026-11-11-factory-rollout.md) — dotfiles and repo-maintenance via reusable workflows, spec #786.

## Recurring problems

- [router cross-references](problems/router-cross-references.md) — skills naming router members as standalone skills; the main source of audit errors.
- [unrunnable commands in skills](problems/unrunnable-skill-commands.md) — shell snippets in SKILL.md that fail when an agent follows them.
- [unlinked PRs](problems/unlinked-prs.md) — merged work left its issue open; caused a wasted worker run.
- [Dependabot on private repos](problems/dependabot-private-repos.md) — update jobs wait for a `dependabot`-labelled runner and are cancelled after 24 h.
- [private repos without rulesets](problems/private-repos-no-rulesets.md) — rollout targets cannot require checks; weaker brakes, push guard #789.
- [cross-repo token exchange](problems/cross-repo-token-exchange.md) — claude-code-action#443 may break the App token in a called workflow; 2026-11-12 probe: the exchange works, token rights unverified.
- [Actions runs stuck in `queued`](problems/actions-runs-stuck-queued.md) — 2026-11-11 stall during GitHub incidents; runs with zero jobs, cancel refused; fresh runs via "Update branch".
- [cross-repo `Blocked by` URLs](problems/cross-repo-blocked-by.md) — fail closed after #785 and stop the implementer until removed.

## Snapshots

- [2026-10-19 backlog](snapshots/2026-10-19-backlog.md) — open issues, audit state, leverage ranking at session start.
- [2026-10-19 CI health](snapshots/2026-10-19-ci-health.md) — all runnable checks green; warn-only gaps and unverifiable steps.
- [2026-10-19 env gaps](snapshots/2026-10-19-env-gaps.md) — missing guardrails for agents, ranked.
- [2026-10-20 skill candidates](snapshots/2026-10-20-skill-candidates.md) — ranked proposals for new skills.
- [2026-11-10 ready-for-human](snapshots/2026-11-10-ready-for-human.md) — four human issues across three repos and their recommended order.
