# 2026-10-19 — Router members are never referenced as standalone skills

- **Decision (user, 2026-10-19):** option A. References to router members
  are rewritten to the router form AGENTS.md prescribes, and a CI check
  enforces it (wired into `scripts/check_all.sh`).
- **Rejected:** B, legalising the pattern — Codex cannot invoke members, so
  such references are dead outside Claude.
- Work: branch `claude/router-cross-refs`, refs #466.

Related: [router cross-references](../problems/router-cross-references.md).
