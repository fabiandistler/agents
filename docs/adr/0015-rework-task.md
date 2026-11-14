# ADR-0015: The Rework task fixes a failed automated review on an implementer pull request, at most two rounds

## Status

Accepted (2026-11-14) with the workflow file; proposed the same day in the
maintainer's agent brief on #782. Builds on
[ADR-0014](0014-agent-runs-in-github-actions.md) (agent runs in GitHub
Actions with the Claude GitHub App token) and leaves
[ADR-0011](0011-pr-review-merge-exception.md) untouched: the Rework task never
merges and never enables auto-merge.

## Context

The implementer (`implementer.yml`) turns an issue into a pull request on
branch `agent/issue-<n>`. `pr-review.yml` reviews it: its `review` job uploads
a `pr-review` artifact (`review.json`: `number`, `head_sha`, `status`,
`verdict`, `findings`), its `assess` job a `pr-context` artifact, and its
`publish` job writes a `review:*` verdict label, `needs-review` and the sticky
comment with `GITHUB_TOKEN`. Nothing acts on a `concerns` or `block` verdict:
every finding waits for the maintainer, even one a model run could fix.

## Decision

`.github/workflows/rework.yml` runs one rework round per non-pass review of an
implementer pull request, at most `MAX_REWORK_ROUNDS = 2` per pull request.

**Trigger.** `workflow_run` on `pr-review`, type `completed`, plus
`workflow_dispatch` with a pull request number. Not a label event: the verdict
labels are written with `GITHUB_TOKEN`, and GitHub Docs ("Events that trigger
workflows", checked 2026-11-14): "With the exception of `workflow_dispatch`
and `repository_dispatch`, other `GITHUB_TOKEN`-triggered events do not create
workflow runs at all." The same page on `workflow_run`:

- it triggers only "if the workflow file exists on the default branch", so the
  task starts working once the file is merged to `main`;
- "You can't use `workflow_run` to chain together more than three levels of
  workflows": `pr-review` → `rework` is two levels, and the rework push starts a
  new `pull_request_target` chain;
- "The workflow started by the `workflow_run` event is able to access secrets
  and write tokens", so the gate re-checks everything from the API and the
  model job runs only after it.

**Gate.** A model-free job, `scripts/rework_gate.py` over the pure
`scripts/rework_policy.py`, reads the triggering run's `pr-review` and
`pr-context` artifacts by run id, the run itself, the live pull request, its
linked issue and its comments. It goes on only if the run concluded `success`
as a `pull_request_target` run of `pr-review.yml`; the pull request is open,
not a draft, in this repository, targets `main`, comes from `agent/issue-<n>`
and was opened by `claude[bot]`; it has no `do-not-merge`; its body closes
issue `#<n>` of the branch, and that issue has no `ready-for-human`; the review
has status `ok`, verdict `concerns` or `block` and at least one finding; the
review's `head_sha` is the live head; no round marker names that head; and no
other rework run is working (the implementer's capacity ordering, now
`scripts/agent_run_capacity.py`). Every stop writes nothing. A manual run
reads the latest successful review run of the live head that still holds a
`pr-review` artifact: a run started by a label event skips the review and
uploads none, and a failed run would only stop the gate.

**Counter.** Before the model job starts, the gate posts
`<!-- rework-round:<k> head:<sha> -->` on the pull request with
`GITHUB_TOKEN`. The markers on the pull request are the counter: only markers
by `github-actions[bot]` count, so a person quoting one neither spends nor
resets a round. One marker per head makes a repeated review of the same commit
a no-op.

**Cap.** With two markers and a new non-pass verdict, the gate replaces
`ready-for-agent` with `ready-for-human` on the issue, then posts one handoff
comment marked `<!-- rework-handoff head:<sha> -->` on the pull request. No
model runs. A repeat for the same head writes nothing. The marker lands last,
so a run that fails at the swap leaves none, and a rerun retries the swap.

**Model job.** `claude-code-action` with the Claude GitHub App token, as in the
implementer, on the model alias the skill audit uses (`sonnet`), overridable by
the repository variable `REWORK_MODEL`. It receives the findings as the
`rework-findings` artifact, never in the prompt, fixes only those findings,
runs `scripts/check_all.sh`, pushes a normal commit to the same branch and
posts one comment that lists each finding as fixed or declined. After two red
check rounds it pushes nothing, comments and hands the issue to a person. The
prompt interpolates only validated numbers and the repository name and keeps
the implementer's hard limits.

**Security posture.** The gate holds `GITHUB_TOKEN` with `issues: write`,
`pull-requests: read`, `actions: read` and `contents: read`, and no model
token. The model job holds the App token because only its push starts
`ci.yml` and the next review; its job token is `contents: read` and
`id-token: write`. The action stops runs started by bots unless they are listed
in `allowed_bots`; the review run is often started by the App's own push, so
`allowed_bots: claude` lists the App and nothing else.

## Considered options

- **Trigger on the `review:concerns` / `review:block` label.** Rejected: the
  label is written with `GITHUB_TOKEN` and starts no run.
- **Count rounds in a label or in the issue.** Rejected: a label holds no
  number and is easy to edit by hand; markers on the pull request carry round
  and head, and the author check keeps them trustworthy.
- **Let the model read the sticky review comment.** Rejected: the comment is
  editable text on a public pull request; the artifact pinned to `head_sha` is
  the review the gate checked.
- **Rework on red CI alone, or on any pull request.** Out of scope: the task
  acts only on a non-pass review of an `agent/issue-<n>` pull request.

## Consequences

- An implementer pull request with findings gets up to two automatic fix
  rounds before the maintainer reads it; each round is one more review.
- The workflow file lands by hand: the App token cannot write
  `.github/workflows/`, so its pull request carries the file in its body.
- A review that stops at capacity starts no later round on its own; a manual
  run (Actions → rework → Run workflow) for the pull request retries it.
- `docs/agents/triage-labels.md` keeps the outcome table.
