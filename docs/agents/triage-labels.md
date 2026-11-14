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

`.github/workflows/triage-label.yml` adds `needs-triage` to every new issue
that opens without a state label. It needs no model and no secret;
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
stop after two bot triages per issue. Issues by people without write access,
bot issues and issues filed with a state label are not sent to the model.
`scripts/test_issue_triage_policy.py` keeps the bot's state labels in sync
with this table.

Setup: the `CLAUDE_CODE_OAUTH_TOKEN` secret of the PR review; the optional
repository variable `ISSUE_TRIAGE_MODEL` (default `sonnet`). A failed or
off-format model answer writes nothing; the run log says why.

## Implementer claim

Adding `ready-for-agent` starts `.github/workflows/implementer.yml`
([ADR-0014](../adr/0014-agent-runs-in-github-actions.md)). Its first write is
`scripts/implementer_claim.py`, which decides what happens to branch
`agent/issue-<n>`:

| Situation | Outcome | What the run does | Who acts next |
| --- | --- | --- | --- |
| The branch does not exist | `claimed` | Builds on the new branch | Nobody |
| The branch exists with no commits of its own and no pull request holds the issue (`needs-info` exit, or a crash before the first push) | `reclaimed` | Fast-forwards the branch to `main`, then builds on it | Nobody |
| An open or merged pull request closes the issue, or an open pull request uses the branch (the stop rule's draft) | `pr-exists` | Ends without changes | The maintainer, on that pull request |
| The branch has commits and no open pull request (a crash after pushing, or a pull request closed unmerged) | `needs-human` | Comments naming the branch, replaces `ready-for-agent` with `ready-for-human`, ends | A person: open a pull request from the branch, or rescue what is needed, delete the branch and add `ready-for-agent` again |
| The issue was opened by an account without write access, and no owner, member or collaborator has posted a comment containing a `## Agent Brief` heading | `no-contract` | Comments, removes `ready-for-agent`, ends before any branch exists | A person with write access: post the brief, then add `ready-for-agent` again |
| A blocker in the issue body, the latest comment by a person with write access containing a `## Agent Brief` heading, or the native dependencies is not closed as completed, or a "Blocked by" entry names no issue of this repository (a title, another repository's issue or a pull request) | `blocked` | Comments naming the blockers, removes `ready-for-agent`, ends before any branch exists | A person: add `ready-for-agent` again once every blocker is done, or rewrite an unresolvable entry as `#<n>` or remove it once it is done |
| Another implementer run started working first | `at-capacity` | Comments naming the capacity reason, removes `ready-for-agent`, ends before any branch exists | A person: add `ready-for-agent` again when that run has ended |
| Any other API error | `failed` | Writes `RUN FAILED: claim (<reason>)`, so the run turns red | The maintainer reads the run; a retry is safe |

The brief is the latest comment by a person with write access that has a
`## Agent Brief` heading at the start of a line, so the AI disclaimer the triage
skill puts first does not hide it. A trusted comment counts with its brief in a
`<details>` block too; the triage bot's draft brief does not, because the bot's
association is not a trusted one and the maintainer posts the brief (ADR-0013).
A heading inside code or an HTML comment is no brief.

**Decision (2026-11-11, #770): `Blocked by <URL>`.** A line starting with
`Blocked by` followed by a GitHub URL declares a blocker, as `Blocked by #<n>`
does, with or without a colon:

- `https://github.com/<owner>/<repo>/issues/<n>` of this repository (owner and
  name in any case) is blocker `#<n>` and is checked like it.
- A pull request URL, of this repository or another, stays unresolved and
  blocks: the gate's only done state is an issue closed as completed, which a
  pull request never reaches. Counting it as `#<n>` would name a blocker that
  can never clear.
- An issue URL of another repository stays unresolved and blocks. The claim's
  token cannot be shown to read other repositories, so the blocker cannot be
  checked; ignoring it would let the run start on a ticket a person marked as
  waiting, which is the silent fail-open this gate exists to stop. The comment
  says so, and a person removes the line once that blocker is done.

Runs for one issue share a concurrency group, so a branch that exists at claim
time never belongs to a live run of this workflow.

At most one implementer run works at a time (`MAX_WORKING_RUNS` in the script).
Runs are ordered by the start of their `implement` job, then by run id; only
runs earlier in that order count, so of two simultaneous starts exactly one
stops. The check reads the Actions API, so it can lag a few seconds; a run about
to end still counts, and the ticket then waits for a person to re-label it.

An issue stopped as `no-contract`, `blocked` or `at-capacity` carries no state label until a
person adds `ready-for-agent` again. Nothing restarts it on its own: a blocker
closing fires no run. The triage workflows do not act on it either; they ignore
the bot's comment, and their state check accepts an issue without a state.

## Rework

When the automated review of an implementer pull request ends with
`concerns` or `block`, `.github/workflows/rework.yml` may run one model round
that fixes only those findings ([ADR-0015](../adr/0015-rework-task.md)). Its
model-free gate, `scripts/rework_gate.py` over `scripts/rework_policy.py`,
decides from the review run's artifacts and the live pull request:

| Situation | Outcome | What the run does | Who acts next |
| --- | --- | --- | --- |
| Non-pass review with findings of the live head, fewer than two round markers, no other rework run working | `proceed` | Posts `<!-- rework-round:<k> head:<sha> -->`, hands the findings to the model job as a file; it fixes them, pushes, comments fixed or declined | The next review of the pushed commit |
| Two round markers and a new non-pass verdict | `handoff` | Comments once per head on the pull request, replaces `ready-for-agent` with `ready-for-human` on the issue; no model runs | A person, on the pull request |
| The model job's checks stay red after two rounds | (model job) | Pushes nothing, comments, replaces `ready-for-agent` with `ready-for-human` | A person, on the pull request |
| Anything else: a pass or unavailable review, no findings, a draft, `do-not-merge`, a head that moved, a marker for this head, an issue with `ready-for-human`, another rework run working, a pull request not opened by `claude[bot]` from `agent/issue-<n>` | `stop` | Writes nothing | Nobody; a manual run (Actions → rework → Run workflow) retries |

Only markers by `github-actions[bot]` count, so a quoted marker neither spends
nor resets a round. Setup: the secrets of the implementer; the optional
repository variable `REWORK_MODEL` (default `sonnet`).

## Pull request labels

Pull requests use separate label families, written by the model-free `hold`
and `publish` jobs of `.github/workflows/pr-review.yml` ([runbook](pr-review-runbook.md)).
They never carry the issue roles above. `publish` creates all ten labels on
first use (`LABELS` in `scripts/pr_labels.py`) and keeps one label per
family, removing stale ones.

**Risk** (deterministic, `scripts/pr_risk.py`; the model can only raise it):

| Label | Meaning | Action |
| --- | --- | --- |
| `risk:low` | Only `docs/**` outside `docs/agents/` and `docs/adr/`, `GLOSSARY.md`, `MAINTENANCE.md`, `maintenance/reports/**` | Auto-merge eligible when every gate holds |
| `risk:medium` | Skills, instructions, agent docs (`AGENTS.md`, `CLAUDE.md`, `docs/agents/**`), `README.md`, ADRs, plugins, the `.claude/` mirror, tests, non-gate scripts | `needs-review`; never auto-merged |
| `risk:high` | Workflows, installer, gate, guard, hook and build scripts, the review pipeline itself, config and pins, binary files, unknown paths, forks, unreadable diffs | `needs-review`; never auto-merged |

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
