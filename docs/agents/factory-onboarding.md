# Factory onboarding runbook

For the maintainer who puts another repository on the factory: the triage
label, the issue triage, the PR review, the implementer and its queue, the
Rework task and the Fix task, each called from the target as a reusable workflow of this
repository
([ADR-0018](../adr/0018-reusable-factory-workflows.md)). This page lists what
to add, what to set by hand and in which order, and how to check the result
with `scripts/factory_onboarding_check.py`. For a new repository, start with
the [setup wizard](#setup-wizard); the [manual steps](#manual-steps-in-order)
are the fallback. The factory's day-to-day use is in the
[user guide](../factory/README.md), its design in the
[architecture](../factory/architecture.md).

## Contents

- [Before you start](#before-you-start)
- [Setup wizard](#setup-wizard)
- [Caller templates](#caller-templates)
- [Inputs and secret](#inputs-and-secret)
- [One SHA for all callers](#one-sha-for-all-callers)
- [Manual steps, in order](#manual-steps-in-order)
- [Start slow](#start-slow)
- [First implementer run probes the token's rights](#first-implementer-run-probes-the-tokens-rights)
- [Rollback](#rollback)
- [Cost](#cost)

## Before you start

- **agents stays public.** Every factory job except the triage label fetches
  the factory scripts with an anonymous `git fetch` of
  `job.workflow_repository` at `job.workflow_sha` into `$RUNNER_TEMP/factory`,
  without a credential. Every caller therefore depends on
  `fabiandistler/agents` staying public: made private, every caller's "Fetch
  the factory scripts" step fails.
- **Fixed names.** The Rework and Fix tasks find the other tasks' runs by
  file path and workflow name, so the callers keep the names of the
  templates below: `.github/workflows/pr-review.yml` named `pr-review`,
  `implementer.yml` named `implementer`, `implementer-queue.yml` named
  `implementer-queue`, `issue-triage.yml` named `issue-triage`, `rework.yml`
  named `rework`. Rework serves only branches
  `agent/issue-<n>`, the implementer's default `branch_prefix`.
- **Default-branch rule.** Merge each caller to the target's default branch
  before its first run. Issue events run the default branch's file anyway
  (`pull_request_target` the base branch's), and the implementer's App token
  exchange checks the calling file, with identical content, against the
  default branch. A caller changed on a branch, a pin bump in an open pull
  request included, gets no App token until it is merged. A
  `401 … Workflow validation failed` from the exchange points here first.
- **Brakes without rulesets.** A private target on GitHub Free has no
  rulesets, so no check can be required
  ([private repos have no rulesets](../wiki/problems/private-repos-no-rulesets.md)).
  The default-branch push guard
  ([#789](https://github.com/fabiandistler/agents/issues/789),
  `scripts/default_branch_push_guard.py`) stops agent pushes to the default
  branch, and the maintainer merges only on green. A public target can require
  its checks with a ruleset and needs an event policy for
  `pull_request_target` ([event policy](pr-review-event-policy.md); ADR-0018,
  "Brakes in target repositories").

## Setup wizard

The first step for a new repository. `scripts/factory-repo-setup.sh` does
everything outside the caller files with the maintainer's own `gh` login, in
six stages:

1. Preconditions: `gh auth status`, the repository is reachable, and what its
   visibility means (a private repository on GitHub Free gets no ruleset).
2. Labels: the five state labels and the categories `bug` and `enhancement`,
   created if missing; an existing label keeps its colour and description.
3. Secret: `CLAUDE_CODE_OAUTH_TOKEN` from hidden entry or `--token-file`,
   created with `claude setup-token`. The value is never printed or logged; an
   existing secret is replaced only after a confirmation. The token must be
   one word on one line (surrounding whitespace is dropped); one that does not
   start with `sk-ant-oat` is set only after a confirmation.
4. Actions allow-list: if the repository allows only selected actions, adds
   `fabiandistler/agents/.github/workflows/*` and the actions the factory
   workflows use. An unrestricted policy is left unchanged. GitHub's REST docs
   say `patterns_allowed` applies only to public repositories, so on a private
   one the wizard asks you to check the list in the repository's Actions
   settings.
5. Clicks without an API: opens the page for the Claude GitHub App and for the
   Dependabot runner type, with the path to click.
6. Verify: runs `scripts/factory_onboarding_check.py` with the `gh` login's
   token.

```bash
scripts/factory-repo-setup.sh --repo OWNER/NAME          # dry run: prints every planned write
scripts/factory-repo-setup.sh --repo OWNER/NAME --apply  # performs them, asks for the token and the clicks
```

Every stage is safe to re-run. The wizard writes no file: the caller workflows
come from the template repository or from [Caller templates](#caller-templates),
and the callers still need merging to the default branch (step 6 below). If the
wizard cannot run, follow the [manual steps](#manual-steps-in-order).

## Caller templates

One file per factory workflow, in the target's `.github/workflows/`. Each
starts with `permissions: {}`; the calling job grants the scopes from
ADR-0018's table (the PR review with `statuses: write` as well), pins the
reusable workflow to a full 40-hex commit SHA with the comment
`# agents main, <date>`, and passes `CLAUDE_CODE_OAUTH_TOKEN` by name under
`secrets:`, never with `secrets: inherit`. The comment has more than one word
because zizmor's online `ref-version-mismatch` audit reads a one-word comment
after a SHA as a version and flags it when that SHA carries no such tag. This
repository's `triage-label.yml`, `issue-triage.yml`, `pr-review.yml`,
`implementer.yml`, `implementer-queue.yml`, `rework.yml` and `fix-task.yml`
are the model, with `./` replaced by the pinned path (the triage caller
without `issue_comment`, see below; the Fix caller with the target's own watch
list). Replace `<SHA>` and `<date>` with the same values in all seven.

`.github/workflows/triage-label.yml`:

```yaml
name: Triage label
on:
  issues:
    types: [opened]
permissions: {}
jobs:
  label:
    permissions:
      issues: write
    uses: fabiandistler/agents/.github/workflows/factory-triage-label.yml@<SHA> # agents main, <date>
```

`.github/workflows/issue-triage.yml`:

```yaml
name: issue-triage
on:
  issues:
    types: [opened, labeled]
  workflow_dispatch:
    inputs:
      issue:
        description: Issue number
        required: true
        type: string
      dry_run:
        description: Print the planned actions instead of applying them
        required: false
        type: boolean
        default: true
permissions: {}
jobs:
  triage:
    permissions:
      contents: read
      issues: write
    uses: fabiandistler/agents/.github/workflows/factory-issue-triage.yml@<SHA> # agents main, <date>
    with:
      issue: ${{ inputs.issue }}
      dry_run: ${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

The triage caller does not subscribe to `issue_comment`, which zizmor rates as
a dangerous trigger. A reporter's reply to `needs-info` is therefore not
re-triaged until a person re-adds `needs-triage`. A target that wants
automatic re-triage may add `issue_comment: [created]` back, with a second
justified `# zizmor: ignore[dangerous-triggers]` beside the PR review's.

`.github/workflows/pr-review.yml`. A target that runs zizmor keeps the inline
ignore on the trigger, as this repository's `pr-review.yml` does. Others may
drop the comment.

```yaml
name: pr-review
on:
  pull_request_target: # zizmor: ignore[dangerous-triggers]
    types: [opened, synchronize, reopened, ready_for_review, labeled]
  workflow_dispatch:
    inputs:
      pr:
        description: Pull request number
        required: true
        type: string
      dry_run:
        description: Print the planned actions instead of applying them
        required: false
        type: boolean
        default: true
permissions: {}
jobs:
  pr-review:
    permissions:
      contents: write
      pull-requests: write
      issues: write
      statuses: write
    uses: fabiandistler/agents/.github/workflows/factory-pr-review.yml@<SHA> # agents main, <date>
    with:
      pr: ${{ inputs.pr || '' }}
      dry_run: ${{ inputs.dry_run != false }}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

`.github/workflows/implementer.yml`. Keep the `run-name`: the claim script
and the Fix and Retro tasks find a run by it. `actions: write` is the cap for
the model-free `follow-up` job (#863); the model job asks for `actions: read`
only. GitHub refuses to start the run if the cap is lower, so a caller that
pins a commit from before #863 with `actions: read` must raise it in the same
pull request that bumps the pin. `queue_workflow` names the queue caller
below: only with it does a `blocked` or `at-capacity` issue keep
`ready-for-agent` and wait, and only such a run fails if the queue is
missing or not active. `fix_task_workflow` names the Fix caller; the
`follow-up` job dispatches both after a run the queue started.

```yaml
name: implementer
run-name: "implementer: issue #${{ github.event.issue.number || inputs.issue }}"
on:
  issues:
    types: [labeled]
  workflow_dispatch:
    inputs:
      issue:
        description: Issue number
        required: true
        type: string
permissions: {}
jobs:
  implement:
    permissions:
      contents: read
      actions: write
      id-token: write
    uses: fabiandistler/agents/.github/workflows/factory-implementer.yml@<SHA> # agents main, <date>
    with:
      issue: ${{ inputs.issue }}
      check_command: scripts/check.sh
      queue_workflow: implementer-queue.yml
      fix_task_workflow: fix-task.yml
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

`.github/workflows/implementer-queue.yml`. Model-free, with no secret: it
dispatches `implementer.yml` for the lowest waiting issue after an implementer
run, when an issue closes, hourly, once when this file lands or changes on the
default branch, and by hand (a dry run by default;
[implementer queue](implementer-queue.md#implementer-queue)). It needs the
implementer caller above under the name `implementer`. A pin from before #910
has no `fix_task_workflow` input.

```yaml
name: implementer-queue
on:
  workflow_run: # zizmor: ignore[dangerous-triggers] model-free; reads only the API, checks out no code of the run
    workflows: [implementer]
    types: [completed]
  issues:
    types: [closed]
  schedule:
    - cron: "17 * * * *"
  push:
    branches: [main] # the target's default branch
    paths: [.github/workflows/implementer-queue.yml]
  workflow_dispatch:
    inputs:
      dry_run:
        description: Print the pick and dispatch nothing
        type: boolean
        default: true
permissions: {}
jobs:
  start-next:
    if: >-
      github.event_name != 'workflow_run' ||
      github.event.workflow_run.conclusion != 'skipped'
    permissions:
      actions: write
      contents: read
      issues: read
      pull-requests: read
    uses: fabiandistler/agents/.github/workflows/factory-implementer-queue.yml@<SHA> # agents main, <date>
    with:
      fix_task_workflow: fix-task.yml
      dry_run: ${{ github.event_name == 'workflow_dispatch' && inputs.dry_run }}
```

`.github/workflows/rework.yml`. It starts when the target's `pr-review` run
completes, so it needs the PR review caller above under that name. Pass the
same `check_command`, `setup_command` and `submodules` as the implementer
caller: the model runs the same checks on the same branch. `workflow_run`
fires only from the file on the default branch.

```yaml
name: rework
on:
  workflow_run: # zizmor: ignore[dangerous-triggers] the model-free gate re-checks the run and the pull request
    workflows: [pr-review]
    types: [completed]
  workflow_dispatch:
    inputs:
      pr:
        description: Pull request number
        required: true
        type: string
permissions: {}
jobs:
  rework:
    permissions:
      contents: read
      actions: read
      pull-requests: write
      issues: write
      id-token: write
    uses: fabiandistler/agents/.github/workflows/factory-rework.yml@<SHA> # agents main, <date>
    with:
      pr: ${{ inputs.pr }}
      check_command: scripts/check.sh
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

`retro.yml`, `pr-issue-links.yml` and `hand-part-follow-up.yml` are optional
last stages, with their own page: [Optional callers](factory-onboarding-optional.md).
Add `retro` to the Fix caller's `workflow_run` list below only when the target
has it.

`.github/workflows/fix-task.yml`. The `workflow_run` list names this
repository's own caller workflows by their `name:`, never `fix-task` itself
and never a `factory-*.yml` file: a called workflow fails inside its caller's
run. List only callers the target has. Each caller's path must be in
`WATCHED_WORKFLOWS` of `scripts/factory_failure_policy.py`
(`implementer.yml`, `implementer-queue.yml`, `issue-triage.yml`,
`pr-review.yml`, `rework.yml`, `retro.yml`, and this repository's
`skill-audit.yml`); a run of any other path
is not filed. The triage label caller is not watched. Fix is model-free and
needs no secret.

```yaml
name: fix-task
on:
  workflow_run: # zizmor: ignore[dangerous-triggers] model-free, GITHUB_TOKEN only
    workflows: [implementer, implementer-queue, pr-review, issue-triage, rework]
    types: [completed]
  workflow_dispatch:
    inputs:
      run_id:
        description: Workflow run id
        required: true
        type: string
      dry_run:
        description: Print the plan instead of applying it
        required: false
        type: boolean
        default: true
permissions: {}
jobs:
  file:
    permissions:
      issues: write
      actions: read
      checks: read
    uses: fabiandistler/agents/.github/workflows/factory-fix-task.yml@<SHA> # agents main, <date>
    with:
      run_id: ${{ inputs.run_id }}
      dry_run: ${{ inputs.dry_run != false }}
```

## Inputs and secret

Every `workflow_call` input and secret, with its default and an example value,
and the caller's optional repository variables are in
[factory workflow inputs](factory-inputs.md).

`factory-implementer-queue.yml` had no template here: as of 2026-11-20 only
agents called it. A target that adds a queue caller passes it
`fix_task_workflow` as well, the same file as the implementer caller's, so a
failed queue run that the `follow-up` job dispatched reaches the Fix task
(#909). Updated 2026-11-25 (fabiandistler/repo-maintenance#205): the claim
lets a `blocked` or `at-capacity` issue wait only for the queue that the
implementer caller names in `queue_workflow`, and otherwise removes
`ready-for-agent`. The queue caller now has a [template](#caller-templates),
and the check requires it wherever the implementer is called.

## One SHA for all callers

All callers of a target pin the same commit of `fabiandistler/agents` `main`,
and one pull request bumps them together. A bump takes effect once it is
merged (default-branch rule). Whether Dependabot bumps reusable-workflow refs
is open (ADR-0018, open question 5): bump by hand until a Dependabot run shows
otherwise. A bump past #863 also raises the implementer caller's `actions`
cap to `write` ([template](#caller-templates)).

```bash
gh api repos/fabiandistler/agents/commits/main --jq .sha
```

## Manual steps, in order

The fallback for the [setup wizard](#setup-wizard), and the order it follows.

1. Install the Claude GitHub App on the repository
   (<https://github.com/apps/claude>), or confirm that an existing
   installation covers it (repository settings, "GitHub Apps").
2. Add the `CLAUDE_CODE_OAUTH_TOKEN` repository secret (settings, "Secrets
   and variables", "Actions").
3. If Actions is limited to selected actions and reusable workflows, allow
   `fabiandistler/agents/.github/workflows/*`. GitHub documents that the
   caller's Actions permissions must allow the reusable workflows it uses
   ([Reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations),
   checked 2026-11-14). Whether the actions the factory
   workflows use (`actions/checkout`, `actions/setup-python`,
   `actions/upload-artifact`, `actions/download-artifact`,
   `anthropics/claude-code-action`) must be on the caller's list too is
   unverified: that page does not say. Allow them as well, or record the
   first run's result.
4. Create the five state labels if missing (`needs-triage`, `needs-info`,
   `ready-for-agent`, `ready-for-human`, `wontfix`; their meaning:
   [triage labels](triage-labels.md)), one call per label:

   ```bash
   gh api repos/OWNER/NAME/labels -f name=needs-triage
   ```

5. Public repositories only: a ruleset requiring the repository's checks,
   and an event policy allowing `pull_request_target` for the PR review
   caller's path ([event policy](pr-review-event-policy.md)). Private on
   GitHub Free: write down in the onboarding issue that nothing can be
   required and that the maintainer merges only on green.
6. Merge the callers to the default branch.
7. Run the check and act on every `MISSING` line; check every
   `CANNOT-VERIFY` line by hand:

   ```bash
   GH_TOKEN=$(gh auth token) python3 scripts/factory_onboarding_check.py --repo OWNER/NAME
   ```

The check prints `<STATUS>\t<item>\t<detail>` lines for `labels`,
`visibility`, `rulesets`, `app-installation`,
`secret:CLAUDE_CODE_OAUTH_TOKEN`, `actions-policy`, one `caller:<file>` per
factory workflow, and `pin`. The App installation, the secret and the Actions
policy are not readable with a session token, so they are always
`CANNOT-VERIFY`. Exit 0: no `MISSING` line; 1: at least one; 2: usage error;
3: a GitHub API error, named on stderr.

## Start slow

Enable the stages one at a time: the triage label and the triage first, then
the PR review, then the implementer with its queue, then the Rework task. The Fix task can
come with the first caller it watches. Until a stage is enabled, its
`caller:<file>` line reads `MISSING`, and the `pin` line covers only the
callers present.

## First implementer run probes the token's rights

The token exchange from a private caller is proven (ADR-0018, "Token
exchange"). What the App token may do inside a target is not. Make the first
`ready-for-agent` ticket in a target a trivial one. Its run shows whether the
App token can create the claimed branch, comment, set labels, push and open
a ready-for-review pull request there, and whether that pull request starts
the target's checks and PR review.

If one of these fails, disable the implementer caller ([Rollback](#rollback))
and record the run and the failed operation on
[#786](https://github.com/fabiandistler/agents/issues/786). No fallback is
decided for missing rights. A target that never ran the exchange
(repo-maintenance) proves the exchange in the same run.

## Rollback

Disable the caller workflow in the target's Actions UI ("Disable workflow"),
or remove the caller file in a pull request. Nothing else in the target
depends on it.

## Cost

Runner minutes are billed to the caller's repository: a private repository
draws from the owner's included Actions compute usage
([GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
All targets share one Claude subscription with interactive use and with
this repository's runs (ADR-0018, "Billing and capacity").
