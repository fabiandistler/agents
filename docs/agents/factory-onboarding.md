# Factory onboarding runbook

For the maintainer who puts another repository on the factory: the triage
label, the issue triage, the PR review and the implementer, each called from
the target as a reusable workflow of this repository
([ADR-0018](../adr/0018-reusable-factory-workflows.md)). This page lists what
to add, what to set by hand and in which order, and how to check the result
with `scripts/factory_onboarding_check.py`.

## Contents

- [Before you start](#before-you-start)
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

## Caller templates

One file per factory workflow, in the target's `.github/workflows/`. Each
starts with `permissions: {}`; the calling job grants the scopes from
ADR-0018's table (the PR review with `statuses: write` as well), pins the
reusable workflow to a full 40-hex commit SHA with the date as a comment, and
passes `CLAUDE_CODE_OAUTH_TOKEN` by name under `secrets:`, never with
`secrets: inherit`. This repository's `triage-label.yml`, `issue-triage.yml`,
`pr-review.yml` and `implementer.yml` are the model, with `./` replaced by the
pinned path. Replace `<SHA>` and `<date>` with the same values in all four.

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
    uses: fabiandistler/agents/.github/workflows/factory-triage-label.yml@<SHA> # <date>
```

`.github/workflows/issue-triage.yml`:

```yaml
name: issue-triage
on:
  issues:
    types: [opened, labeled]
  issue_comment: # zizmor: ignore[dangerous-triggers]
    types: [created]
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
    uses: fabiandistler/agents/.github/workflows/factory-issue-triage.yml@<SHA> # <date>
    with:
      issue: ${{ inputs.issue }}
      dry_run: ${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

`.github/workflows/pr-review.yml`. A target that runs zizmor keeps the inline
ignore on the trigger, as this repository's `pr-review.yml` does (and on
`issue_comment` in the triage caller above). Others may drop the comments.

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
    uses: fabiandistler/agents/.github/workflows/factory-pr-review.yml@<SHA> # <date>
    with:
      pr: ${{ inputs.pr || '' }}
      dry_run: ${{ inputs.dry_run != false }}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

`.github/workflows/implementer.yml`. Keep the `run-name`: the claim script
and the Fix and Retro tasks find a run by it.

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
      actions: read
      id-token: write
    uses: fabiandistler/agents/.github/workflows/factory-implementer.yml@<SHA> # <date>
    with:
      issue: ${{ inputs.issue }}
      check_command: scripts/check.sh
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## Inputs and secret

Every `workflow_call` input and secret, with its default and an example value.
The examples come from the first targets (fabiandistler/dotfiles#61 and
fabiandistler/repo-maintenance#153).

`factory-implementer.yml`:

| Name | Default | Example |
| --- | --- | --- |
| `issue` | `""` | `${{ inputs.issue }}` |
| `check_command` | required | `scripts/maintenance-baseline.sh` |
| `setup_command` | `""` | `pip install -r requirements-dev.txt` |
| `submodules` | `false` | `true` (dotfiles) |
| `python_version` | `"3.12"` | `"3.12"` (dotfiles) |
| `model` | `opus` | `opus` |
| `branch_prefix` | `agent/issue-` | `agent/issue-` |
| secret `CLAUDE_CODE_OAUTH_TOKEN` | required | `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` |

`factory-pr-review.yml`; the effect of each input is in the
[input table](pr-review-reusable-workflow.md):

| Name | Default | Example |
| --- | --- | --- |
| `pr` | `""` | `${{ inputs.pr \|\| '' }}` |
| `dry_run` | `true` | `${{ inputs.dry_run != false }}` |
| `skip_head_prefixes` | `""` | `maintenance/` (repo-maintenance) |
| `standards_path` | `""` | `instructions/review-standards.md` (repo-maintenance) |
| `fail_on_unavailable` | `false` | `true` (dotfiles) |
| `quiet_logs` | `false` | `true` (dotfiles) |
| `setup_command` | `""` | `scripts/install-runner-standards.sh` (dotfiles) |
| secret `CLAUDE_CODE_OAUTH_TOKEN` | required | `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` |

`factory-issue-triage.yml`:

| Name | Default | Example |
| --- | --- | --- |
| `issue` | `""` | `${{ inputs.issue }}` |
| `dry_run` | `true` | `${{ github.event_name != 'workflow_dispatch' \|\| inputs.dry_run }}` |
| `setup_command` | `""` | `pip install -r requirements-dev.txt` |
| secret `CLAUDE_CODE_OAUTH_TOKEN` | required | `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` |

`factory-triage-label.yml` takes no input and no secret.

Optional repository variables of the caller: `PR_REVIEW_MODEL` (the PR
review's model) and `ISSUE_TRIAGE_MODEL` (the triage's model). Leave
`PR_AUTO_MERGE` unset in a target: auto-merge is this repository's alone
(ADR-0011, ADR-0018).

## One SHA for all callers

All callers of a target pin the same commit of `fabiandistler/agents` `main`,
and one pull request bumps them together. A bump takes effect once it is
merged (default-branch rule). Whether Dependabot bumps reusable-workflow refs
is open (ADR-0018, open question 5): bump by hand until a Dependabot run shows
otherwise.

```bash
gh api repos/fabiandistler/agents/commits/main --jq .sha
```

## Manual steps, in order

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
the PR review, then the implementer. Until a stage is enabled, its
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
