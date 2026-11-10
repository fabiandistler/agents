# ADR-0013: New issues are triaged by a model that may set only `needs-info`

## Status

Accepted (2026-11-10) by the maintainer, after the review of #743: the bot
sets `needs-info` itself, the three Actions jobs run it, and the brakes below
stand. Builds on
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
  `needs-triage` without a model, whether or not a triage follows. This holds
  for every reporter, outsiders included, and for a `needs-info` the
  maintainer set: it is the triage state machine's own transition, and it only
  returns the issue to the maintainer's queue.
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
- The issue text is untrusted even from a collaborator. It reaches the model
  as one JSON document between marker lines, so it cannot pose as prompt
  structure; it can still sway the recommendation, which is why the bot's own
  power stops at `needs-info` and a comment.
- `--restricted` also refuses symlinks in the checkout that resolve outside it
  (files, directories and `/proc/<pid>/environ`; checked 2026-11-10). The
  check holds for the pinned version only: before the CLI pin is bumped, run
  it again with the new version (Read and Grep on a file, a `/proc` link and
  a directory link outside the working directory must all be refused).
- The triage job always checks out the default branch, and a newer trigger
  waits for the run in flight instead of cancelling it.
- Publish posts the comment before it moves the label, so a failed label
  write leaves the reasoning visible and the run red. The comment still
  counts towards the two automatic triages.
- `triage-label.yml` re-reads the labels before it adds `needs-triage`. That
  narrows the race with a parallel `needs-info` to the gap between two API
  calls; if both labels ever land, the next run reports conflicting state
  labels and skips the issue.
