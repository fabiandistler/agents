# PR review verdict status

For the repository maintainer. The `publish` job of
`.github/workflows/pr-review.yml` sets the commit status `pr-review/verdict`
on the head SHA it reviewed, as its last write. Once the ruleset requires it,
every merge, a hand-armed auto-merge included, waits until the review of that
head is published. It does not judge the verdict: the review stays advisory
([ADR-0011](../adr/0011-pr-review-merge-exception.md), amendment of
2026-11-11). Jobs and the security model are in the
[runbook](pr-review-runbook.md).

## States

| Review of the head | State | Merge |
| --- | --- | --- |
| No run has published yet (new push, run still going) | none: GitHub shows *Expected — Waiting for status to be reported* | waits |
| `pass`, `concerns` or `block`, partial or not | `success` | may proceed |
| `review:unavailable` | `error` | waits for a [re-run](#escape-a-head-without-a-verdict) |
| Draft | `pending` | waits for the `ready_for_review` run |
| Fork (never reviewed by the model) | `success` | may proceed; the maintainer reviews it |

The status links to the run that set it. The `publish` step summary shows the
state as `pr-review/verdict: …`.

## Guarantees

- **Nothing sets it green ahead of time.** A status belongs to a commit, so a
  push starts the new head with no status. No job writes a placeholder: the
  missing required status is the wait.
- **A failed or skipped run leaves no green.** A dry run writes nothing. A
  run whose assessment failed skips `publish`. A run that aborts
  (`head_sha_changed`, `pull_request_closed`) writes nothing. When an earlier
  write of the same run fails, `publish` withholds `success` and goes red;
  `gh run rerun <run-id> --failed` sets it.
- **Only this context.** `publish` holds `statuses: write`, which could set
  any status. The writer (`scripts/pr_actions.py`) refuses any other context,
  any commit but the assessed head and the state `failure`, so the job cannot
  touch `checks` or another required check.

## Escape: a head without a verdict

Dispatch the workflow with `"dry_run": "false"` for the pull request
([manual re-run](pr-review-runbook.md#manual-re-run)). The dispatch reviews
the current head and sets the status on it. This covers:

- pull requests opened before the status existed;
- pull requests whose events start no workflow, such as one opened with
  another workflow's `GITHUB_TOKEN`;
- an unavailable review, once its cause is fixed
  ([troubleshooting](pr-review-troubleshooting.md#symptoms)).

When the review cannot run at all (token expired, workflow paused or
removed), every pull request waits. Fix the cause, or remove
`pr-review/verdict` from the ruleset
([disable and roll back](pr-review-runbook.md#disable-and-roll-back)).

## Adding it to the ruleset

A one-time manual step (runbook [setup](pr-review-runbook.md#setup), step 6),
in this order:

1. Merge the change that sets the status, and wait until one pull request
   shows `pr-review/verdict`. GitHub offers a check in the ruleset only after
   it has reported in the repository within the past seven days.
2. *Rules → Rulesets → `default` → Require status checks to pass*: add
   `pr-review/verdict` (and `bats`) with GitHub Actions as the source.
   `publish` writes the status with the workflow's `GITHUB_TOKEN`. If the next
   pull request's merge box does not count the status, set that check to any
   source.
3. Push to, or dispatch with `"dry_run": "false"` for, each pull request that
   is still open; until then it has no status on its head and waits.
