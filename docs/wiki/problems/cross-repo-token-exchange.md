# App token exchange from a cross-repo reusable workflow

- 2026-11-11: the rollout runs claude-code-action inside a reusable
  workflow hosted in agents and called from another repository.
  anthropics/claude-code-action#443 (open) reports a 401 "Workflow
  validation failed" from the token exchange in exactly that setup. A
  backend fix was announced in 2025-08, and later comments report related
  failures. Source: #786, "Not verified" item 1, which cites the upstream
  issue; the upstream issue was not readable from this session.
- 2026-11-11: #786 says only a live run in a target repository settles it,
  and ADR-0018 (#787) is to record a fallback. The onboarding issues
  (dotfiles#61, repo-maintenance#153) make the first `ready-for-agent`
  ticket in each target a trivial one, as the probe.
- 2026-11-11: a probe was started the same day. Result: pending, not yet
  known. *Superseded 2026-11-12, see below.*
- 2026-11-12 (supersedes the 2026-11-11 "pending" claim): the probe ran.
  The first caller run (dotfiles 43096185342) never started in the
  2026-11-11 Actions stall ([runs stuck in `queued`](actions-runs-stuck-queued.md));
  dotfiles#62 then moved the caller to `main` with only
  `workflow_dispatch`, because the exchange validates the calling workflow
  against the caller's default branch (#796, dotfiles#62). Run
  fabiandistler/dotfiles 43209973289 (job 131154816342), a
  `workflow_dispatch` on dotfiles `main`, called
  `fabiandistler/agents@cacc67a` (`.github/workflows/token-probe.yml`). Its
  log shows "OIDC token successfully obtained" and "App token successfully
  obtained". So the 401 from anthropics/claude-code-action#443 did not
  occur for a private caller on its default branch, with the App installed
  and the secret set.
- 2026-11-12, not verified: the App token's rights in the target. The
  probe's one `gh api` call was refused by a permission rule
  (`permission_denials_count: 1` in the job log; dotfiles#63 names the
  call), so the run shows nothing about what the token may do there. The
  first implementer run in dotfiles checks this (#790, dotfiles#61).
- 2026-11-12: dotfiles#63 (open) removes the probe caller, which pins a
  commit of the closed, unmerged #796.

Related: [rollout](../decisions/2026-11-11-factory-rollout.md).
