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
