# 2026-11-20 decisions

Decided by the maintainer on 2026-11-20, after the [2026-11-20 status sweep](../snapshots/2026-11-20-status.md). Times UTC; bare numbers are agents issues and PRs. Merge times and SHAs were read in the GitHub API during the wiki ingest that afternoon.

## Factory fixes

- #905 filed 09:15 (`ready-for-agent`): the one-page guard in `scripts/agent_run_capacity.py` fails implementer-queue `start-next` ([implementer-queue page guard](../problems/implementer-queue-page-guard.md)). Fixed by the implementer's PR #907 (`claude[bot]`), merged 10:49 as `fabiandistler/agents@68dcf08`.
- The Fix task watches `implementer-queue`: #908, merged 10:49 as `fabiandistler/agents@77f4ee8`.
- #909 filed 10:56 (`ready-for-human`): queue runs that the implementer's follow-up job dispatches with `GITHUB_TOKEN` still reach no Fix task. PR #910 was open for it when the maintainer decided; read later that day, it merged 12:11 as `fabiandistler/agents@8f96040` and closed #909.
- repo-maintenance#174 merged 11:24 as `fabiandistler/repo-maintenance@9a5c5e3`: the `## Prompt` blocks of both routine docs retry a tool call when the auto-mode check "gave no verdict (error)" and stop with a `RUN FAILED` push after the 9th such answer in a row. Its finding [read, PR body]: the `gh` risk did not hold. The old prompt implied deps-audit's Dependabot check would be blocked, but `gh api` REST calls go through the session proxy; only GraphQL (`gh pr`, `gh issue`) and the runners list are refused, and the scanner already reports the runners list `[not checked]`.

## Maintenance routines

- Pin Opus on the agents (`trig_016FpvZkZFm5tPdbFCrXebbT`) and dotfiles (`trig_01XtaNXwvNSQbiDAZJq2vBPV`) maintenance routines, and replace their stored direct prompts with the bootstrap prompt of repo-maintenance's `docs/agents/target-repo-maintenance-routine.md`. Evidence: [2026-11-20 maintenance cadence](../snapshots/2026-11-20-maintenance-cadence.md).
- Three-week test: dotfiles runs twice a week, Sundays and Wednesdays 01:36 UTC. Schedule and manual revert: [schedules](../schedules.md).
- The maintenance runs stay claude.ai routines (option B). Option A, moving them to GitHub Actions, is parked; its draft is the [parked spec](../specs/2026-11-20-maintenance-runs-on-actions-draft.md). Reasons:
  - The Claude App token is sandboxed to the current repository. `anthropics/claude-code-action@4fa93a8` exchanges the job's OIDC token without naming a repository (`src/github/token.ts:103-123`), and its docs say the token "is sandboxed to the current repository only" (`docs/faq.md:180-182`). So option A needs a new read credential for the private repo-maintenance in agents and dotfiles, and 12 tickets, 9 of which touch workflow files the implementer cannot write and so need interactive sessions or the maintainer ([findings](../specs/2026-11-20-maintenance-runs-on-actions-draft-findings.md), F1; [tickets](../specs/2026-11-20-maintenance-runs-on-actions-draft-tickets.md)).
  - Actions schedules can start late or be dropped without a failed run (spec F5; [runs without a trace](../problems/runs-without-trace.md)).
- A wrong claim, corrected the same day: the chief of staff first told the maintainer that ADR-0014's reason was probably obsolete. That reason says the Actions token cannot reach the private repo-maintenance without a personal access token (`docs/adr/0014-agent-runs-in-github-actions.md:45-47` at `fabiandistler/agents@8f96040`). Corrected on 2026-11-20: the fact holds, for the sandboxing reason above.
- The maintainer makes the routine changes by hand on each routine's page. Agents cannot: on 2026-11-20 `update_trigger` refused these routines because they were created via `http_api`. Whether the changes were applied was not read during this ingest.

Related: [schedules](../schedules.md), [2026-11-18 decisions](2026-11-18-decisions.md).
