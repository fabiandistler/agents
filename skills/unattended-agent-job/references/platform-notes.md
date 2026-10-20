# Platform notes

Platform behaviour that decides where the credential split can sit. Each note
carries the date its source was read; recheck the source before relying on a
note older than three months. Next review: 2027-01-20.

## GitHub Actions

Split the job into two jobs. `agent` runs the LLM with `permissions:
contents: read` (plus nothing else) and uploads `outputs/` as an artifact;
`publish` declares `needs: agent`, holds the write permissions, downloads the
artifact, validates it, re-checks the entry condition, and writes. Secrets
the publisher needs are referenced only in `publish`. A workflow triggered by
comments or issue text runs on untrusted input: the job sheet's
untrusted-input row applies.

## GitHub Agentic Workflows (gh-aw) — read 2026-10-20

Ships rung 2/3 as *safe outputs*: "agents run read-only and request actions
via structured output, while separate permission-controlled jobs execute those
requests". Each output kind has a declared maximum (for example create-issue
max 1, add-comment max 1, PR review comments max 10), and credentials for
external targets stay in the safe-outputs job. Source:
<https://github.github.com/gh-aw/reference/safe-outputs/>. On gh-aw, map
`assets/outputs.schema.json` onto its safe-output declarations instead of
building a publisher.

## Claude Code scheduled tasks (formerly routines) — read 2026-10-20

Source: <https://code.claude.com/docs/en/routines>. The feature is in research
preview; recheck before relying on any of this.

- Triggers: schedule (minimum interval one hour), API (`/fire` with a
  per-task bearer token), GitHub events (pull request, release).
- A run is a full cloud session with no permission mode; it uses every tool of
  every included connector, writes included, without asking. All connected
  connectors are included by default: remove the ones the job does not need.
- Writes go out as the owner: commits, PRs and connector actions use the
  owner's linked accounts. Claude pushes to `claude/`-prefixed branches unless
  the prompt says otherwise; branch protection or rulesets are applied to the
  connected GitHub access, and a rule that access can bypass does not block
  the push.
- API `text` arrives wrapped as untrusted data; the saved prompt must opt in
  to acting on it.
- A green run status means the session exited without an infrastructure
  error, not that the work succeeded.
- Repositories are cloned fresh on every run, so "already done" state must
  live in the repository or a remote system, not the session.

Consequence for the ladder (inference, not from the source): the LLM session
holds the owner's GitHub identity, so a scheduled task alone tops out at
rung 1. To reach rung 2/3, have the task push only to its `claude/<job>-*`
branch under a ruleset the connected access cannot bypass, and let a
model-free GitHub Actions workflow on that branch validate and publish.

## Codex GitHub Action — read 2026-10-20

`safety-strategy` defaults to `drop-sudo`, which removes `sudo` before Codex
runs. `read-only` keeps Codex from changing files or using the network but
still runs with elevated privileges, so it is no isolation of secrets. Ask the
same question of any agent action: can the LLM process read secrets meant for
a later step? Source: <https://learn.chatgpt.com/docs/github-action>
(formerly developers.openai.com/codex/github-action).
