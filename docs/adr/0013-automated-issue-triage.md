# ADR-0013: New issues are triaged by a model that may set only `needs-info`

## Status

Proposed (2026-11-10). The maintainer chose the autonomy (`needs-info` only)
and the runner (three Actions jobs); the brakes below are proposed with the
pull request that adds the workflow. Builds on
[ADR-0012](0012-pr-review-on-claude-subscription.md) (the model runs through
`claude -p` on the Claude subscription).

## Context

Issues reach `ready-for-agent`, and from there the implementer, only after the
maintainer has triaged them by hand with `/triage`. `triage-label.yml` marks
every new issue `needs-triage` and stops there, so untriaged issues wait for
the maintainer (#735 on 2026-11-10). The PR side already has an automated
review (`pr-review.yml`); the issue side has no automated step.

Adding `ready-for-agent` starts the implementer. A model that sets that label
would chain issue → implementation → PR with no human in between before the
PR review.

## Decision

`.github/workflows/issue-triage.yml` triages an issue in three jobs, split the
same way as the PR review:

- **assess** (issues read, no model): fetch the issue and its comments and
  decide with `scripts/issue_triage_policy.py` whether the trigger may start a
  model run.
- **triage** (model token, no GitHub token): `scripts/issue_triage.py triage`
  runs `claude -p --restricted --tools Read,Grep,Glob` in a checkout of the
  default branch. The model checks whether the request is already implemented,
  previously rejected in `.out-of-scope/`, and traceable in the code, and
  answers with a category, one recommended state, evidence, and either
  questions or a draft agent brief.
- **publish** (issues write, no model): post one comment and move the label.

The bot applies **`needs-info` only**. `ready-for-agent`, `ready-for-human`
and `wontfix` stay recommendations in the comment; the maintainer sets them,
and only the maintainer closes an issue.

Brakes:

- Only issues by `OWNER`, `MEMBER` or `COLLABORATOR` reach the model. The
  repository is public; an outsider spends neither the quota nor the prompt.
- The automatic triggers (a new issue, the reporter answering `needs-info`)
  stop after two bot triages per issue. The maintainer adding `needs-triage`
  or starting a manual run is not capped.
- When the reporter answers a `needs-info` issue, it moves back to
  `needs-triage` without a model, whether or not a triage follows.
- Publish re-reads the labels and writes nothing if the maintainer changed the
  state while the model ran.

## Considered options

- **The bot also sets `ready-for-agent`.** Rejected for now: it starts the
  implementer, and the only brake left would be the PR review and the merge.
  Reopen once the recommendations have proved right for a few weeks.
- **Recommendations only, no label at all.** Rejected: `needs-info` stops
  nothing downstream, and a bot that asks the reporter at once saves a round
  trip.
- **`anthropics/claude-code-action`.** Rejected for the reason in ADR-0012:
  the model job would hold a GitHub write token. It could reproduce bugs with
  Bash; the read-only checkout cannot, so "confirmed" means traced in code.
- **A scheduled Claude Code routine** (like the skill audit). Rejected: the
  clock delays triage to the next run, and the session holds full rights.

## Consequences

- Each new issue by a collaborator costs one `claude -p` run of up to 40 turns
  on the subscription, shared with interactive use and the PR review.
- `claude --restricted` confines the file tools to the checkout and refuses
  process files such as `/proc/self/environ` (checked with 2.1.321 on
  2026-11-10); an answer that contains the token is refused before it can be
  published. The pinned CLI version is shared with the PR review and bumped
  with it.
- Issues filed with a state label already (maintenance runs, `to-tickets`)
  are not triaged again.
