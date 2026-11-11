# PR review troubleshooting

For the repository maintainer, when a run of `.github/workflows/pr-review.yml`
is red or a pull request carries labels you did not expect. Setup and the
security model are in the [runbook](pr-review-runbook.md); the label meanings
in [triage-labels.md](triage-labels.md#pull-request-labels).

## Read a run

```bash
gh run list --workflow pr-review.yml --limit 5
gh run view <run-id>
gh run view <run-id> --log-failed
gh run download <run-id> -n pr-review
```

Artifacts: `pr-context` (the fetched pull request, including the diff),
`pr-assessment` (path risk and reasons), `pr-review` (verdict, findings, raw
model text). The `publish` step summary, **PR review decision**, shows the
risk, review status, verdict, auto-merge state, the `pr-review/verdict` state
and the labels the run added and removed; the full plan JSON follows it.

Every `scripts/pr_*.py` command line shares one exit-code table
(`scripts/pr_cli.py`); a code means the same failure in every script:

| Code | Failure | Returned by |
| --- | --- | --- |
| 1 | a write action failed | `pr_publish.py`, `pr_apply.py` |
| 2 | usage | all |
| 3 | bad input file (context, assessment, review, response or plan) | `pr_risk.py`, `pr_review.py`, `pr_publish.py`, `pr_apply.py` |
| 4 | GitHub fetch failed | `pr_github.py`, `pr_risk.py`, `pr_publish.py` |
| 5 | missing `GITHUB_TOKEN` | `pr_github.py`, `pr_risk.py`, `pr_publish.py`, `pr_apply.py` |
| 6 | output file (`--output`, `--summary`) not writable | `pr_github.py`, `pr_risk.py`, `pr_review.py`, `pr_publish.py` |
| 7 | `--write` outside GitHub Actions | `pr_publish.py`, `pr_apply.py` |

The jobs run `pr_github.py` and `pr_risk.py` (assess), `pr_review.py`
(review) and `pr_publish.py` (hold, publish). A provider failure is never a
red run: `pr_review.py` exits 0 and the pull request shows
`review:unavailable`.

## Symptoms

| Symptom | Check and recovery |
| --- | --- |
| Labels missing after a green run | The run planned no change or aborted. Read the step summary: `aborted: head_sha_changed` means a push superseded the run (wait for the newer run); `pull_request_closed` needs no action. |
| `publish` or `hold` red with HTTP 403 | A write scope was refused. Check *Settings → Actions → General*: the policy must allow the jobs' `contents`, `pull-requests` and `issues` write scopes, and `statuses` for `publish`. Auto-merge writes also need **Allow auto-merge** on. The model token grants none of these. |
| `review:unavailable` on every pull request | Missing or expired `CLAUDE_CODE_OAUTH_TOKEN` ([token renewal](pr-review-runbook.md#token-renewal)), a `PR_REVIEW_MODEL` the CLI does not know (such as an old OpenCode Zen ID), a failed CLI install, a reached subscription limit or an outage. The review artifact's summary says whether the provider is not configured or the call failed. A failed call leaves one line in the `Review the diff` step log, `pr_review.py: the claude CLI …`, with the CLI's own reason (for example `api_error_status=401` for an expired token); the `Install Claude Code` step log shows install failures. Fix the cause, then follow the [manual re-run](pr-review-runbook.md#manual-re-run). Never paste the token into an issue or log. |
| Stale decision: labels or auto-merge from an older head | Each push runs `hold`, which disables the bot's auto-merge at once, and a fresh assessment. If the newest run was cancelled or failed, dispatch with `"dry_run": "false"` for that pull request. |
| Conflicting labels, such as `risk:low` and `risk:high` together | Someone added a label by hand. The next successful `publish` keeps one label per family and removes the rest. Do not edit labels to override the policy; change `scripts/pr_risk.py` in a reviewed pull request instead. |
| Auto-merge not armed; comment says it could not be armed | GitHub refused to arm auto-merge because the pull request was already mergeable with its checks done (decision D). The run stays green and adds `needs-review`. Merge by hand if you agree. |
| `do-not-merge` removed, but auto-merge stays off | Intended: there is no `unlabeled` trigger. Push a commit or dispatch with `"dry_run": "false"` to let `publish` decide again. |
| Auto-merge you enabled was disabled | Either `do-not-merge` was on the pull request (it disables any auto-merge), or the pull request carried `auto-merge:bot`, so the bot treated it as its own. Do not add `auto-merge:bot` by hand. |
| Bot auto-merge stays on after a worse verdict | `auto-merge:bot` was removed by hand, so the bot now treats the auto-merge as a human's and leaves it alone. Disable it in the pull request page, or add `do-not-merge`. |
| Docs pull request merged, but no CI run on `main` | Expected: a merge through auto-merge armed with `GITHUB_TOKEN` starts no `push` workflow. CI on `main` runs with the next human push. |
| Pull request merged before `bats`, `mermaid`, `secrets` or the review finished | The ruleset does not yet require all five checks: `checks`, `bats`, `mermaid`, `secrets` and `pr-review/verdict`. Make the one-time [ruleset change](pr-review-runbook.md#setup). |
| Merge blocked: `pr-review/verdict` *Expected — Waiting for status to be reported* | No run has published a verdict for this head yet. Wait for the run of the latest push. With no run (an older pull request, or one opened by another workflow's `GITHUB_TOKEN`), dispatch with `"dry_run": "false"`. See [verdict status](pr-review-verdict-status.md). |
| `pr-review/verdict` is `error` | The review was unavailable (row `review:unavailable` above). Fix the cause, then dispatch with `"dry_run": "false"`; any verdict turns it green. |
| `pr-review/verdict` stays `pending` | The pull request is a draft. Mark it ready for review; that run sets the status. |
| `publish` red and `pr-review/verdict` not set | An earlier write of the run failed, so `publish` withheld the green status. Read the failed action in the step summary, then `gh run rerun <run-id> --failed`. A 403 on `/statuses/` means the `statuses: write` scope was refused (row `publish` or `hold` red with HTTP 403). |
| Duplicate sticky comments | Check for runs that bypassed the per-pull-request concurrency group. `publish` edits only the comment the bot authored with the marker; delete the extra ones by hand. |
