# Optional callers

Callers a target may add after the stages of the
[factory onboarding](factory-onboarding.md): Retro, the PR issue-link check and
the hand-applied follow-up. The onboarding check does not require them. Their
inputs are in [factory workflow inputs](factory-inputs.md).

## Retro

`.github/workflows/retro.yml`: about one merged agent
pull request in ten becomes one proposed change to the instruction texts you
list. The gate's floor is the commit that adds this file, so add it by a
squash merge, and say in the pull request that the `cron:` line needs
**Squash and merge** ([changing a task](../factory/changing-a-task.md), item 9).
Pass the implementer's `setup_command`, `submodules` and a `check_command`
that runs the target's checks. `editable_paths` names only files the model
may rewrite: never `.github/`, `.claude/` or a vendored file. Add `retro` to
the `workflow_run` list of the Fix caller in the onboarding runbook. The Retro pull request's body
starts with `No issue:`, so the target needs the PR issue-link check or none.

```yaml
name: retro
on:
  schedule:
    - cron: "23 6 * * *" # pick another minute; scheduled runs start on the default branch only
      timezone: Europe/Berlin
  workflow_dispatch:
permissions: {}
jobs:
  retro:
    permissions:
      contents: read
      pull-requests: write
      issues: write
      actions: read
      id-token: write
    uses: fabiandistler/agents/.github/workflows/factory-retro.yml@<SHA> # agents main, <date>
    with:
      check_command: scripts/check.sh
      editable_paths: |
        AGENTS.md
        docs/agents/
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## PR issue links

`.github/workflows/pr-issue-links.yml` fails a pull request body that names no
issue with a closing keyword and does not say `No issue: <reason>`. Model-free,
no secret. Skip the pull requests whose body a tool writes, such as
Dependabot's, with an `if:` on the calling job; the check would fail each one.
Do not make it a required check before you have seen it pass on a few
pull requests.

```yaml
name: pr-issue-links
on:
  pull_request:
    types: [opened, edited, synchronize, reopened, ready_for_review]
permissions: {}
jobs:
  issue-links:
    if: github.event.pull_request.user.login != 'dependabot[bot]'
    permissions:
      contents: read
      pull-requests: read
    uses: fabiandistler/agents/.github/workflows/factory-pr-issue-links.yml@<SHA> # agents main, <date>
```

## Hand-applied follow-up

`.github/workflows/hand-part-follow-up.yml` files one `ready-for-human` issue
for each top-level `##` section ending in "to add by hand" of a merged
implementer pull request, and links it from the original issue. An implementer
run cannot write `.github/workflows/`, `.claude/` or
`.pre-commit-config.yaml`, so its brief asks for that YAML in such a section.
The called job filters on a merged pull request by the Claude GitHub App from
an `agent/issue-` head. Model-free, no secret.

```yaml
name: hand-part-follow-up
on:
  pull_request:
    types: [closed]
permissions: {}
jobs:
  file-follow-up:
    permissions:
      contents: read
      issues: write
    uses: fabiandistler/agents/.github/workflows/factory-hand-part-follow-up.yml@<SHA> # agents main, <date>
```
