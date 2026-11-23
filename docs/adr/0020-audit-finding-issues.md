# ADR-0020: Audit finding issues become implementer contracts once a person releases them

## Status

Accepted (2026-11-23).

Amended 2026-11-23 after the review of #946: the release now needs write
access, not only a `User` actor. The adder's base role comes from the
collaborator permission endpoint (`admin` or `write`; it reports triage as
`read`), which a `GITHUB_TOKEN` can read with its implicit metadata scope.

## Context

The skill audit ([ADR-0014](0014-agent-runs-in-github-actions.md),
`docs/agents/skill-audit.md`) fixes only mechanical findings itself. Every
other finding stays in the rolling `skill-audit` issue for a person. On
2026-11-23 that issue (#466) held 43 `warn` and 54 `nit` findings, some
carried over since October, and no task worked them off; one manual sweep
(#560, 2026-10-21) was the only one.

The implementer could work them off, but it does not fit the rolling issue.
It builds one issue into one pull request that closes it; #466 spans about
20 skills and must stay open across runs. When #452 was closed, its findings
were lost.

The audit runs as the Claude GitHub App, so its issues are authored by
`claude[bot]` with the association `CONTRIBUTOR`. The implementer takes only
text by owners, members and collaborators as its contract
(`scripts/implementer_contract.py`), so it would stop every such issue with
`no-contract`. The implementer queue dispatches any open issue labelled
`ready-for-agent`, whoever added the label.

## Decision

1. The audit keeps one issue per skill, labelled `audit-finding` and titled
   `Skill audit: <skill>`, for each skill with an open `error` or `warn`
   finding outside its description. The body lists the skill's open findings,
   nits included, in the format the runbook gives.
2. Such an issue's body counts as a contract when the issue was opened by
   `claude[bot]` (type `Bot`), carries `audit-finding`, and the latest
   `labeled` event for `ready-for-agent` has a `User` actor with write access
   (`GET /repos/{repo}/collaborators/{login}/permission` answers `admin` or
   `write`; a 404 counts as no access). The rule lives in
   `implementer_contract.body_is_trusted`, which the implementer claim, the
   implementer queue, Retro and the PR review's linked issues share.
3. The audit never adds `ready-for-agent` or another state label, and never
   edits a finding issue's body once `ready-for-agent` was added to it.
4. Description (`D`) findings stay in the rolling issue for a person.

## Consequences

- The audit gains no new power. It already pushes branches and opens pull
  requests with the same App token; trusting its issue text lets an
  implementer run do what the audit could do itself, and only after a person
  added the label.
- The person's label is the only gate. A finding's text comes from a model
  that read skill files and web pages, so read the issue before you label it.
- The rule checks the label's latest adder, not when the body last changed.
  A run that edited the body after the release would slip through; the
  runbook forbids that edit, and the implementer usually claims within
  minutes of the label.
- A person with the triage role can add the label, but the permission check
  turns that release down, so the issue stops with `no-contract`.
- Description findings wait for a person until the eval prompts
  ([ADR-0006](0006-skill-eval-prompts.md)) run as trigger tests: changing a
  description changes when a skill loads, and no check catches that today.
