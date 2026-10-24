# ADR-0011: Decide the docs-only CI merge exception separately

## Status

Proposed. No merge exception is active; #635 and #636 remain pending the
maintainer's decision. The interactive merge guard remains unchanged.

## Context

The PR review feature (#621, #630–634) separates a read-only model review from
a deterministic publisher. Its current writer can label, comment and request
a maintainer review, but cannot approve or enable auto-merge. The repository
currently reserves merging for humans. Automating even low-risk merges would
change that governance boundary, so a ready issue or a passing model verdict
cannot grant the exception.

## Proposed decision

Keep the advisory review pipeline and the human merge rule as implemented.
Review the proposed docs-only CI exception independently before adding any
merge capability. Approval would authorize one model-free CI publisher to
enable GitHub native auto-merge, never direct merging and never bot approval.
Interactive agents would retain the existing merge prohibition.

The proposed exception would require all of these gates together:

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
this proposal. An accepted decision must precede a separately reviewed merge
implementation and operator rollout.

## Considered options

- **Advisory review with human merges (current).** Provides labels and findings
  with a small write surface, but routine documentation still waits on a human.
- **Narrow native auto-merge exception (proposed).** Could reduce that queue;
  requires a new governance decision, tested revocation and enforced checks.
- **LLM-held write or merge credential.** Rejected: untrusted review input must
  not control repository writes.
- **Direct bot merge or general auto-merge.** Rejected: it would bypass native
  check waiting or expand beyond the intended documentation-only scope.

## Consequences

The current review feature can be evaluated without granting merge authority.
#635 and the merge-rule portion of #636 cannot be marked complete yet. If the
exception is approved, the maintainer must review the exact rule change and
its implementation, configure required checks and record live acceptance.
