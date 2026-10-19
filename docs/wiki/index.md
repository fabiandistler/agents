# Wiki

Historical record kept by the chief-of-staff sessions working on the goal
"improve and extend this repo". Every claim is dated or pinned to a commit;
nothing here describes the present. See [conventions](conventions.md).

## Goal and plan

- [goal](goal.md) — the long-running goal, its scope, and the ordering decision (improve before extend).
- [merge plan](merge-plan.md) — open PRs and their merge-order constraints.

## Decisions

- [2026-10-19 wiki location](decisions/2026-10-19-wiki-location.md) — why the wiki lives in `docs/wiki/`.

## Recurring problems

- [router cross-references](problems/router-cross-references.md) — skills naming router members as standalone skills; the main source of audit errors.
- [unrunnable commands in skills](problems/unrunnable-skill-commands.md) — shell snippets in SKILL.md that fail when an agent follows them.
- [unlinked PRs](problems/unlinked-prs.md) — merged work left its issue open; caused a wasted worker run.

## Snapshots

- [2026-10-19 backlog](snapshots/2026-10-19-backlog.md) — open issues, audit state, leverage ranking at session start.
- [2026-10-19 CI health](snapshots/2026-10-19-ci-health.md) — all runnable checks green; warn-only gaps and unverifiable steps.
- [2026-10-19 env gaps](snapshots/2026-10-19-env-gaps.md) — missing guardrails for agents, ranked.
