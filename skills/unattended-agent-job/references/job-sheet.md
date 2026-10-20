# Job sheet

One sheet per unattended job, kept next to the job definition. Each row asks
one question and links the convention that answers it; the convention is the
single source, this sheet only makes sure the question gets asked for *this*
job. A blank cell is a finding.

## Template

| Question | This job | Convention |
|---|---|---|
| Trigger: schedule, API, event? Who can fire it, and with which input? | | — |
| Rung on the ladder (0–3) and the next change | | SKILL.md step 2 |
| Writes and the credential of each step | | SKILL.md step 1; *Agent pipelines* fragment, *Writing into external systems* |
| Output contract file and validator call | | `assets/outputs.schema.json`, `scripts/validate_patch.py` |
| Allowlist and protected paths, and where the allowlist file lives | | *Agent pipelines* fragment (allowlist, self-edits) |
| "Already done" state and where the pre-write re-check runs | | *Agent pipelines* fragment (re-check, state file) |
| Pre-flight probes | | SKILL.md step 6 |
| Hard spend stop at the provider, timeout, worst case (TPM × max minutes × price) | | spend-stop line, [#464](https://github.com/fabiandistler/agents/issues/464) |
| Untrusted inputs reaching the prompt (issue bodies, comments, fetched pages, fire payloads) and how they are stripped | | *Agent pipelines* fragment, untrusted-text line, [#489](https://github.com/fabiandistler/agents/issues/489) |
| Database access: dedicated user, grants on approved views only | | DB-grant line, [#456](https://github.com/fabiandistler/agents/issues/456) |
| Runner isolation: can the LLM step read secrets meant for later steps (procfs, sudo, shared env)? | | `references/platform-notes.md` |

Where the conventions live: the *Agent pipelines* fragment is
`instructions/80-agent-pipelines.md` in this catalogue. The spend-stop and
DB-grant lines are in `references/ai-engineering-conventions.md` of
`members/llm-application-engineering/SKILL.md`, read via the `ai-ml` router
(sections *Serving & architecture* and *Guardrails & security*).

## Filled example: this catalogue's weekly skill audit

As of 2026-10-20, from `docs/agents/skill-audit.md`.

| Question | This job |
|---|---|
| Trigger | Claude Code scheduled task, weekly; a manual **Run now** repeats the same slice |
| Rung | 1: the session itself creates the label, rewrites the issue body, pushes `claude/skill-audit-<date>` and opens the PR; a human merges. Next change: the session writes `outputs/` only, a model-free publisher performs the writes |
| Writes and credentials | issue + label + comment + push + PR, all through the owner's connected GitHub identity held by the LLM session |
| Output contract / validator | none; the 200-line diff budget and fix classes are prompt prose |
| Allowlist / protected | none outside the prompt |
| State and re-check | slice from ISO week (`scripts/skill_audit_select.py`); "skip while last week's PR is open" is a prose check, not a pre-write re-check |
| Pre-flight | `git fetch --shallow-since` in step 1 compensates the shallow clone; no abort on failure |
| Spend stop | subscription usage limits only |
| Untrusted inputs | fetched pages; skill files under review |
| Database | none |
| Runner isolation | Anthropic-managed cloud session; the connected GitHub identity is available to the LLM step |
