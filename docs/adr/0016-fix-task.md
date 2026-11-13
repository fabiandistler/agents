# ADR-0016: A model-free Fix task files each failed factory run as one deduplicated issue

## Status

Proposed (2026-11-13) for #783. The scripts, tests and docs land first; the
workflow `.github/workflows/fix-task.yml` is added by hand from the pull
request, because the implementer cannot write workflow files.

## Context

The factory workflows fail in two ways. The agent runs (`implementer`,
`skill-audit`) write `RUN FAILED: <reason>` to their step summary and
`scripts/agent_run_report.py` exits 1. The model-free pipelines
(`issue-triage`, `pr-review`) only turn red. Nothing records a failure as an
issue, so a recurring failure is noticed only by reading run pages, and the
step summary is not readable through the REST API.

## Decision

`.github/workflows/fix-task.yml` runs `scripts/factory_failure.py` in one
model-free job.

**Trigger.** `workflow_run`, type `completed`, for `implementer`,
`skill-audit`, `issue-triage` and `pr-review`, and `workflow_dispatch` with a
run id, which plans only unless `dry_run` is false. It acts on conclusion
`failure` or `timed_out` only. Excluded: `cancelled` (a person or a newer run
stopped it, nothing broke), `ci.yml` (a red check on a pull request is the
author's to fix, and it reports itself there), and the Fix task itself, which
does not watch its own runs. `factory_failure_policy.WATCHED_WORKFLOWS` repeats
the list, so a dispatch for any other run plans nothing.

**Readable reason.** `agent_run_report.py` also prints one `::error::` line
with the failed summary's first line (or the no-summary line), capped at 300
characters. GitHub turns it into a check-run annotation, which the REST API
serves.

**Signature.** The workflow path, the job name and the step name of the first
failed step, and a normalized reason: the first annotation starting with
`RUN FAILED`, otherwise the job's first error annotation. URLs, `#<n>`, hex
SHAs and digits become placeholders, whitespace collapses, and the reason is
capped at 200 characters. A 16-hex SHA-256 prefix of the four fields is the
marker `<!-- factory-failure:<hash> -->`.

**Dedupe.** Among issues labelled `factory-failure` and opened by
`github-actions[bot]` with the marker:

- an open one gets one comment (run link, attempt, date), unless that run id
  and attempt is already recorded by the bot in its body or a comment;
- with none, a new issue `<workflow>: <job>/<step> failed` with the labels
  `factory-failure`, `bug` and `needs-triage`: the marker, the run link, job,
  step and the reason in a fenced block with `@` neutralized. No log text;
- with only a closed one, a new issue that names it.

The script reads everything again right before it writes, and creates the
`factory-failure` label on first use; a 422 "already exists" counts as done.

**Fix-related runs.** An implementer run whose `run-name` is
`implementer: issue #<n>` works on issue `<n>`. When that issue carries
`factory-failure`, the failure is a failed fix attempt: it is commented there
and nothing new is filed.

**Model-free.** The job holds `GITHUB_TOKEN` with `issues: write`,
`actions: read` and `checks: read`, no model token and no App token: the
publisher pattern of ADR-0013, with no subscription use.

**Fix attempts are human-started.** The Fix task never adds `ready-for-agent`.
A fix is a person posting an agent brief on the failure issue and adding the
label, which starts an ordinary implementer run. Issues and comments made with
`GITHUB_TOKEN` start no workflow, so the Fix task cannot chain into a fix, a
failed fix cannot file and start another, and every fix passes the PR review
and a human merge.

## Considered options

- **A model reads the logs and writes the issue.** Rejected: logs of a public
  repository can carry secrets and untrusted text, and a model would spend
  the subscription on every red run. The signature needs no judgment.
- **One issue per run.** Rejected: a recurring failure would file one issue
  per run and bury the signal.
- **The Fix task starts a fix run itself.** Rejected: fixes would chain
  without a human, and the App token would be needed to start one.

## Consequences

- The failure issue enters triage like any other (`needs-triage`), but the
  issue-triage workflow does not run on it: an issue opened by
  `GITHUB_TOKEN` starts no workflow.
- The concurrency group is one per watched workflow name with
  `cancel-in-progress: false`. GitHub keeps one pending run per group, so a
  third failure of the same workflow arriving while one runs and one waits
  replaces the waiting one; that run is lost, not misfiled. A manual dispatch
  for its run id files it.
- A job or step rename gives a new signature and a new issue.
- An implementer run started before the `run-name` handover lands has the
  issue title as its display title and is filed by signature only.
