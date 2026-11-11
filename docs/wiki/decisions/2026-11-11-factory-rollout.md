# 2026-11-11 — Roll the factory out to dotfiles and repo-maintenance

- **Decision (user, 2026-11-11, chief-of-staff session):** roll the
  software factory out to fabiandistler/dotfiles and
  fabiandistler/repo-maintenance.
- **Not chosen (2026-11-11):** lintrhelper and pypet.
- **How (decision recorded in #786, 2026-11-11):** each task becomes a
  reusable workflow (`workflow_call`) hosted in this repository, which
  calls the same workflows itself. Target repositories carry only thin
  caller workflows pinned to a commit SHA. Rollout waits until the brakes
  have merged (see [expansion order](2026-11-11-factory-expansion-order.md)).
- Tickets filed 2026-11-11:
  - Spec #786, with sub-issues #787–#790 and #792–#794 (ADR-0018, claim
    script, push guard, implementer extraction, PR review extraction,
    triage extraction, onboarding runbook and check script). All
    `ready-for-human`.
  - Onboarding: fabiandistler/dotfiles#61 and
    fabiandistler/repo-maintenance#153, each blocked by the brakes and the
    sub-issues.
- Problems found while planning (2026-11-11):
  - [private targets without rulesets](../problems/private-repos-no-rulesets.md);
  - [cross-repo App token exchange](../problems/cross-repo-token-exchange.md);
  - [cross-repo `Blocked by` URLs](../problems/cross-repo-blocked-by.md).
