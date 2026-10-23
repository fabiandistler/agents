# Triage Labels

The skills speak in terms of two category roles and five state roles. This
file maps those roles to the actual label strings used in this repo's issue
tracker. The triage workflow and `scripts/triage.py` read this table, so a
missing role fails the run instead of silently inventing a label.

## Category roles

| Canonical role | Label in our tracker | Meaning            |
| -------------- | -------------------- | ------------------ |
| `bug`          | `bug`                | Something is broken |
| `enhancement`  | `enhancement`        | New feature or improvement |

## State roles

| Canonical role    | Label in our tracker | Meaning                                  |
| ----------------- | -------------------- | ---------------------------------------- |
| `needs-triage`    | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`      | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human` | `ready-for-human`    | Requires human implementation            |
| `wontfix`         | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use
the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Automation policy

The issue-triage workflow may add only `bug`, `enhancement`, `needs-triage`,
and `ready-for-human`.

It never adds `wontfix`, `ready-for-agent`, or `needs-info`: those need a
human decision, an agent brief, or a question to the reporter. It never
comments, closes, or assigns an issue, and it never removes a label.

An issue carries at most one category and one state. The workflow adds a
label only when it is missing, and an issue that already carries a state
label is left alone by the sweep. A label a human set wins over the model's
suggestion.
