# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Canonical role      | Label in our tracker | Meaning                                  |
| ------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`      | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`        | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`   | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`   | `ready-for-human`    | Requires human implementation            |
| `wontfix`           | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

The [factory user guide](../factory/README.md) shows where each label falls in
an issue's life; the [architecture](../factory/architecture.md#label-state-machine)
draws the state labels as a state machine.

`.github/workflows/triage-label.yml` adds `needs-triage` to every new issue
that opens without a state label, except a wayfinder map or ticket: an issue
that opens with a label containing `wayfinder:` is a decision, not
implementation work, and carries no triage label (#896). Only a label set in
the create call counts; one added later comes too late. It calls the reusable workflow
`.github/workflows/factory-triage-label.yml`
([ADR-0018](../adr/0018-reusable-factory-workflows.md)), which holds the job
and its state-label guard and takes no inputs. It needs no model and no secret;
`scripts/test_triage_label_workflow.py` keeps its state labels in sync with
this table.

## Automated triage

`.github/workflows/issue-triage.yml` triages issues by collaborators
([ADR-0013](../adr/0013-automated-issue-triage.md)). It posts one comment
marked `<!-- issue-triage-bot -->` with a category, a recommended state, where
it looked in the code, and either questions or a draft agent brief.

| The model recommends | The bot leaves | Who acts next |
| --- | --- | --- |
| Recommends `needs-info` | Sets `needs-info` | The reporter answers; the issue returns to `needs-triage` |
| Recommends `ready-for-agent` or `ready-for-human` | Keeps `needs-triage` | The maintainer sets the state and posts the brief |
| Recommends `wontfix` | Keeps `needs-triage` | The maintainer sets `wontfix` and closes |

Runs start on a new issue, on the reporter's reply to `needs-info`, when the
maintainer adds `needs-triage` again, and from a manual run (Actions →
issue-triage → Run workflow, dry run by default). The two automatic triggers
stop after two bot triages per issue. A new issue gets one automated triage,
even when it is filed with `needs-triage`: the workflow filter drops that
issue's `opened` run. When two runs do start for a new issue, the per-issue
concurrency group starts the second only after the first has posted its
triage, so the second finds the bot triage and skips without a model call.
The skip relies on that order: `assess` reads the comments when it starts, and
`publish` does not check again. Adding `needs-triage` starts a run only when a
person's label event is newer than the last bot triage; a bot's label event
never does.
Issues by people without write access, bot issues and issues filed with a
state label are not sent to the model. The workflow filter already drops a
bot's issue, an issue filed with a state label other than `needs-triage` and
an issue filed with a `wayfinder:` label, so none of them starts a runner. A
wayfinder issue is still triaged when a person adds `needs-triage` to it or
starts a manual run.
The state labels live in the handoff protocol module
(`scripts/factory_handoff.py`); `scripts/test_issue_triage_policy.py` keeps
them in sync with this table.

Setup: the `CLAUDE_CODE_OAUTH_TOKEN` secret of the PR review; the optional
repository variable `ISSUE_TRIAGE_MODEL` (default `sonnet`). A failed or
off-format model answer writes nothing; the run log says why.

`issue-triage.yml` is a thin caller of the reusable workflow
`.github/workflows/factory-issue-triage.yml`
([ADR-0018](../adr/0018-reusable-factory-workflows.md)), which holds the three
jobs, their filter and the per-issue concurrency group. Its inputs are `issue`
and `dry_run` (read on a manual run only) and `setup_command` (run in the
caller's checkout before the model step, without secrets); its secret is
`CLAUDE_CODE_OAUTH_TOKEN`, passed by name. A caller grants `contents: read` and
`issues: write`, and `ISSUE_TRIAGE_MODEL` is read from the caller's
repository. The scripts and the prompt are fetched from the workflow's own
commit into `$RUNNER_TEMP/factory`, outside the workspace, as in the PR
review, so the model never reads them.

## Implementer claim and queue

Adding `ready-for-agent` starts the implementer. Its claim on branch
`agent/issue-<n>`, the outcomes of that claim, and the queue that starts
waiting issues one at a time are in
[implementer claim and queue](implementer-queue.md).

## Rework

When the automated review of an implementer pull request ends with
`concerns` or `block`, `.github/workflows/rework.yml` may run one model round
that fixes only those findings ([ADR-0015](../adr/0015-rework-task.md)). It
calls the reusable `.github/workflows/factory-rework.yml`, which other
repositories call too ([factory onboarding](factory-onboarding.md)). The
workflow is added to `main` by hand; until it is there, nothing below runs. Its
model-free gate, `scripts/rework_gate.py` over `scripts/rework_policy.py`,
decides from the review run's artifacts and the live pull request:

| Situation | Outcome | What the run does | Who acts next |
| --- | --- | --- | --- |
| Non-pass review with findings of the live head, fewer than two round markers, no other rework run working | `proceed` | Posts `<!-- rework-round:<k> head:<sha> -->`, hands the findings to the model job as a file; it fixes them, pushes, comments fixed or declined | The next review of the pushed commit |
| Two round markers and a new non-pass verdict | `handoff` | Comments once per head on the pull request, replaces `ready-for-agent` with `ready-for-human` on the issue; no model runs | A person, on the pull request |
| The model job's checks stay red after two rounds | (model job) | Pushes nothing, comments, replaces `ready-for-agent` with `ready-for-human` | A person, on the pull request |
| The model job declines every finding | (model job) | Pushes nothing, comments every finding as declined with its reason | A person, on the pull request |
| Anything else: a pass or unavailable review, no findings, a draft, `do-not-merge`, a head that moved, a marker for this head, an issue with `ready-for-human`, another rework run working, a pull request not opened by `claude[bot]` from `agent/issue-<n>` | `stop` | Writes nothing | Nobody; a manual run (Actions → rework → Run workflow) retries |

Only markers by `github-actions[bot]` count, so a quoted marker neither spends
nor resets a round. Setup: the secrets of the implementer; the optional
repository variable `REWORK_MODEL` (default `sonnet`).

## Fix task

`.github/workflows/fix-task.yml`, through the reusable
`.github/workflows/factory-fix-task.yml`, runs `scripts/factory_failure.py` after a
factory run (`implementer`, `skill-audit`, `issue-triage`, `pr-review`,
`rework`, `retro`) concludes `failure` or `timed_out`
([ADR-0016](../adr/0016-fix-task.md)). It needs no model. It files issues with the label `factory-failure`, which it
creates on first use, plus `bug` and `needs-triage`. Each issue carries the
marker `<!-- factory-failure:<hash> -->` of one failure signature: workflow
path, job, step and the normalized reason.

| Situation | Outcome | Who acts next |
| --- | --- | --- |
| No issue by `github-actions[bot]` carries the signature's marker | A new issue `<workflow>: <job>/<step> failed` | The maintainer triages it |
| An open bot issue carries the marker | One comment with the run link, attempt and date | The maintainer, on that issue |
| That run attempt is already recorded on the issue | Nothing | Nobody |
| Only a closed bot issue carries the marker | A new issue that names the closed one | The maintainer triages it |
| A failed implementer run whose `run-name` names an issue labelled `factory-failure` | One comment on that issue, nothing new | The maintainer revises the brief or takes it over |
| The run was cancelled or succeeded, or its workflow is not watched (`ci.yml`, the Fix task itself) | Nothing | Nobody |

A fix attempt is a person posting an agent brief on the issue and adding
`ready-for-agent`; the Fix task never sets it. A manual run (Actions →
fix-task → Run workflow, with a run id) plans only unless `dry_run` is false.

## Pull request labels

Pull requests use separate label families, written by the model-free `hold`
and `publish` jobs of `.github/workflows/factory-pr-review.yml`, which
`.github/workflows/pr-review.yml` calls ([runbook](pr-review-runbook.md)).
They never carry the issue roles above. `publish` creates all ten labels on
first use (`LABELS` in `scripts/pr_labels.py`) and keeps one label per
family, removing stale ones.

**Risk** (deterministic, `scripts/pr_risk.py`; the model can only raise it):

| Label | Meaning | Action |
| --- | --- | --- |
| `risk:low` | Only plain Markdown (`*.md`, no dot-directory in the path) under `docs/` outside `docs/agents/`, `docs/adr/` and `docs/factory/`, or under `maintenance/reports/`; `GLOSSARY.md`, `MAINTENANCE.md`. An agent instruction file name is never low | Auto-merge eligible when every gate holds |
| `risk:medium` | Skills, instructions, agent docs (`SKILL.md`, `AGENTS*.md`, `CLAUDE*.md` and `GEMINI.md` anywhere, `docs/agents/**`, `docs/factory/**`), `README.md`, ADRs, plugins, the `.claude/` mirror, tests, non-gate scripts | `needs-review`; never auto-merged |
| `risk:high` | Workflows, installer, gate, guard, hook and build scripts, the review pipeline itself, config and pins, binary files, unknown paths (including anything under `docs/` or `maintenance/reports/` that is not plain Markdown), forks, unreadable diffs | `needs-review`; never auto-merged |

Thresholds raise the path risk: more than 300 changed lines or 20 files makes
it at least medium, more than 1000 lines or 50 files high. Any deletion or
rename makes it at least medium; deleting a skill, workflow, installer or
guard file makes it high. An empty file list or an unmatched path is high.
The label shows the effective risk: the path risk, raised by the model's
suggestion when that is higher.

**Verdict** (from the model review; at most one):

| Label | Meaning | Action |
| --- | --- | --- |
| `review:pass` | The model returned a parseable `pass` verdict | Auto-merge eligible with `risk:low` and a complete review |
| `review:concerns`, `review:block` | Findings to read in the sticky comment | `needs-review`; read the findings first |
| `review:unavailable` | Missing key, provider error or timeout | `needs-review`; no auto-merge until a review succeeds |

A draft or fork pull request has no verdict label: its review is skipped.

**Control labels:**

| Label | Set by | Meaning |
| --- | --- | --- |
| `needs-review` | `publish` | The maintainer should look: medium or high risk, a non-pass or unavailable verdict, a self-authored pull request, or auto-merge refused because the pull request was already mergeable |
| `do-not-merge` | the maintainer | Hard veto: disables any auto-merge, including a human's, and blocks enabling it |
| `auto-merge:bot` | `publish` | Marks an auto-merge the bot enabled; only that one may it disable later. Never add or remove it by hand |
