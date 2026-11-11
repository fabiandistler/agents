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
  known.

Related: [rollout](../decisions/2026-11-11-factory-rollout.md).
