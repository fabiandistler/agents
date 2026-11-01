# ADR-0011: A narrow docs-only CI merge exception

## Status

Accepted (2026-10-28) by the maintainer on #621, for the gated cases below
only. Not yet active: the merge capability ships with #635 and the merge-rule
text with #636. The interactive merge guard remains unchanged.

## Context

The PR review feature (#621, #630–634) separates a read-only model review from
a deterministic publisher. Its current writer can label, comment and request
a maintainer review, but cannot approve or enable auto-merge. The repository
currently reserves merging for humans. Automating even low-risk merges would
change that governance boundary, so a ready issue or a passing model verdict
cannot grant the exception.

## Decision

Ship the advisory review pipeline first, then add the docs-only CI exception
as a separately reviewed change (#635). The exception authorizes one
model-free CI publisher to enable GitHub native auto-merge, never direct
merging and never bot approval. Interactive agents keep the existing merge
prohibition.

The exception requires all of these gates together:

- An explicit, off-by-default `PR_AUTO_MERGE=true` operator setting.
- Low deterministic risk and a complete passing model review; the model may
  only raise the risk floor. Policy documents, skills, workflow changes and
  automation changes stay outside low risk.
- A same-repository, non-draft, open and mergeable PR to the default branch.
- Fresh head SHA, file policy, labels and review state immediately before
  writing, with no human change request or `do-not-merge` veto.
- Required `checks`, `mermaid` and `secrets` enforced by the default branch's
  ruleset, verified by a docs PR waiting for those checks.
- Bot-owned enable/disable state so a later risk change revokes only the
  bot's auto-merge, preserving human-controlled auto-merge.

The runbook's [acceptance record](../agents/pr-review-runbook.md#acceptance-record)
tracks the required manual evidence. The existing code, workflow permissions,
repository ruleset, variables, secrets and interactive guard are unchanged by
this decision. The merge implementation and the operator rollout are reviewed
separately.

## Considered options

- **Advisory review with human merges only.** Provides labels and findings
  with a small write surface, but routine documentation still waits on a human.
- **Narrow native auto-merge exception (chosen).** Reduces that queue;
  requires tested revocation and enforced checks.
- **LLM-held write or merge credential.** Rejected: untrusted review input must
  not control repository writes.
- **Direct bot merge or general auto-merge.** Rejected: it would bypass native
  check waiting or expand beyond the intended documentation-only scope.

## Consequences

The review feature can be evaluated before any merge authority is live. #635
and the merge-rule portion of #636 remain open until the maintainer reviews
the exact rule change and its implementation, configures the required checks
and records live acceptance.
