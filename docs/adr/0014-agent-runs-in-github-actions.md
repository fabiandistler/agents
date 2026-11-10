# ADR-0014: Agent runs that write move from Claude Code scheduled tasks to GitHub Actions

## Status

Accepted (2026-11-10) by the maintainer. Narrows the reasoning of
[ADR-0012](0012-pr-review-on-claude-subscription.md) and
[ADR-0013](0013-automated-issue-triage.md), which rejected
`anthropics/claude-code-action` for jobs that only need to read; both
decisions stand for the PR review and the issue triage.

## Context

Two agent runs of this repository ran as Claude Code scheduled tasks in the
maintainer's cloud account (checked 2026-11-10):

- **Implementer** ("Software factory"): a GitHub event trigger on
  `ready-for-agent`; one issue becomes one pull request.
- **Skill audit** ("Weekly skill audit"): the 8th and the 22nd of each month,
  following [`docs/agents/skill-audit.md`](../agents/skill-audit.md).

The PR review and the issue triage already run in GitHub Actions. The
software factory was split across two orchestrators, with its run history,
prompts and failures in two places, and the scheduled tasks' prompts lived
outside the repository, unreviewed and unversioned.

Unlike the review and the triage, these runs must write: claim a branch, push,
open a pull request, comment on and relabel issues. A model-free publisher
cannot take over those writes without rebuilding each task as a patch
artifact plus a publisher script.

A third task, the weekly `repo-maintenance` run, stays a scheduled task: it
reads the plugin from the private `fabiandistler/repo-maintenance`, which the
Actions token cannot reach without a personal access token.

## Decision

`.github/workflows/implementer.yml` and `.github/workflows/skill-audit.yml`
run the pinned `anthropics/claude-code-action` on the maintainer's Claude
subscription (`CLAUDE_CODE_OAUTH_TOKEN`, as in ADR-0012). The action
exchanges the job's OIDC token for a **Claude GitHub App** installation token
and gives it to the model as `GH_TOKEN`:

- It reaches this repository only and cannot write workflows.
- Its pushes and pull requests start `ci.yml` and `pr-review.yml`. A
  `GITHUB_TOKEN` push would start neither, so the required checks would never
  report and the PR review never run.
- The job's own token stays read-only: `contents: read`, plus `actions: read`
  in the implementer alone, which `scripts/implementer_claim.py` uses to count
  working runs because the App token cannot be shown to have Actions read.
  `id-token: write` is the only other scope. The implementer's model step passes
  this token as `ACTIONS_READ_TOKEN`; the action already exposes it to that step
  as `DEFAULT_WORKFLOW_TOKEN`, so this adds no token the model could not reach.

The prompts are versioned in the workflow files. The skill audit's prompt
only points at its runbook, as the scheduled task's did.

## Considered options

- **Model/publisher split, as in the PR review.** The model edits a checkout
  without any GitHub token; a model-free job pushes its patch and opens the
  PR. Safer, but each task needs its own publisher with tests, and the
  publisher still needs an App token or a personal access token for the
  checks to start. Not chosen: several days of work for runs that today
  already hold full rights in the cloud session.
- **`github_token: ${{ secrets.GITHUB_TOKEN }}`.** Scoped by the job's
  `permissions`, but its pull requests start no workflows (GitHub docs,
  "Triggering a workflow from a workflow"). Rejected.
- **Keep the scheduled tasks.** Rejected by the maintainer: everything in one
  place.

## Consequences

- The model holds a write token. A prompt injection in an issue, a comment or
  a fetched page can make it push a branch, open a pull request or comment.
  The brakes: the prompts' hard limits; the PR merge guard
  (`scripts/pr_merge_guard.py`), which loads from `.claude/settings.json`
  because the action reads project settings; branch protection with the
  required checks; the automated PR review; and the human merge.
- Only a person starts the implementer: the job skips labels added by a bot,
  and claude-code-action checks that the actor has write access.
- Runs draw on the subscription limits, shared with interactive use, the PR
  review and the triage. The implementer runs on `opus`, the audit on
  `sonnet`, as the scheduled tasks did.
- No push notification. A run that writes `RUN FAILED` or no summary fails
  its job, and GitHub notifies about failed runs. The summary is on the run
  page.
- The action is pinned to a commit SHA; Dependabot (`github-actions`) moves it.
- Scheduled workflows run on the default branch only and are disabled after
  60 days without repository activity in a public repository.
- The scheduled tasks are disabled, not deleted, after each workflow's first
  green manual run.
