# Implementer Claim and Queue

How the implementer picks up an issue labelled `ready-for-agent`: the claim
each run makes first, and the queue that starts waiting issues. The label
vocabulary is in [triage labels](triage-labels.md).

## Implementer claim

Adding `ready-for-agent` starts `.github/workflows/implementer.yml`
([ADR-0014](../adr/0014-agent-runs-in-github-actions.md)), which calls the
reusable `.github/workflows/factory-implementer.yml`
([ADR-0018](../adr/0018-reusable-factory-workflows.md)). Its first write is
`scripts/implementer_claim.py`, run from the factory checkout under
`$RUNNER_TEMP/factory`, which decides what happens to branch `agent/issue-<n>`.
The script takes the workflow file whose runs it counts from `--workflow-file`
or, as the reusable workflow leaves it, from `GITHUB_WORKFLOW_REF`, which names
the caller's file. It matches the job by `--job-name` also as
`<caller job> / <name>` (here `implement / implement`), and names the branch
with `--branch-prefix`, which the reusable workflow passes from its
`branch_prefix` input; the defaults are `implementer.yml`, `implement` and
`agent/issue-`. `--queue-workflow` is the reusable workflow's `queue_workflow`
input, the caller's queue: empty when it has none. Only a claim that would
leave the issue waiting (`blocked`, `at-capacity`) reads it, just before its
comment: a named queue that is not an active workflow of the repository
(Actions API) then fails the claim before any write, so a renamed or disabled
queue turns the run red instead of leaving the issue waiting for nothing. A
claim that leaves nothing waiting does not read it, because GitHub disables a
scheduled workflow, as the queue is, after 60 days without activity in a
public repository
([GitHub docs](https://docs.github.com/actions/using-workflows/disabling-and-enabling-a-workflow)).
The outcomes:

| Situation | Outcome | What the run does | Who acts next |
| --- | --- | --- | --- |
| The branch does not exist | `claimed` | Builds on the new branch | Nobody |
| The branch exists with no commits of its own and no pull request holds the issue (`needs-info` exit, or a crash before the first push) | `reclaimed` | Fast-forwards the branch to `main`, then builds on it | Nobody |
| An open or merged pull request closes the issue, or an open pull request uses the branch (the stop rule's draft) | `pr-exists` | Ends without changes | The maintainer, on that pull request |
| The branch has commits and no open pull request (a crash after pushing, or a pull request closed unmerged) | `needs-human` | Comments naming the branch, replaces `ready-for-agent` with `ready-for-human`, ends | A person: open a pull request from the branch, or rescue what is needed, delete the branch and add `ready-for-agent` again |
| The issue was opened by an account without write access, is not an audit finding a person with write access released with its body unchanged since ([ADR-0020](../adr/0020-audit-finding-issues.md)), and no owner, member or collaborator has posted a comment containing a `## Agent Brief` heading | `no-contract` | Comments, removes `ready-for-agent`, ends before any branch exists | A person with write access: post the brief, then add `ready-for-agent` again |
| A blocker in the issue body, the latest comment by a person with write access containing a `## Agent Brief` heading, or the native dependencies is not closed as completed, or a "Blocked by" entry names no issue of this repository (a title, another repository's issue or a pull request) | `blocked` | Comments naming the blockers, keeps `ready-for-agent`, ends before any branch exists; without a queue, removes the label | The [queue](#implementer-queue), once every blocker is closed as completed; without one, a person adds `ready-for-agent` again then. A person rewrites an unresolvable entry as `#<n>` or removes it once it is done |
| Another implementer run started working first | `at-capacity` | Comments naming the capacity reason, keeps `ready-for-agent`, ends before any branch exists; without a queue, removes the label | The [queue](#implementer-queue), when no run is working; without one, a person adds `ready-for-agent` again once that run has ended |
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

At most one implementer run works at a time (`MAX_WORKING_RUNS` in
`scripts/implementer_capacity.py`).
Runs are ordered by the start of their `implement` job, then by run id; only
runs earlier in that order count, so of two simultaneous starts exactly one
stops. The check reads the Actions API, so it can lag a few seconds; a run about
to end still counts, and the ticket then waits in the queue.

An issue stopped as `no-contract` carries no state label until a person adds
`ready-for-agent` again; nothing restarts it on its own, because only a
person's brief can. The triage workflows do not act on it either; they ignore
the bot's comment, and their state check accepts an issue without a state.

## Implementer queue

`ready-for-agent` is the queue (#801). An issue stopped as `blocked` or
`at-capacity` keeps the label and waits; its comment says so and that removing
the label takes it out of the queue. That holds only where the implementer
caller names its queue in `queue_workflow`. Without one nothing would start a
waiting issue (fabiandistler/repo-maintenance#205), so the claim removes the
label and its comment says when to add it again. `scripts/implementer_queue.py`, model-free,
dispatches the implementer workflow (`inputs.issue`, on the default branch) for
one waiting issue. It runs from `.github/workflows/implementer-queue.yml`, which
calls the reusable `.github/workflows/factory-implementer-queue.yml`: after an
implementer run a person or a label started completes (unless its job was
skipped), when an issue closes, on an hourly schedule, and by hand (Actions →
implementer-queue → Run workflow, a dry run by default). The schedule is a slow
fallback, not a guarantee: GitHub starts scheduled runs late or skips slots
(observed 2026-11-15: 2 runs in about 12 slots, each 30 minutes or more late,
#864).

The starter dispatches with the job's `GITHUB_TOKEN`, so a dispatched run's
actor is `github-actions[bot]`. The implementer's `claude-code-action` step
admits it through `allowed_bots: github-actions`; without it the run fails
seconds into the model step (#858). A run started this way starts no
`workflow_run` workflow (observed 2026-11-15), so the reusable implementer's
model-free `follow-up` job (`scripts/implementer_follow_up.py`) starts both
follow-ups by `workflow_dispatch` (#863): after such a run it dispatches implementer-queue (`dry_run: false`)
and, unless the implement job succeeded, fix-task with the run's id. The Fix
task waits up to 180 seconds for the run to complete before it reads it. Runs a
person or a label started skip that job and reach both through `workflow_run`.

The Fix task also files a failed implementer-queue run (ADR-0016, amended
2026-11-20). A scheduled run, one started by an issue a person closed, one
after an implementer run a person or a label started, and a person's manual
run reach it through `workflow_run`. A queue run the `follow-up` job
dispatched starts no `workflow_run` either, so the reusable queue's model-free
`report-failure` job dispatches fix-task with the run's id and `dry_run: false`
when the run's `start-next` job failed (#909); the caller names its Fix task in
`fix_task_workflow`. The job skips every run that `workflow_run` reaches, so
no run is filed twice. It checks `github.triggering_actor`, which a person's
re-run of a dispatched run changes and `github.actor` keeps, so such a re-run
is left to `workflow_run`. Whether a re-run starts `workflow_run` has not been
observed (no re-run of a bot-started run as of 2026-11-20); if no fix-task run
follows a failed re-run, file it by hand (Actions → fix-task → Run workflow,
its run id, `dry_run` false).

| Situation | Outcome | What the starter does |
| --- | --- | --- |
| An implementer job is working | `busy` | Dispatches nothing and reads no issue |
| An open issue with `ready-for-agent` passes every check below | `dispatched` | Dispatches the implementer for the lowest such number, once |
| No issue waits, or every one is skipped | `empty` | Dispatches nothing |

**Order rule:** lowest issue number first. A waiting issue is skipped when its
latest implementer run (by the run name `implementer: issue #<n>`) has not
completed or ended other than success or skipped (`run-active`, `run-failed`:
a failed run waits for a person, so a failing issue is not dispatched again
and again; the Fix task files it), when
its branch exists (`branch`: a run claimed it
and ended without a pull request), and by the claim's own checks when a pull
request holds it, it has no contract or a blocker is not done (`pull-request`,
`no-contract`, `blocked`; a blocker closed as not planned still blocks).

The starter dispatches nothing while a run works, so a dispatched run that
stops `at-capacity` and ends starts no other run: no loop of model starts. The
capacity gate stays the only arbiter of who works. A run whose job is still
queued does not count as working, so a dispatch can race a person's new label;
one of the two runs stops `at-capacity`, keeps waiting, and starts after the
other. Adding `ready-for-agent` again to a waiting issue fires no event; to
restart one by hand, dispatch `implementer.yml` with its number, or remove and
add the label.
