# 2026-11-13 — Triage decisions: reopen #783, queue issue, #769 split, YAML tickets in interactive sessions

Four decisions the user took during the
[2026-11-13 triage](../snapshots/2026-11-13-triage.md).

- **Decision (user, 2026-11-13, chief-of-staff session):** reopen #783
  (Fix task). GitHub had closed it as completed on the merge of PR #795,
  with no Fix-task code on main. Reopened 2026-11-13 (comment 6863813860);
  PR #795's body was reworded so the implementer claim no longer sees a
  closing PR. See
  [closing keyword in quoted text](../problems/closing-keyword-in-quotes.md).
- **Decision (user, 2026-11-13):** file an issue for a queue in front of
  the implementer, so that tickets stopped at capacity start when a run
  ends. Filed as #801 (`enhancement`, `ready-for-human`). Its finding: each
  at-capacity stop already starts an Opus session, because the claim runs
  inside the model step (`.github/workflows/implementer.yml:58-63` and
  `:121` at `fabiandistler/agents@0585e8e`). Until the queue exists, the
  chief-of-staff session sets the next `ready-for-agent` label by hand
  (order: [merge plan](../merge-plan.md), 2026-11-13 section).
- **Decision (user, 2026-11-13):** #769 is fixed in the scripts only
  (`scripts/issue_triage_policy.py` and `scripts/issue_triage.py`); its
  workflow-side part moves to #797. Brief: #769 comment 6864133803; note on
  #797: comment 6864136095.
- **Decision (user, 2026-11-13):** YAML-heavy tickets (#797, #793, #790,
  #767) are done in interactive `claude/*` sessions, not by the AFK
  implementer. Cloud sessions started 2026-11-13 20:33 UTC:
  - #797: `session_0154VwoYHq2bsPL8PPr9trEn`;
  - #767: `session_0154VwoXeFaip7yHhkMAXKQ5`.

  Related constraint (2026-11-11): the implementer's App token cannot write
  `.github/workflows/` ([new factory tasks](2026-11-11-new-factory-tasks.md)).

Related: [factory rollout](2026-11-11-factory-rollout.md).
