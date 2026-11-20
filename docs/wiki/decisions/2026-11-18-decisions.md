# 2026-11-18 decisions

Decided by the maintainer on 2026-11-18:

- `PR_AUTO_MERGE` set to `true` at 15:21 UTC, step 5 of the PR review rollout (`docs/agents/pr-review-runbook.md`, Rollout). Until then the repository had no Actions variables (API check around 14:50 UTC). The ruleset `default` already required the five checks (see [2026-11-14 decisions](2026-11-14-decisions.md)), and `allow_auto_merge` was `true`.
- No issue for "high-risk zones block auto-merge whatever the `risk:` label says" (Thoughtworks Technology Radar Vol. 35, risk-tiered human oversight). At `fabiandistler/agents@cc99f54` the rule already holds. `scripts/pr_risk.py` `PATH_RULES` rates `.github/`, `install.sh`, and the hook and settings files high and `docs/adr/` medium. The path risk is a floor that the review can only raise (`scripts/pr_plan.py` `_effective_risk`), auto-merge needs `low`, and `risk:` labels are output only. All six merged `risk:low` pull requests up to that day (#757 to #833) changed only `docs/wiki/`.
- #877 (`## Other repos` in `AGENTS.md`): list all five repos in the public `AGENTS.md`, the private ones included.
- The pull request that adds this page is the live acceptance test for the bot's auto-merge (`docs/agents/pr-review-acceptance.md`, throwaway docs pull request).

## 2026-11-20 outcomes

Read in the [2026-11-20 status sweep](../snapshots/2026-11-20-status.md).

- 2026-11-20 [read]: the auto-merge acceptance test passed. `github-actions[bot]` merged #878, the pull request that added this page, on 2026-11-18 15:30:43 UTC.
- 2026-11-20 [read]: #877 closed via PR #879 (`claude[bot]`), merged 2026-11-18 17:48 UTC. Read during the wiki ingest the same day: the PR's commit `fabiandistler/agents@062e880` lists two repos, repo-maintenance and dotfiles, and `AGENTS.md:17-25` at `fabiandistler/agents@acbd1c9` still does, not all five as decided above.
- 2026-11-20 (extends the count of `risk:low` pull requests) [read]: three more `risk:low` pull requests were bot-merged since: #878 (2026-11-18), #902 and #904 (2026-11-19). [inferred] Their titles say `docs(wiki)`; their file lists were not checked.

Related: [2026-11-14 decisions](2026-11-14-decisions.md).
