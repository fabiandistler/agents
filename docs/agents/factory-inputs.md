# Factory workflow inputs

Every `workflow_call` input and secret of the factory's reusable workflows,
with its default and an example value, for the
[caller templates](factory-onboarding.md#caller-templates) of the
[onboarding runbook](factory-onboarding.md). The examples come from the first
targets (fabiandistler/dotfiles#61 and fabiandistler/repo-maintenance#153).

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
| `queue_workflow` | `""` | `implementer-queue.yml`, the queue caller; empty: `blocked` and `at-capacity` issues lose `ready-for-agent` |
| `fix_task_workflow` | `""` | `fix-task.yml` (agents; only with a queue caller) |
| secret `CLAUDE_CODE_OAUTH_TOKEN` | required | `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` |

`factory-implementer-queue.yml` takes no secret:

| Name | Default | Example |
| --- | --- | --- |
| `workflow_file` | `implementer.yml` | `implementer.yml` |
| `branch_prefix` | `agent/issue-` | the implementer caller's value |
| `python_version` | `"3.12"` | `"3.12"` |
| `dry_run` | `false` | `${{ github.event_name == 'workflow_dispatch' && inputs.dry_run }}` |
| `fix_task_workflow` | `""` | `fix-task.yml`, the implementer caller's value |

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

`factory-rework.yml`:

| Name | Default | Example |
| --- | --- | --- |
| `pr` | `""` | `${{ inputs.pr }}` |
| `check_command` | required | the implementer caller's value |
| `setup_command` | `""` | the implementer caller's value |
| `submodules` | `false` | `true` (dotfiles) |
| `python_version` | `"3.12"` | `"3.12"` |
| `model` | `sonnet` | `${{ vars.REWORK_MODEL \|\| 'sonnet' }}` |
| secret `CLAUDE_CODE_OAUTH_TOKEN` | required | `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` |

`factory-fix-task.yml`:

| Name | Default | Example |
| --- | --- | --- |
| `run_id` | `""` | `${{ inputs.run_id }}` |
| `dry_run` | `true` | `${{ inputs.dry_run != false }}` |

`factory-triage-label.yml` takes no input and no secret.

Optional repository variables of the caller: `PR_REVIEW_MODEL` (the PR
review's model) and `ISSUE_TRIAGE_MODEL` (the triage's model). Leave
`PR_AUTO_MERGE` unset in a target: auto-merge is this repository's alone
(ADR-0011, ADR-0018).
