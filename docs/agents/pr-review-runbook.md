# PR review runbook

For the repository maintainer, who operates the PR review workflow with admin
access to the repository settings.

`.github/workflows/pr-review.yml` assesses, reviews and labels every pull
request. It is a thin caller: the jobs live in the reusable workflow
`.github/workflows/factory-pr-review.yml`, which other repositories call at a
pinned commit ([ADR-0018](../adr/0018-reusable-factory-workflows.md);
[reusable workflow and inputs](pr-review-reusable-workflow.md)). The review
keeps one sticky comment up to date and requests the maintainer's review. For
a gated docs-only pull request it may also enable GitHub's native auto-merge,
once `PR_AUTO_MERGE` is `true`. It never approves, never requests changes and
never merges directly: the merge happens when GitHub's auto-merge sees the
required checks pass. Why this exception exists, and its limits:
[ADR-0011](../adr/0011-pr-review-merge-exception.md).

Related pages:

- [Labels and thresholds](triage-labels.md#pull-request-labels)
- [Troubleshooting and reading a run](pr-review-troubleshooting.md)
- [Acceptance record](pr-review-acceptance.md)
- In the review payload: [linked issues](pr-review-linked-issues.md), [PR comments](pr-review-comments.md)
- [Verdict status](pr-review-verdict-status.md)
- [Event policy for `pull_request_target`](pr-review-event-policy.md)
- [Reusable workflow and inputs](pr-review-reusable-workflow.md)

## Contents

- [Jobs and security model](#jobs-and-security-model)
- [Auto-merge](#auto-merge)
- [Setup](#setup)
- [Rollout](#rollout)
- [Dry run](#dry-run)
- [Linked issues](#linked-issues)
- [Manual re-run](#manual-re-run)
- [Model change](#model-change)
- [Quota and cost](#quota-and-cost)
- [Disable and roll back](#disable-and-roll-back)
- [Known limits](#known-limits)

## Jobs and security model

The workflow triggers on `pull_request_target` (`opened`, `synchronize`,
`reopened`, `ready_for_review`, `labeled`) and on a manual `workflow_dispatch`
with a pull request number and `dry_run` (default `true`). From 2026-12-02
the `pull_request_target` trigger runs only with the event policy of
[setup step 8](#setup).

| Job | Permissions and secrets | Does |
| --- | --- | --- |
| `hold` | write: contents, pull-requests, issues; no model token | On a push, disables the bot's auto-merge; when `do-not-merge` is added, disables any auto-merge. Never enables. |
| `assess` | read: contents, pull-requests, issues | `pr_github.py` fetches the context over REST; `pr_risk.py` classifies it. |
| `review` | `contents: read`; `CLAUDE_CODE_OAUTH_TOKEN` | Installs a pinned Claude Code CLI; `pr_review.py` sanitizes and caps the input, runs `claude -p` without tools, parses the verdict. |
| `publish` | write: contents, pull-requests, issues, statuses; no model token | `pr_publish.py` re-fetches, plans and, through `pr_apply.py`, writes, then sets [`pr-review/verdict`](pr-review-verdict-status.md). |

- **Base code only.** `pull_request_target` runs the workflow file and scripts
  from the default branch. No job checks out or executes the pull request
  head; the diff, file list and base files arrive through the REST API. A
  pull request that edits the pipeline is reviewed by the version on `main`.
- **Credential split.** Only `review` holds the model token, and it has no
  write scope. The jobs that write hold no model token and check out nothing;
  `review` checks out the caller's base with `persist-credentials: false`. The
  default of both workflow files is `permissions: {}`.
- **The model only advises, and holds no tool.** It runs inside the Claude
  Code CLI with `--tools ""`, a replaced system prompt, no settings, MCP
  servers or slash commands, and an empty working directory. Injected text can
  sway its verdict but cannot run a command or read the token. Its risk can
  raise the path-based risk, never lower it. Title, body and diff are untrusted data: HTML comments,
  zero-width characters and base64 blobs are stripped before the prompt is
  built. Unparseable output becomes `concerns` and `high`.
- **Drafts and forks** are assessed and labeled but not reviewed; their
  review is `skipped`. A fork's diff never reaches the job that holds a
  secret, and a fork never auto-merges.
- **Fresh data before writing.** `publish` re-fetches the pull request,
  plans, then re-fetches again right before the first write and re-plans
  from that data. If the head moved since the assessment, it aborts with
  `head_sha_changed`; a closed pull request aborts with
  `pull_request_closed`. Both write nothing.
- **One sticky comment.** It is found by the hidden marker
  `<!-- pr-review-bot -->` and the bot author; a human comment quoting the
  marker is never edited. An unchanged body is not rewritten.
- **Reviewer.** `fabiandistler` is requested as reviewer. When the maintainer
  authored the pull request, GitHub refuses a self-review request, so
  `publish` assigns them and adds `needs-review`. A draft gets neither the
  request nor the assignment; the `ready_for_review` run asks for them.
- **Concurrency.** One group per pull request; a new push cancels the run for
  the old head. Each label event has its own group, so it never cancels a
  review run. The group is defined in `factory-pr-review.yml` only; a caller
  defines none, because a group shared with the called workflow would cancel
  the caller.

Risk rules are `PATH_RULES` in `scripts/pr_risk.py`; the prompt is
`scripts/pr_review_prompt.md`.

## Auto-merge

`publish` enables auto-merge only when every gate holds on the re-fetched
data:

- the repository variable `PR_AUTO_MERGE` is exactly `true`;
- the effective risk is `low` and the review is complete (`ok`, not partial)
  with verdict `pass`;
- the pull request comes from this repository, is not a draft, targets the
  default branch and GitHub reports it mergeable;
- the head SHA is unchanged since the assessment;
- no human review requests changes, and `do-not-merge` is absent.

The required checks are not a gate in the script (decision A). The default
ruleset requires the five checks of [setup step 6](#setup); native auto-merge
waits for them and merges only when they pass. Pending checks never disable the bot's auto-merge; a failing check
simply blocks the merge.

The write is GitHub's GraphQL `enablePullRequestAutoMerge` with merge method
`MERGE` (a merge commit) and `expectedHeadOid` pinned to the assessed head.
Branch deletion comes from the repository setting `delete_branch_on_merge`.

**Ownership.** The bot adds `auto-merge:bot` when it enables auto-merge. An
active auto-merge without that label belongs to a human: the bot never takes
it over and never disables it. The one exception is `do-not-merge`
(decision B), which disables any auto-merge, whoever enabled it.

**Revocation.** On a push, `hold` disables the bot's auto-merge at once, before
the new head is reviewed (GitHub keeps auto-merge on when someone with write
access pushes). `publish` then decides afresh for the new head. A worse
verdict or any failed gate disables the bot's auto-merge and removes
`auto-merge:bot`. While GitHub still computes mergeability, the bot neither
enables nor disables.

**Already mergeable (decision D).** GitHub refuses to arm auto-merge on a pull
request whose checks are already done. `publish` treats the refusal as "not
enabled": the run stays green, `needs-review` is added and the sticky comment
says auto-merge could not be armed. The maintainer merges by hand. The bot
never merges directly.

**Bot merges start no workflows.** A merge done by auto-merge that
`GITHUB_TOKEN` enabled triggers no `push` workflow on `main` (`ci.yml`,
`maintenance-gate.yml`, `pages.yml`). Pages is built from `skills.json` and
`site/`, which are never low risk, so the site is unaffected. CI on `main`
runs again with the next human push.

## Setup

All settings live under the repository's **Settings** tab.

1. **Model token.** *Secrets and variables → Actions → Secrets*:
   `CLAUDE_CODE_OAUTH_TOKEN`, created locally with `claude setup-token` from
   the maintainer's Claude subscription. It is valid for one year; see
   [token renewal](#token-renewal). `claude.yml` reads the same secret. Only
   the `review` step of `factory-pr-review.yml` sees it; the caller passes it
   by name. Without it every review is
   `review:unavailable` with `needs-review`. Why a subscription and not an
   API key: [ADR-0012](../adr/0012-pr-review-on-claude-subscription.md).
2. **Model (optional).** *Variables*: `PR_REVIEW_MODEL`, a Claude Code model
   alias (`sonnet`, `opus`, `haiku`) or full model name. Unset means `sonnet`
   (`DEFAULT_MODEL` in `scripts/pr_review.py`). Delete the variable if it
   still holds an OpenCode Zen model ID: the CLI rejects it, and every review
   becomes `review:unavailable`.
3. **Auto-merge switch.** *Variables*: `PR_AUTO_MERGE`. Leave it unset until
   step 5 of the [rollout](#rollout). Any value but `true` keeps auto-merge
   off.
4. **Labels.** Nothing to create: `publish` creates its ten labels on first
   use and leaves existing ones as they are.
5. **Repository settings.** *General → Pull Requests*: **Allow auto-merge**
   on, **Automatically delete head branches** on (`delete_branch_on_merge`).
   On 2026-11-07 both were on. Check with
   `gh api repos/fabiandistler/agents --jq '{allow_auto_merge, delete_branch_on_merge}'`.
6. **Ruleset (one-time, manual).** *Rules → Rulesets → `default` → Require
   status checks to pass*: require `checks`, `bats`, `mermaid`, `secrets` and
   `pr-review/verdict` from GitHub Actions; add the last
   [in this order](pr-review-verdict-status.md#adding-it-to-the-ruleset).
7. **Actions policy.** *Actions → General*: Actions enabled, and the
   allowed-actions policy permits `actions/checkout`, `actions/setup-python`,
   `actions/upload-artifact` and `actions/download-artifact` (all pinned to
   commit SHAs).
8. **Event policy (one-time, manual).** *Actions → Policies*: an active
   policy that allows `pull_request_target` and `workflow_dispatch` for
   `.github/workflows/pr-review.yml` only: the caller, which carries the
   trigger, not `factory-pr-review.yml`. From 2026-12-02 GitHub blocks
   `pull_request_target` in public repositories without one. Steps, check
   and sources: [pr-review-event-policy.md](pr-review-event-policy.md).

Nothing runs before the workflow is on the default branch: a dispatch needs
the file there, and `pull_request_target` reads it from there.

## Rollout

1. Merge the scripts, tests, docs and workflow with `PR_AUTO_MERGE` unset.
   From then on every pull request event writes labels and the comment.
2. Run the [Actions dry run](#dry-run) on an open docs-only pull request
   (paths under `docs/` outside `docs/agents/` and `docs/adr/`).
3. Observe for a week: labels, verdicts and the comment on real pull
   requests. Check that no `auto-merge:bot` label appears.
4. Make the [ruleset change](#setup) (step 6 of the setup).
5. Set `PR_AUTO_MERGE` to `true`, then record the acceptance runs in the
   [acceptance record](pr-review-acceptance.md).

**Test pull requests must still have checks running.** A docs pull request
whose CI finishes before `publish` runs is already mergeable, so GitHub
refuses to arm auto-merge as "clean" ([decision D](#auto-merge)): the run
stays green but adds `needs-review` and nothing merges. To see an armed
auto-merge, open the test pull request (or push to it) and let `publish` run
while `checks`, `bats`, `mermaid` and `secrets` are still in progress.

## Dry run

**Locally, read-only.** Runs the same scripts against a real pull request.
Needs `gh auth status` to succeed. Run it from the repository root:

```bash
scripts="$PWD/scripts"; pr=NNN; out=/tmp/pr-review-$pr
mkdir -p "$out" && cd "$out"
export GITHUB_TOKEN="$(gh auth token)"
python3 "$scripts/pr_github.py" --repo fabiandistler/agents --pr "$pr" --output context.json
python3 "$scripts/pr_risk.py" --context context.json --output assessment.json
python3 "$scripts/pr_review.py" --context context.json --dry-run --output request.json  # no network
python3 "$scripts/pr_review.py" --context context.json > review.json  # claude -p if CLAUDE_CODE_OAUTH_TOKEN is set
PR_AUTO_MERGE=true python3 "$scripts/pr_publish.py" --live --repo fabiandistler/agents \
  --pr "$pr" --assessment assessment.json --review review.json
```

The last command prints the plan: label changes, the comment body, the
reviewer action and `decision.auto_merge` (`enabled` for an eligible docs
pull request, else `off`, `kept`, `disabled` or `human`). Drop
`PR_AUTO_MERGE=true` to see today's behaviour. `--write` is refused outside
GitHub Actions (exit 7).

**In Actions.** Dispatch with the default `dry_run: true`:

```bash
gh api --method POST \
  repos/fabiandistler/agents/actions/workflows/pr-review.yml/dispatches \
  --input - <<'JSON'
{"ref": "main", "inputs": {"pr": "NNN", "dry_run": "true"}}
JSON
```

Or *Actions → pr-review → Run workflow*. A dry run calls the model once,
re-fetches the pull request, re-checks the head SHA and the policy on that
fresh data and plans exactly what a write run would, then writes nothing.
`hold` does not run on a dispatch. Check:

- `assess`, `review` and `publish` are green;
- the run summary under **PR review decision** shows the risk, the verdict,
  the auto-merge state and the planned labels;
- the pull request has no new labels or comments.

## Linked issues

`pr_github.py --linked-issues` adds up to three same-repository issues the
pull request body closes (`Closes #n`) to the context, as the field
`linked_issues`. `pr_review.py` renders them after the diff, in the room the
capped payload leaves, without marking the review partial; only issues by an
owner, member or collaborator show their text. Fields, caps, failure handling
and framing: [pr-review-linked-issues.md](pr-review-linked-issues.md).

## Manual re-run

- **Fresh review after a model or prompt change:** dispatch as above with
  `"dry_run": "false"`. It writes exactly what a pull request event would.
- **Same run again** (a red job after a transient failure):
  `gh run rerun <run-id>`. A re-run uses the original run's commit. Use
  `--failed` only for a red job: a `review:unavailable` run is green, so
  `--failed` does not retry it.
- **No verdict on the head:** dispatch with `"dry_run": "false"`
  ([verdict status](pr-review-verdict-status.md)).
- **A new push** always triggers a fresh assessment and review.

## Model change

The default is the alias `sonnet`, which follows the current Sonnet model, so
it does not go stale. A misspelled model fails safe as `review:unavailable` on
every pull request.

1. Check the name locally: `claude -p --model <name> --tools "" 'Say OK'`.
2. Set the repository variable `PR_REVIEW_MODEL` to it. No code change is
   needed; unset it to return to the default.
3. Dispatch a dry run and check that the review is not `unavailable`.

Changing `DEFAULT_MODEL` itself is a `scripts/pr_*` change, so its pull request
is high risk and needs a human review.

### CLI update

The review job installs `@anthropic-ai/claude-code` at the exact version
pinned in `.github/workflows/factory-pr-review.yml`; the next step hands that binary
the token. Dependabot does not update it. To update, check the release notes,
change the version, and dispatch a dry run before merging. A test fails if the
pin loses its exact version.

### Token renewal

`claude setup-token` tokens last one year. An expired token makes every review
`review:unavailable`. Run `claude setup-token` locally and replace the secret
`CLAUDE_CODE_OAUTH_TOKEN`; `claude.yml` picks up the same value.

## Quota and cost

- One review job makes one single-turn `claude -p` call: input capped (diff
  2000 lines or 200 KB, request 300 KB, roughly 75k tokens), 300-second
  timeout. Label events, drafts and forks make none. A newer push cancels the
  run for the old head.
- Each review draws on the maintainer's Claude subscription usage limits,
  shared with interactive Claude Code use. No extra money is charged. Fork
  pull requests are never reviewed, so outside contributors cannot spend the
  quota. A reached limit or an outage yields `review:unavailable` and no
  auto-merge, never a pass. `opus` uses the quota faster than `sonnet`.
- Anthropic sizes subscription limits for ordinary, individual use. One
  review per push in the maintainer's own repository is that; do not reuse
  the token for other people's repositories.
- The repository is public, so standard runners cost no Actions minutes.

## Disable and roll back

Before a step that stops reviews, remove `pr-review/verdict` from the
ruleset, or merges wait.

- **Stop auto-merge:** delete `PR_AUTO_MERGE` or set it to `false`. The next
  run per pull request disables the bot's own auto-merge. To stop one pull
  request at once, add `do-not-merge`.
- **Stop model calls:** delete `CLAUDE_CODE_OAUTH_TOKEN` (this also stops
  `claude.yml`), or pause the workflow as below. Pull requests keep their
  risk labels and comment, with `review:unavailable`.
- **Pause everything:**
  `gh api --method PUT repos/fabiandistler/agents/actions/workflows/pr-review.yml/disable`
  (resume with `.../enable`). A disabled workflow cannot be dispatched.
- **Remove:** revert the merge commit in a pull request. Labels and bot
  comments stay; `gh api --method DELETE repos/fabiandistler/agents/labels/risk:low`
  deletes a label from every pull request.

## Known limits

- **Interactive agents still never merge.** The merge guard
  (`scripts/pr_merge_guard.py`, `merge-guard` plugin) is unchanged and blocks
  agents from merging and from enabling auto-merge.
- **No `unlabeled` trigger.** Removing `do-not-merge` re-arms nothing until
  the next push or a dispatch with `"dry_run": "false"`.
- **Small race.** `do-not-merge` added between the final re-fetch and the
  enable write leaves auto-merge on until the `labeled` run of `hold`
  disables it moments later.
- **Fork pull requests are never reviewed by the model,** including those
  from the maintainer's own fork.
- **Partial reviews never auto-merge.** A capped diff, or hidden markup
  (HTML comments, hidden elements, zero-width characters, base64 blobs)
  removed from the diff, marks the review partial in the comment. A docs
  pull request that adds a Markdown comment therefore waits for a human.
