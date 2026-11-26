# ADR-0021: The triage bot also sets `ready-for-human`

## Status

Accepted (2026-11-26) by the maintainer. Partly supersedes
[ADR-0013](0013-automated-issue-triage.md): its "the bot applies
`needs-info` only" becomes "`needs-info` and `ready-for-human`". Every
other part of ADR-0013 stands, including its brakes.

## Context

ADR-0013 left `ready-for-human` as a recommendation in the triage comment,
so the maintainer had to move every such issue by hand. On 2026-11-26 all
five open `needs-triage` issues across the three factory repositories carried
a bot recommendation of `ready-for-human` (agents #972, #984, #985, #986;
repo-maintenance #137). The manual step only copied the recommendation.

ADR-0013 kept `ready-for-agent` with the maintainer because it starts the
implementer. `ready-for-human` starts no factory task: no workflow triggers
on it, and the Rework gate stops on an issue that carries it.

## Decision

`scripts/issue_triage_policy.py` adds `ready-for-human` to the states the
bot applies (`BOT_STATES`). Publish replaces `needs-triage` (or a stale
`needs-info`) with it, after the comment, as for `needs-info`.

The draft brief in the triage comment is the issue's brief; the maintainer
posts none of their own. The comment says so instead of "only the
maintainer sets".

`ready-for-agent` and `wontfix` stay recommendations: the first starts the
implementer, the second goes with closing, which only the maintainer does.

The change lives in the reusable workflow's scripts, with no input: every
caller gets it at its next pin bump.

## Considered options

- **Keep it a recommendation (ADR-0013).** Rejected: the maintainer works a
  `ready-for-human` issue either way, so the manual label adds a step and no
  check.
- **A caller input to opt in.** Rejected: no caller asks for the old
  behaviour, and an option nobody passes is dead code.
- **Also set `wontfix`.** Rejected: the state belongs with closing the
  issue, which stays with the maintainer.

## Consequences

- The `needs-triage` queue is no longer where a wrong `ready-for-human`
  recommendation is caught. An issue an agent could have built lands in the
  maintainer's work queue and is reclassified when picked up. The error is
  cheap to undo and starts nothing.
- The prompt's "prefer `ready-for-human` over `ready-for-agent` when in
  doubt" now routes doubtful issues straight to the maintainer's queue
  instead of the triage queue.
- An issue the maintainer re-triages by adding `needs-triage` gets a new
  bot run, which may set `ready-for-human` again.
