# 2026-11-18 decisions

Decided by the maintainer on 2026-11-18:

- `PR_AUTO_MERGE` set to `true` at 15:21 UTC, step 5 of the PR review rollout (`docs/agents/pr-review-runbook.md`, Rollout). Until then the repository had no Actions variables (API check around 14:50 UTC). The ruleset `default` already required the five checks (see [2026-11-14 decisions](2026-11-14-decisions.md)), and `allow_auto_merge` was `true`.
- No issue for "high-risk zones block auto-merge whatever the `risk:` label says" (Thoughtworks Technology Radar Vol. 35, risk-tiered human oversight). At `fabiandistler/agents@cc99f54` the rule already holds. `scripts/pr_risk.py` `PATH_RULES` rates `.github/`, `install.sh`, and the hook and settings files high and `docs/adr/` medium. The path risk is a floor that the review can only raise (`scripts/pr_plan.py` `_effective_risk`), auto-merge needs `low`, and `risk:` labels are output only. All six merged `risk:low` pull requests up to that day (#757 to #833) changed only `docs/wiki/`.
- #877 (`## Other repos` in `AGENTS.md`): list all five repos in the public `AGENTS.md`, the private ones included.
- The pull request that adds this page is the live acceptance test for the bot's auto-merge (`docs/agents/pr-review-acceptance.md`, throwaway docs pull request).

Related: [2026-11-14 decisions](2026-11-14-decisions.md).
