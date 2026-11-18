# Software factory architecture

For a developer, usually an agent session, about to change a factory task:
how the tasks, their gates and the reusable workflows fit together, and which
brake each part holds. Day-to-day use is in the [user guide](README.md), the
checklist for a change in [changing a task](changing-a-task.md); the
vocabulary (task, run, trigger, brake) is the
[software-factory skill's](../../.claude/skills/software-factory/SKILL.md).
Line numbers are at `fabiandistler/agents@33f9445`; scripts are under
`scripts/` and workflows under `.github/workflows/`.

## Context and goals

Agents act under the maintainer's GitHub account, and agents that merged their
own pull requests produced red-CI merges and reverts (#557, ADR-0011). Yet a
clear issue should not wait for an interactive session. The factory runs
agents unattended in GitHub Actions and bounds every model by model-free code:
a model writes only where a gate, a guard or a human merge stands after it.

Goals: one issue becomes one reviewed pull request; one copy of each task
serves several repositories (ADR-0018). Constraints: one Claude subscription,
shared with interactive use; a personal account, so no organization rulesets
or required workflows; private targets on GitHub Free have no rulesets. Out of
scope: merging (the human), and starting a fix without a person.

## System context

```mermaid
---
title: System Context diagram — software factory
---
flowchart TB
    maintainer["Maintainer<br/>[Person]<br/>Writes issues, adds ready-for-agent, merges"]
    subgraph repos ["Repositories the factory works on"]
        agents["fabiandistler/agents<br/>[Software System, public]<br/>Hosts the factory and calls it with ./"]
        dotfiles["fabiandistler/dotfiles<br/>[Software System, private]<br/>Thin callers"]
        rm["fabiandistler/repo-maintenance<br/>[Software System, private]<br/>Thin callers"]
    end
    factory["Software factory<br/>[Software System]<br/>factory-*.yml, agents-only workflows, scripts/"]
    actions["GitHub Actions<br/>[External]<br/>Runners, OIDC tokens, GITHUB_TOKEN"]
    app["Claude GitHub App<br/>[External]<br/>Installation token per repository"]
    claude["Claude subscription<br/>[External]<br/>Model calls"]
    maintainer -- "Issues, labels, merges [web, gh api]" --> repos
    repos -- "Issue, PR and clock events start runs [workflow_call]" --> factory
    factory -- "Runs on; reads its OIDC token from" --> actions
    factory -- "Trades the OIDC token for a write token [HTTPS]" --> app
    factory -- "Prompts with CLAUDE_CODE_OAUTH_TOKEN [Claude Code CLI]" --> claude
    factory -- "Comments, labels, pushes, PRs, statuses [REST]" --> repos
    classDef person fill:#08427b,color:#fff
    classDef system fill:#1168bd,color:#fff
    classDef external fill:#999999,color:#fff
    class maintainer person
    class factory system
    class agents,dotfiles,rm,actions,app,claude external
```

Key: dark blue a person, blue the system in scope, grey external; arrows
point from the initiator.

Text equivalent: the maintainer works in three repositories, whose issue,
pull request and schedule events start the factory's runs on Actions
runners. A run that pushes has `claude-code-action` trade the job's OIDC
token for a Claude GitHub App installation token for the calling
repository. Every model call uses
the maintainer's Claude subscription through `CLAUDE_CODE_OAUTH_TOKEN`. Runs
write back with that App token or with the job's `GITHUB_TOKEN`.

## Containers

```mermaid
---
title: Container diagram — software factory
---
flowchart LR
    callers["Caller workflows<br/>[YAML in each repository]<br/>triage-label, issue-triage,<br/>pr-review, implementer"]
    subgraph factory ["Software factory, in fabiandistler/agents"]
        tl["factory-triage-label.yml<br/>[reusable]<br/>model-free"]
        it["factory-issue-triage.yml<br/>[reusable]<br/>assess, triage, publish"]
        prr["factory-pr-review.yml<br/>[reusable]<br/>hold, assess, review, publish"]
        im["factory-implementer.yml<br/>[reusable]<br/>claim, build, open PR"]
        rw["rework.yml<br/>[agents only]<br/>gate, model round"]
        fx["fix-task.yml<br/>[agents only]<br/>model-free"]
        rt["retro.yml<br/>[agents only]<br/>gate, model"]
        sa["skill-audit.yml<br/>[agents only]<br/>model"]
        scripts[("scripts/<br/>[Python, stdlib]<br/>gates, policies, guards")]
    end
    callers -- "uses: …@SHA" --> tl & it & prr & im
    tl & it & prr & im -- "anonymous fetch at job.workflow_sha" --> scripts
    prr -- "completed run [workflow_run]" --> rw
    rw & fx & rt & sa -- "run from the checkout" --> scripts
    fx -. "watches failed runs of" .-> callers
    classDef system fill:#1168bd,color:#fff
    classDef external fill:#999999,color:#fff
    class tl,it,prr,im,rw,fx,rt,sa,scripts system
    class callers external
```

Key: blue boxes are the factory's containers, grey the callers; a dashed
arrow is a watch, not a call.

Text equivalent: the **callers** (`triage-label.yml`, `issue-triage.yml`,
`pr-review.yml`, `implementer.yml`) hold the triggers, `permissions: {}`, the
scope cap and any secret by name; agents calls with `./`, a target pins a SHA.
They call four reusable workflows: **`factory-triage-label.yml`** (adds
`needs-triage`, no model), **`factory-issue-triage.yml`** (`assess` reads
issues, `triage` holds the model token and no GitHub token, `publish` writes
issues), **`factory-pr-review.yml`** (`hold`, `assess`, `review` with the
model and no write scope, `publish` with write scopes and no model token) and
**`factory-implementer.yml`** (one model step with the App token, then a
model-free `follow-up` job). **`rework.yml`,
`fix-task.yml`, `retro.yml` and `skill-audit.yml`** run in agents only and
read `scripts/` from their own checkout; Fix watches six workflows by name
(`fix-task.yml:14`). **`scripts/`** holds the model-free logic: the claim,
`pr_risk.py`, `pr_publish.py`, the gates and the two guards.
`implementer_queue.py` (#847) dispatches the next waiting issue from
`implementer-queue.yml`, which calls the reusable
`factory-implementer-queue.yml`; after a run it dispatched, the `follow-up`
job's `implementer_follow_up.py` starts the queue and the Fix task (#863),
because such a run starts no `workflow_run`. The diagram omits them.

## Dynamic view: claim to verdict

```mermaid
sequenceDiagram
    title Dynamic view — implementer claim to PR review publish
    actor M as Maintainer
    participant GH as GitHub API
    participant I as implement job
    participant C as implementer_claim.py
    participant R as pr-review jobs
    M->>GH: 1. add ready-for-agent
    GH->>I: 2. issues.labeled, sender not a bot
    I->>I: 3. fetch scripts at job.workflow_sha, render guards
    I->>GH: 4. OIDC token for App token (claude-code-action)
    I->>C: 5. first write: claim once
    C->>GH: 6. pr-exists? no-contract? blocked?
    C->>GH: 7. at-capacity? (working runs, job token)
    C->>GH: 8. create refs/heads/agent/issue-n at main
    C-->>I: 9. outcome JSON: build only if claimed or reclaimed
    I->>GH: 10. checks green: push, open ready-for-review PR
    GH->>R: 11. pull_request_target (hold on a push)
    R->>R: 12. assess: context, path risk (artifacts)
    R->>R: 13. review: claude -p, no tools (artifact)
    R->>GH: 14. publish: fetch, plan, fetch again, re-plan
    R->>GH: 15. labels, comment, reviewer, auto-merge, verdict status last
```

Text equivalent: a person's label starts the implement job
(`factory-implementer.yml:76-82`). It fetches the scripts at the workflow's
own commit, renders both guards, and starts `claude-code-action`, which
trades the OIDC token for the App token. The model's first write is
`implementer_claim.py`, which stops with `pr-exists`,
`no-contract`, `blocked` or `at-capacity`, in that order, before any branch
exists (`implementer_claim.py:339-356`). Otherwise it creates the branch at
`main`. An existing branch (422) without commits of its own is
fast-forwarded to `main` (`reclaimed`); one with commits goes to a person
(`needs-human`, `:357-380`). The model builds, runs the caller's
`check_command` and opens a ready-for-review pull request. In the PR review,
`assess` fetches the context and classifies the risk, `review` asks the
model without tools, and `publish` re-fetches, aborts on a moved head
or a closed pull request, and otherwise writes labels, the sticky comment,
the reviewer, any auto-merge change and, last, `pr-review/verdict`
(`pr_plan.py:280-291`). The status goes last so a merge waits until the
verdict is visible; when an earlier write fails, `publish` withholds it and
turns red.

## The brakes and why

The implementer holds a token that pushes and opens pull requests, and it
reads issue text anyone can write. Without brakes, a prompt injection in an
issue would become a merged change. Each brake stops one path:

| Brake | What it stops | Where |
| --- | --- | --- |
| Trigger filter | A bot, or the run itself, starting a run from a label | `factory-implementer.yml:76-82`; any `workflow_dispatch` passes, and the action admits only people and `allowed_bots: github-actions`, the queue's dispatch (#858) |
| Claim outcomes | Building from an outsider's text, on open blockers, beside another run, or over a branch with work | `implementer_claim.py:329-380`; `MAX_WORKING_RUNS`, `implementer_capacity.py:18` |
| Merge guard | An agent merging or enabling auto-merge | `pr_merge_guard.py`, loaded by `agent_run_settings.json` and `.claude/settings.json` |
| Push guard | An agent pushing to the default branch | `default_branch_push_guard.py`; as of 2026-11-14 only the implementer loads it (`factory-implementer.yml:219`) |
| Prompt hard limits | Labels, branches and files outside the task | the `prompt:` of each model step |
| App token | Writes to `.github/workflows/` | the App's permissions (ADR-0014) |
| Headless Claude Code | Writes to `.claude/` and `.pre-commit-config.yaml` | observed, cause inferred ([wiki](../wiki/problems/implementer-write-limits.md)) |
| Credential split | A model holding a write token in the review or the triage | separate jobs joined by artifacts |
| Risk labels | Auto-merge of anything but low-risk docs | `PATH_RULES`, `pr_risk.py:30`; the model may only raise the risk |
| Verdict status | A merge before the head's review is published | `pr_verdict_status.py:15`; green for any verdict |
| Ruleset | A merge on red checks, a push to `main` | ruleset `default`, agents only |
| Rework cap | Endless fix rounds | `MAX_REWORK_ROUNDS`, `rework_policy.py:25` |
| Human merge | Everything above failing at once | the maintainer |

Why the App token at all: pushes and pull requests made with `GITHUB_TOKEN`
start no workflow, so CI, the required checks and the review would never run
(ADR-0014). As of 2026-11-14 the ruleset requires five checks,
`pr-review/verdict` among them
([runbook setup step 6](../agents/pr-review-runbook.md#setup)), and a pull
request for `main`; that is what keeps `rework.yml`, `retro.yml` and
`skill-audit.yml` off `main`, since they load the merge guard from
`.claude/settings.json` but no push guard.

## Label state machine

```mermaid
---
title: Issue state labels
---
stateDiagram-v2
    state "needs-triage" as triage
    state "needs-info" as info
    state "ready-for-agent" as agent
    state "ready-for-human" as human
    state "no state label" as none
    [*] --> triage: triage-label, Fix task
    triage --> info: triage bot or maintainer
    info --> triage: reporter answers
    triage --> agent: maintainer, with a brief
    triage --> human: maintainer
    triage --> wontfix: maintainer, closes
    agent --> none: no-contract
    agent --> agent: blocked, at-capacity (waits)
    none --> agent: a person adds it again
    agent --> human: needs-human, red stop rule, Rework handoff
    agent --> info: implementer cannot read the contract
    agent --> [*]: closing pull request merged
```

Text equivalent: an issue holds at most one of the five state labels
(`STATE_LABELS`, `issue_triage_policy.py:26`). The triage label task, and the
Fix task for its own issues, start it in `needs-triage`. The triage bot may
move it to `needs-info`, and the reporter's answer moves it back (in a
target, a person re-adds `needs-triage`). From `needs-triage`, only the
maintainer sets `ready-for-agent`, `ready-for-human` or `wontfix`. From
`ready-for-agent`, `no-contract` comments and removes the label, leaving no
state until a person adds it again; `blocked` and `at-capacity` comment and
keep it, so the issue waits in the implementer queue (#847); `pr-exists`
changes nothing; `needs-human`, the implementer's red stop rule, the Rework
handoff and the Rework model's red checks set `ready-for-human`. Pull
requests carry separate families, written only by `hold` and `publish`
([labels](../agents/triage-labels.md#pull-request-labels)).

## Data flow

A runner keeps nothing, so every fact one run hands the next lives on GitHub:

| Carrier | Written by | Read by |
| --- | --- | --- |
| Artifacts `pr-context`, `pr-assessment`, `pr-review` | PR review `assess`, `review` | `publish`; the Rework gate, by run id |
| Artifact `rework-findings` | Rework gate | Rework model job, its only task list |
| Artifacts `issue-context`, `issue-triage` | triage `assess`, `triage` | triage `publish` |
| Artifact `run-summary` (90 days) | implementer | Retro gate |
| PR comment `<!-- pr-review-bot -->` | `publish`, through the handoff protocol module (`factory_handoff.py`) | `publish`, which edits only its own, and Retro gate, both through the module's reader |
| Issue comment `<!-- issue-triage-bot -->` | triage `publish`, through the handoff protocol module (`factory_handoff.py`) | triage `assess` through the module's reader: two automatic triages per issue |
| PR comments `<!-- rework-round:<k> head:<sha> -->`, `<!-- rework-handoff head:<sha> -->` | Rework gate, through the handoff protocol module (`factory_handoff.py`) | Rework gate (one per head; their count is the round), Retro gate, both through the module's reader |
| Issue body `<!-- factory-failure:<hash> -->` | Fix task | Fix task (dedupe) |
| Labels `retro:done`, `auto-merge:bot` | Retro gate; `publish` | Retro gate (counter); `hold`, `publish` (ownership) |
| Status `pr-review/verdict` | `publish` | the ruleset |
| Run name `implementer: issue #<n>` | `implementer.yml:17` | Fix task, Retro gate |
| `RUN FAILED: <reason>` in the run summary | model step | `agent_run_report.py`, whose `::error::` becomes the Fix task's signature |

Only markers in comments by `github-actions[bot]` count, so quoting one
changes nothing. Events from `GITHUB_TOKEN` writes start no workflow: that is
why Rework listens to `workflow_run` instead of the verdict label, and why the
Fix task cannot chain into a fix. Where data is lost: artifacts expire; the
Fix task's per-workflow group keeps one waiting run, so a third failure
replaces the waiting one, which is never filed ([ADR-0016](../adr/0016-fix-task.md)).

## Cross-repo specifics

- **Pins.** A target's four callers pin `fabiandistler/agents/.github/workflows/factory-*.yml`
  to one full commit SHA with the comment `# agents main, <date>`. A change reaches a target when a
  pull request bumping all four merges on its default branch; the App token
  exchange also checks the caller there
  ([onboarding](../agents/factory-onboarding.md#one-sha-for-all-callers)).
- **Anonymous fetch.** Every reusable job but the triage label's fetches
  `job.workflow_repository` at `job.workflow_sha` into `$RUNNER_TEMP/factory`
  without a credential (`factory-implementer.yml:149-162`), even when agents
  calls with `./`. agents must stay public: private, all those fetches fail,
  and on the owner's plan agents would lose its ruleset too.
- **Caller's context.** `github` and `vars` are the caller's, so
  `PR_AUTO_MERGE` and the model variables are set per repository
  (`factory-pr-review.yml:30-32`).
- **Private targets.** No rulesets on GitHub Free: nothing can be required,
  the push guard stops pushes to the default branch, and the maintainer
  merges only on green ([wiki](../wiki/problems/private-repos-no-rulesets.md)).
- **Capacity.** One implementer per repository, one subscription for all
  (ADR-0018, "Billing and capacity").
- **Proven in the targets, 2026-11-14.** The implementer claimed, pushed
  and opened a pull request in both: dotfiles run 43634268109 (dotfiles#67)
  and repo-maintenance run 43634321706 (repo-maintenance#160), both merged.
  The model review ran on repo-maintenance#157 (run 43628269770, attempt
  2); #786 closed on it (comment 6883412967).

## Trade-offs and limits

Each decision, with its rejected options, is an ADR:
App write token in the model step instead of a model/publisher split
([0014](../adr/0014-agent-runs-in-github-actions.md)); the review on the
subscription through the CLI ([0012](../adr/0012-pr-review-on-claude-subscription.md));
a triage bot that sets only `needs-info` ([0013](../adr/0013-automated-issue-triage.md));
auto-merge for gated docs-only pull requests ([0011](../adr/0011-pr-review-merge-exception.md));
Rework on `workflow_run`, two rounds ([0015](../adr/0015-rework-task.md)); a
model-free Fix task that never starts a fix ([0016](../adr/0016-fix-task.md));
Retro on a clock, Proposed as of 2026-11-14 ([0017](../adr/0017-retro-task.md));
reusable workflows over copies ([0018](../adr/0018-reusable-factory-workflows.md)).

Known weaknesses, as of 2026-11-15: a failed run leaves
`ready-for-agent`, and the queue skips it, so nothing retries; the claim
branches from `main`, not the caller's default branch
(`implementer_claim.py:68`); the Fix task watches agents' runs only. Still
open (ADR-0018): whether Dependabot bumps the callers' agents pins
(question 5), and how an event policy targets a caller, which matters only
if a target goes public (question 2).

## How to change a task safely

The checklist is its own page: [changing a task](changing-a-task.md).

## Keeping this page current

Cited lines shift with any edit to their file; the required checks, target
status and ADR statuses are dated because they change by hand. No check
reads this prose (the `mermaid` check parses the diagrams only): re-read it
when a `factory-*.yml`, a caller, `implementer_claim.py`, `pr_plan.py` or a
guard changes. The `check-file-tokens` hook stops a file over 20000 bytes;
split a section off before this page gets there.
