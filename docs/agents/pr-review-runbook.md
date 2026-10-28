# PR review runbook

Repository maintainers use this runbook to operate PR review, with GitHub
Actions access and an understanding of the repository's human merge rule.

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
- [Labels and troubleshooting](#labels-and-troubleshooting)
- [Acceptance record](#acceptance-record)
- [Auto-merge decision](#auto-merge-decision)
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
- Publish re-reads the pull request right before writing and rebuilds its
  plan from the current files, labels and comments. If the head moved, it
  aborts with `head_sha_changed`; a closed PR aborts with
  `pull_request_closed`. Both cases write nothing.

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
`review:unavailable`. After a provider fix, dispatch a fresh dry run or rerun
the whole run with `gh run rerun <run-id>`. Use `--failed` only for a red job;
it does not retry an unavailable review in a successful run. A new PR push
also triggers a fresh assessment.

## Labels and troubleshooting

Issue classification keeps its own [five triage roles](triage-labels.md).
PR review uses these separate families:

| Label | Meaning and operator action |
| --- | --- |
| `risk:low` | Documentation/report path floor; the model can raise it. Merging remains manual. |
| `risk:medium` | Skills, agent instructions, README/ADRs or a size escalation; human review needed. |
| `risk:high` | Workflow, guard, automation, unknown path, fork or large change; human review needed. |
| `review:pass` | The provider returned a parseable passing verdict. |
| `review:concerns`, `review:block` | Read the findings in the sticky comment before merging. |
| `review:unavailable` | Review did not run successfully; inspect the review artifact and configuration. |
| `needs-review` | Maintainer attention is needed, including the self-authored assignment case. |
| `do-not-merge` | Explicit maintainer veto; leave the PR open. |
| `auto-merge:bot` | Reserved for #635; inactive in this implementation. |

Thresholds and path rules live in `scripts/pr_risk.py`: over 300 changed lines
or 20 files raises risk to medium; over 1000 lines or 50 files raises it to
high. README and ADRs are policy documents, so their floor is medium. Risk
suggestions never lower the deterministic floor. A skipped draft/fork review
has no verdict label; a provider failure uses `review:unavailable`.

| Symptom | Check and recovery |
| --- | --- |
| Missing labels or HTTP 403 | Check the publish job and repository Actions policy. Its existing `issues: write` and `pull-requests: write` scopes must be allowed; model access does not grant these scopes. |
| Provider unavailable | Check that the maintainer configured the model secret, model availability and provider quota. Inspect `pr-review`; rerun only after fixing the cause. No raw credential belongs in an issue or log. |
| `head_sha_changed` | A push invalidated the review. Wait for the run for the latest head; the old run intentionally writes nothing. |
| `pull_request_closed` | The PR closed during the run. No action is needed unless it is intentionally reopened. |
| Conflicting `risk:*` or `review:*` labels | A fresh successful publish replaces stale labels within each family. Check that the latest run succeeded rather than editing a label to override the policy. |
| Duplicate sticky comments | Check whether concurrent publishers bypassed the per-PR workflow concurrency. The final snapshot reuses an existing marker comment instead of creating a second one. |
| Publish rejects `disable_auto_merge` | GitHub reports auto-merge as active on a PR that carries `auto-merge:bot`. Disable auto-merge on the PR by hand; the writer deliberately refuses auto-merge actions until #635 is implemented. |

There is no separate daily request quota: one eligible review job makes one
provider request, with bounded input and a 60-second timeout. Superseded runs
are cancelled. The provider account's current quota, pricing and model
availability are operator-managed; a limit or outage yields an unavailable
review.

## Acceptance record

Offline verification and live rollout are separate. Pending rows are not
completion claims for #631, #633, #634 or #636.

| Scenario | Evidence or remaining manual step |
| --- | --- |
| Risk, review parser, publish planning, writer and workflow contracts | Run the six `scripts/test_pr_*.py` suites for this branch; tests use fixtures and fake transports only. |
| State changes between assessment and writing | Regression cases change the final files, labels, sticky comment or PR state; closed/stale PRs write nothing. |
| Live provider smoke test | Pending maintainer setup of `OPENCODE_API_KEY`; run the local read-only sequence with an approved provider configuration and record the result. |
| End-to-end Actions dry run | Pending workflow deployment to `main`; dispatch with `dry_run=true`, record the run URL and verify no PR metadata changed. |
| Live non-docs PR | Pending approved deployment; record a run with `needs-review`, a sticky comment and a maintainer request/assignment, with auto-merge off. |
| Docs PR waiting for required checks | Pending #635, the merge exception decision and maintainer ruleset setup; no such run has been performed. |

Before closing acceptance issues, replace each completed pending row with the
run URL, head SHA and observed result. Offline tests cannot verify live token
permissions, provider availability, label writes or ruleset enforcement.

## Auto-merge decision

Auto-merge remains unavailable. Setting `PR_AUTO_MERGE=true` cannot activate it
because the workflow does not pass that variable and the writer rejects merge
actions. The proposed [CI exception decision](../adr/0011-pr-review-merge-exception.md)
records #635/#636's remaining choice; it does not change the current merge rule.

If that exception is approved, a separate reviewed implementation must add
native auto-merge behind an off-by-default variable, validate every gate, and
update the merge rule precisely. The maintainer must then protect `main` with
required `checks`, `mermaid` and `secrets` checks before any enablement. The
rollout is a read-only dry run, an observation period, verified required-check
configuration, and only then explicit maintainer enablement. The interactive
merge guard remains unchanged throughout.

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
  `enable_auto_merge` and `disable_auto_merge` actions. A stale
  `auto-merge:bot` label is removed on the next publish. Only when GitHub
  also reports auto-merge as active does the planner emit
  `disable_auto_merge`, which `pr_apply.py` rejects; see the troubleshooting
  table. See #635 and #636.
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
