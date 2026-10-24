# PR review runbook

`.github/workflows/pr-review.yml` assesses, reviews and labels every pull
request. It adds risk and verdict labels, keeps one sticky comment up to date,
and asks the maintainer for a review. It never approves, never merges and
never enables auto-merge.

## Contents

- [What the workflow does](#what-the-workflow-does)
- [Setup](#setup)
- [Dry run](#dry-run)
- [Going live](#going-live)
- [Read a run](#read-a-run)
- [Disable and roll back](#disable-and-roll-back)
- [Known limits](#known-limits)

## What the workflow does

Three jobs per pull request event (`opened`, `synchronize`, `reopened`,
`ready_for_review`) or manual dispatch:

| Job     | Permissions                                  | Model key          | Does                                                                                   |
| ------- | -------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------- |
| assess  | read: contents, pull-requests, issues, checks | none               | `pr_github.py` fetches the context over REST; `pr_risk.py` classifies the paths        |
| review  | `contents: read`                             | `OPENCODE_API_KEY` | `pr_review.py` sanitizes and caps the diff, calls the model, parses the verdict         |
| publish | `pull-requests: write`, `issues: write`      | none               | `pr_publish.py` re-fetches the PR, plans, and `pr_apply.py` writes labels and comment |

- The workflow runs on `pull_request_target`, so the workflow file and the
  scripts always come from the default branch. The pull request head is never
  checked out or executed; diff and base files arrive through the REST API.
- The review job is skipped for drafts and for pull requests whose head lives
  in a fork. Publish still runs and records the review as `skipped`.
- The model's risk can only raise the path-based risk, never lower it. A
  missing key, a provider error or a timeout (60 s) becomes
  `review:unavailable`, never a pass.
- Publish re-reads the pull request right before writing. If the head moved,
  it aborts with `head_sha_changed` and writes nothing; the run for the new
  head takes over.

The risk rules are `PATH_RULES` in `scripts/pr_risk.py`, the prompt is
`scripts/pr_review_prompt.md`.

## Setup

All settings live under the repository's **Settings** tab.

1. **Model key (required for reviews).** *Secrets and variables → Actions →
   Secrets → New repository secret*, name `OPENCODE_API_KEY`, value an
   OpenCode Zen API key. Only the review job reads it. Without it every
   reviewed PR gets `review:unavailable` and `needs-review`; labels and the
   comment still work.
2. **Model (optional).** *Secrets and variables → Actions → Variables → New
   repository variable*, name `PR_REVIEW_MODEL`. Unset means
   `deepseek-v4.1-flash-free` (`DEFAULT_MODEL` in `scripts/pr_review.py`).
   The base URL is fixed to `https://opencode.ai/zen/v1`; the workflow does
   not pass `OPENCODE_BASE_URL`.
3. **No auto-merge variable.** Do not create `PR_AUTO_MERGE`. The workflow
   does not pass it to any job, so it has no effect; auto-merge is not
   available yet (#635, #636).
4. **Labels: nothing to create.** Publish creates the ten labels it knows
   (`LABELS` in `scripts/pr_apply.py`) on first use and tolerates existing
   ones: `risk:low`, `risk:medium`, `risk:high`, `review:pass`,
   `review:concerns`, `review:block`, `review:unavailable`, `needs-review`,
   `do-not-merge`, `auto-merge:bot`. Labels you created earlier keep their
   colour and description.
5. **Actions policy.** *Actions → General*: Actions must be enabled and the
   allowed-actions policy must permit `actions/checkout`,
   `actions/setup-python`, `actions/upload-artifact` and
   `actions/download-artifact` (all pinned to commit SHAs). The *Workflow
   permissions* default does not matter: the workflow sets `permissions: {}`
   and each job declares its own scopes.
6. **Maintainer login.** Reviews are requested from `fabiandistler`
   (`BOT_LOGIN` in `scripts/pr_publish.py` and `scripts/pr_apply.py`). When
   the maintainer authored the PR, publish assigns them instead, because
   GitHub refuses a review request to the author.

Nothing runs before the workflow is on the default branch: a manual dispatch
needs the workflow file there, and `pull_request_target` reads it from there.

## Dry run

**Before merge, locally (read-only).** Runs the same scripts against a real
pull request without writing. Needs `gh auth status` to succeed.

```bash
scripts="$PWD/scripts"; pr=637; out=/tmp/pr-review-$pr
mkdir -p "$out" && cd "$out"
export GITHUB_TOKEN="$(gh auth token)"
python3 "$scripts/pr_github.py" --repo fabiandistler/agents --pr "$pr" --output context.json
python3 "$scripts/pr_risk.py" --context context.json --output assessment.json
python3 "$scripts/pr_review.py" --context context.json --dry-run      # provider request, no network
python3 "$scripts/pr_review.py" --context context.json > review.json  # model call if OPENCODE_API_KEY is set
python3 "$scripts/pr_publish.py" --live --repo fabiandistler/agents --pr "$pr" \
  --assessment assessment.json --review review.json
```

Run it from the repository root. Pick a same-repository PR; for a fork PR
`review.json` is `skipped`.

The last command prints the plan: labels to add and remove, the comment body,
the reviewer action, and `decision.auto_merge`, which must be `off`.
`--write` is refused outside GitHub Actions (exit 5).

**After merge, in Actions.** Dispatch with the default `dry_run: true`:

```bash
gh api --method POST \
  repos/fabiandistler/agents/actions/workflows/pr-review.yml/dispatches \
  --input - <<'JSON'
{"ref": "main", "inputs": {"pr": "NNN", "dry_run": "true"}}
JSON
```

Replace `NNN` with an open same-repository PR. Or *Actions → pr-review → Run workflow*. The dry run calls the model (one
request) but writes nothing to GitHub. Check:

- all three jobs are green; for a fork PR, review is skipped by design;
- the run summary under **PR review decision** shows `auto-merge: off` and the
  labels you expect;
- the PR has no new labels or comments.

To apply the same plan to that one PR, dispatch again with `"dry_run": "false"`.

## Going live

There is no separate switch: merging the workflow to `main` is going live.
From then on every `opened`, `synchronize`, `reopened` and `ready_for_review`
event writes labels and the sticky comment. Open PRs are untouched until
their next such event.

1. Add `OPENCODE_API_KEY` (and `PR_REVIEW_MODEL` if wanted) before merging.
2. Merge, then run the Actions dry run above on one open same-repository PR.
3. Watch the next real PR event. Expected for a docs-only same-repo PR:
   `risk:low`, `review:pass` (or `concerns`), one bot comment, and a review
   request; no auto-merge.

## Read a run

```bash
gh run list --workflow pr-review.yml --limit 5
gh run view <run-id>
gh run view <run-id> --log-failed
gh run download <run-id> -n pr-review
```

Artifacts: `pr-context` (the fetched PR, including the diff), `pr-assessment`
(path risk and reasons), `pr-review` (verdict, findings, raw model text).
Publish exit codes: 1 a write failed, 3 a malformed artifact, 4 the live
re-fetch failed. A provider failure is not a red run; it shows as
`review:unavailable`. Rerun with `gh run rerun <run-id> --failed`, or push to
the PR.

## Disable and roll back

- **Pause everything:**
  `gh api --method PUT repos/fabiandistler/agents/actions/workflows/pr-review.yml/disable`
  (resume with `.../enable`), or *Actions → pr-review → … → Disable
  workflow*. A disabled workflow cannot be dispatched either.
- **Stop model calls only:** delete the `OPENCODE_API_KEY` secret. PRs keep
  getting risk labels and the comment, with `review:unavailable`.
- **Remove:** revert the merge commit in a PR. Existing labels and bot
  comments stay; delete a label with `gh api --method DELETE
  repos/fabiandistler/agents/labels/risk:low`, which removes it from every PR.

## Known limits

- **Fork PRs are never reviewed by the model,** including PRs from the
  maintainer's own fork account. Their diff is untrusted and the review job
  holds a secret. They get risk labels and a comment saying the review was
  skipped.
- **No auto-merge.** `PR_AUTO_MERGE` is not passed, and `pr_apply.py` refuses
  `enable_auto_merge` and `disable_auto_merge` actions. Do not add the
  `auto-merge:bot` label by hand: the planner then emits
  `disable_auto_merge`, `pr_apply.py` rejects the plan, and publish fails
  without writing. Remove the label to recover. See #635 and #636.
- **Advisory only.** The bot never approves and never merges. The merge rule
  and the interactive merge guard (`scripts/pr_merge_guard.py`) are unchanged.
- **Pipeline changes take effect only after merge.** A PR that edits
  `pr-review.yml` or `scripts/pr_*` is classified `risk:high` and reviewed by
  the version on `main`.
- **Partial reviews.** The diff is capped at 2000 lines or 200 KB and the
  request at 300 KB; a capped review is marked partial in the comment.
- **Cost.** The repository is public, so the standard runners cost no
  Actions minutes. Each review job run is one model request; a newer push
  cancels the in-progress run for the same PR. The default model is a free
  OpenCode Zen model; a paid `PR_REVIEW_MODEL` is billed to the key's
  account.
