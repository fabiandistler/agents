# Issue triage runbook

`.github/workflows/triage.yml` classifies new issues and applies a small,
allowlisted set of labels. It runs when an issue opens, on a daily sweep, and
on manual dispatch. It never comments, closes, assigns, or removes a label.

## Contents

- [Setup](#setup)
- [What the workflow does](#what-the-workflow-does)
- [Security model](#security-model)
- [Label policy](#label-policy)
- [Triage one issue](#triage-one-issue)
- [Run or inspect the sweep](#run-or-inspect-the-sweep)
- [Read a run](#read-a-run)
- [Retry a failed issue](#retry-a-failed-issue)
- [Change the prompt or model](#change-the-prompt-or-model)
- [Quota and cap](#quota-and-cap)
- [Troubleshooting](#troubleshooting)
- [Acceptance record](#acceptance-record)

## Setup

One-time, before the first run:

- The repository secret `CLAUDE_CODE_OAUTH_TOKEN` must exist. Only the
  classify job reads it.
- All seven labels in [triage-labels.md](triage-labels.md) must exist in the
  tracker before the first run. `apply` adds labels by name and never creates
  them. If you edit the right-hand column of the mapping, create the new
  labels first.
- Actions must be enabled. The workflow grants no top-level permission and
  each job gets only what the security model table shows.
- A manual dispatch or the schedule runs the workflow from the default branch
  only. A branch that adds the workflow cannot be dispatched until it is
  merged; test the model-free steps locally first (see
  [Triage one issue](#triage-one-issue)).

Local runs need `gh` authenticated (`gh auth status`). The script uses the
Python standard library only.

## What the workflow does

Three jobs, one issue number per matrix entry:

1. **discover** computes the issue numbers. It takes the event's issue, the
   number passed to a manual dispatch, or — for a schedule or an empty
   dispatch — the open issues that carry no state label. The sweep command
   returns at most ten issues, oldest first.
2. **classify** fetches the issue through `scripts/triage.py fetch`, strips
   HTML comments, CSS-hidden elements, zero-width characters, and base64
   blobs, then asks Claude for one structured decision. It uploads the issue
   document and the decision as an artifact.
3. **apply** downloads the artifact, validates the decision against
   `docs/agents/triage-labels.md`, re-reads the live issue, and adds only the
   labels that policy allows and the issue lacks.

Every issue is its own matrix entry. One failed classification does not stop
the others: apply still runs for the successful entries and writes a
"no decision" note to the run summary for the failed one.

The classifier prompt is [triage-prompt.md](triage-prompt.md). The label
mapping and the automation policy live in
[triage-labels.md](triage-labels.md). Both are read at run time, so a missing
role fails the run instead of inventing a label.

## Security model

The job split is the boundary, not the prompt:

| Job      | Issue permission | Model credential | Tools                             |
| -------- | ---------------- | ---------------- | --------------------------------- |
| discover | `issues: read`   | none             | none                              |
| classify | `issues: read`   | `CLAUDE_CODE_OAUTH_TOKEN` | `Read`, `Glob`, `Grep`  |
| apply    | `issues: write`  | none             | none                              |

- The model cannot comment, close, assign, or label: its job has no issue
  write permission, and its allowed tools are only `Read`, `Glob`, and `Grep`.
- A deny list blocks reading `/proc`, `/sys`, `.env` files, keys, and
  credential directories.
- Issue text is untrusted data. `fetch` removes hidden content before the
  model sees it, and the prompt restates the boundary.
- The model only proposes a decision. `apply` re-validates it, re-reads the
  issue, and refuses to write when the issue is closed or its state labels
  conflict.
- The repository agent instructions forbid agents from merging PRs; this
  workflow has no pull-request permissions at all.

## Label policy

The decision names a category (`bug`, `enhancement`, `unclear`), a state
(`needs-triage` or `ready-for-human`), a confidence from 0 to 1, and a
one-sentence reason. `apply` derives the labels from the category and the
confidence; the requested state is recorded in the summary but does not
override the thresholds.

| Condition                                  | Labels added              |
| ------------------------------------------ | ------------------------- |
| category clear, confidence ≥ 0.8           | category + `ready-for-human` |
| category clear, 0.6 ≤ confidence < 0.8     | category + `needs-triage` |
| category clear, confidence < 0.6           | `needs-triage`           |
| category `unclear`                         | `needs-triage`           |
| classifier fallback or failed run          | none                      |

`bug`, `enhancement`, `needs-triage`, and `ready-for-human` are the only
labels the automation may add. It never adds `wontfix`, `ready-for-agent`, or
`needs-info`. A human label wins over the model: an existing state label in a
different state blocks the whole write, while an existing category only stops
the category from being added. The state is checked first, so an issue that
already carries a category still receives its state label. An issue with two
state labels is refused, not resolved.

## Triage one issue

Dispatch with an issue number. This is the path to use after a classifier
failure or for an issue the sweep has not reached.

```bash
gh api --method POST \
  repos/fabiandistler/agents/actions/workflows/triage.yml/dispatches \
  --input - <<'JSON'
{"ref": "main", "inputs": {"issue": "466"}}
JSON
```

The run adds exactly `needs-triage` to the issue's existing labels when the
classifier is unsure, and the category plus a state when it is sure.

To see what the workflow would do without writing, run the two model-free
steps locally. They need `gh auth status` to succeed.

```bash
mkdir -p .triage/466
python3 scripts/triage.py --repo fabiandistler/agents fetch \
  --issue 466 --output .triage/466/issue.json
# Put a decision at .triage/466/decision.json, then:
python3 scripts/triage.py --repo fabiandistler/agents apply \
  --issue 466 --decision .triage/466/decision.json --dry-run
```

## Run or inspect the sweep

The schedule runs once a day at 05:17 UTC. To run it now, dispatch without an
issue number:

```bash
gh api --method POST \
  repos/fabiandistler/agents/actions/workflows/triage.yml/dispatches \
  --input - <<'JSON'
{"ref": "main", "inputs": {}}
JSON
```

To see the backlog the next sweep would pick up:

```bash
python3 scripts/triage.py --repo fabiandistler/agents list --limit 10
```

The command returns a JSON array of issue numbers, oldest first. Issues that
are pull requests, authored by a bot, or already carry a state label are
excluded. The workflow runs at most two of them in parallel and does not fail
the whole matrix when one issue fails (`fail-fast: false`).

## Read a run

```bash
gh run list --workflow triage.yml --limit 5
gh run view <run-id>
gh run view <run-id> --log-failed
gh run download <run-id> -n triage-decision-466
```

The run summary shows the category, the requested state, the confidence, the
reason, the labels added, and the outcome (`applied`, `dry-run`, or `skipped`
with the reason). The artifact holds `issue.json` (the sanitized input) and
`decision.json` (the model's proposal). Artifacts are kept for seven days.

A run is red when a classification or an apply fails. The failed issue stays
unlabeled, or keeps the labels it had, and the next sweep retries it. The
other matrix entries still complete, and the failed entry's apply job writes a
"no decision" note to the run summary instead of guessing.

## Retry a failed issue

- **Classifier failed:** dispatch the single issue again with the command
  above. The run is independent of the sweep.
- **Apply failed after a good classification:** rerun only the failed jobs.
  The artifact from the same run is still available for seven days.

  ```bash
  gh run rerun <run-id> --failed
  ```

- **Wrong decision:** the workflow records its reason but does not overrule a
  human. Add the correct label yourself; the automation will not remove it or
  add a second state.

## Change the prompt or model

- The prompt is `docs/agents/triage-prompt.md`. Keep its field descriptions
  in sync with the decision schema. The schema itself has one source:
  `DECISION_SCHEMA` in `scripts/triage.py`; the workflow passes
  `python3 scripts/triage.py schema` to `--json-schema`, and `apply` validates
  against the same constants.
- The model is chosen in the `classify` job's `claude_args`: add
  `--model <name>` there. Without the flag the Claude Code Action uses its own
  default, which can change between action releases. A stronger model raises
  the quota cost of every sweep; a cheaper one may lower confidence and send
  more issues to `needs-triage`.
- Changing thresholds means editing `CATEGORY_THRESHOLD` and
  `READY_THRESHOLD` in `scripts/triage.py`, plus the table in this runbook and
  the policy in `triage-labels.md`. The prompt states the same numbers; update
  it too.
- Run `python3 -m pytest -q scripts/test_triage.py scripts/test_triage_workflow.py`
  before opening a PR.

## Quota and cap

The workflow consumes the existing Claude subscription through
`CLAUDE_CODE_OAUTH_TOKEN`; there is no separate provider key. A sweep is
capped at ten issues, runs at most twice a day in practice (the schedule plus
one manual sweep), and gives each classification at most ten turns. A single
manual dispatch costs one classification. If the quota becomes tight, lower
the cap in the discover step or relax the cron before changing the label
policy.

## Troubleshooting

**The issue has no labels.** Read the apply job's summary: `skipped` names the
reason. A closed issue, an existing state label, an agreeing state with the
category already present, and `labels already present` are all deliberate
no-ops rather than failures.

**`apply` says the issue carries conflicting state labels.** The issue has two
of `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`,
`wontfix`. Remove the wrong one by hand; the automation will not guess.

**The run is red at "Classify with Claude".** The action failed or returned
nothing. Check `--log-failed`, then dispatch the issue again. A failed
classification is not treated as `unclear`: the issue stays unlabeled so the
next sweep retries it.

**The run for a newly opened issue is red at "Classify with Claude".** The
action's `checkWritePermissions` rejects issue authors without write access to
the repository, and the workflow leaves `allowed_non_write_users` unset on
purpose. The `issues: opened` path therefore only labels issues from
collaborators; the daily sweep picks up the rest, because it runs as a
scheduled event rather than as the issue author.

**The run is red before classification.** Discovery could not parse
`docs/agents/triage-labels.md` (a missing role or two roles mapped to one
label) or `gh api` failed. Both are configuration errors; the message names
the missing role or the endpoint.

**Permission denied on a label write.** The apply job needs `issues: write`;
the classify job must not have it. Check that the job split in the workflow
still matches the table above. If the repository uses a custom GitHub App,
confirm the app has issue write access.

**Nothing is discovered although issues are unlabeled.** Check that the issues
are open, are not pull requests, are not authored by a bot, and carry none of
the five state labels. `scripts/triage.py list --limit 10` shows the same
selection the sweep uses.

**A label was added that you did not want.** Remove it by hand. The workflow
adds labels only; it cannot undo a previous run, and it will not re-triage an
issue that already carries a state label.

## Acceptance record

Discovery was exercised against the live repository before merge:
`python3 scripts/triage.py --repo fabiandistler/agents list --limit 10`
returned `[466, 604, 608, 610, 609, 611, 620, 622]` — the unlabeled backlog,
oldest first, with pull requests and bot-authored issues excluded. The
workflow itself can only be dispatched from the default branch, so the first
sweep and the newly-opened issue path are recorded here after merge:

- [ ] First sweep: dispatch with no issue number; record the run id, the
      issues it labeled, and the summary lines.
- [ ] Second sweep: dispatch again; confirm it discovers nothing for the
      already-labeled issues.
- [ ] Newly opened path: open a test issue, confirm it receives a label, and
      confirm there is no bot comment, close, or assignee.
- [ ] Non-collaborator path (#629): open the test issue from an account
      without write access; confirm the `issues: opened` run fails at the
      write-permission check and the next sweep labels the issue. If no such
      account is available, record that this path was not exercised.
- [ ] Check that the parent spec #625 stays open and unchanged.
