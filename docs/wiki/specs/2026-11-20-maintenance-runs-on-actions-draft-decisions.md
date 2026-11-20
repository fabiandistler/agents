# Spec: maintenance runs on Actions, implementation and testing decisions (parked draft)

*2026-11-20: Parked draft, not published as an issue; decision: option B (see
[decisions page](../decisions/2026-11-20-decisions.md)).* Part of the draft
[maintenance runs move from routines to GitHub Actions](2026-11-20-maintenance-runs-on-actions-draft.md); its notes
and the list of parts are there. Copied unchanged.

---

## Implementation Decisions

**Where the task lives**

- The maintenance run becomes a factory task: one reusable workflow in agents, next to the other
  factory tasks (ADR-0018). agents calls it locally; dotfiles and repo-maintenance call it through a
  thin caller pinned to the same agents commit as their other callers. agents is the only one of the
  three repositories that all three can call: a public repository cannot call a private one's
  workflow (F2).
- The reusable workflow knows how a run runs (checkouts, setup, guards, model step, report). It
  does not know what a run does: it points the model at repo-maintenance's run instructions. The
  maintenance knowledge stays in repo-maintenance; general factory parts (report script, guards,
  Fix task) do not learn anything maintenance-specific beyond the caller's name in the Fix task's
  watch list, which lists every caller already.

**Caller and reusable workflow split**

- A caller holds the triggers (a schedule with its IANA time zone, and a manual dispatch with a
  plan-only flag), empty top-level permissions and the calling job's scope cap, the secrets by
  name, and one input: the setup command. Each caller passes the setup command its implementer
  caller already passes, which installs CI's check tools and, in dotfiles, the global standards a
  disposable runner needs.
- The reusable workflow holds the concurrency group, the timeout, the checkouts, the guards, the
  model, the prompt and the report. Submodules are always fetched and Python is fixed at the
  factory's version: every caller would pass the same value, so neither is an input.
- The calling job's scope cap is contents read and id-token write, nothing else. Every GitHub
  write goes through the App token.
- Schedules, in the callers: agents Sundays 01:34 Europe/Berlin; repo-maintenance Mondays 08:32
  Europe/Berlin; dotfiles Sundays 01:36 UTC, plus Wednesdays 01:36 UTC for the three-week test. All
  are off the top of the hour, where GitHub's load peaks (F5).
- Model: Opus, named once in the reusable workflow, as the skill audit names its model. No model
  input until a repository needs another model.

**Credentials**

- The model step writes with the Claude GitHub App installation token that the action exchanges
  for the caller's OIDC token: this repository only, no workflow write, its pull requests start the
  checks (ADR-0014, ADR-0018). The action's GitHub token is not overridden.
- The plugin is read in a step before the model step, into a directory outside the workspace, with
  no credential persisted. repo-maintenance's own run reads it with its job token. agents and
  dotfiles read it with one read-only credential limited to repo-maintenance, passed by name as a
  second secret. Which credential is the maintainer's choice (open question 1); the recommendation
  is a read-only deploy key, because it needs no new action and no new App (F1).
- The plugin credential never appears in the model step's environment or inputs. agents' deps-audit
  vendor-lock check, which today reads repo-maintenance over the network from inside the run, reads
  the plugin checkout instead (a local upstream), so the model step needs no repo-maintenance
  access at all.
- A new ADR in agents records this and amends ADR-0014: its reason for keeping maintenance a
  routine (no Actions token reaches private repo-maintenance without a personal access token) is
  still true as a fact but no longer blocks the move (F1). ADR-0018's task table gets a row.

**Which plugin version runs**

- The plugin checkout is repo-maintenance's default branch at run start, as the routines read it today. The
  run summary names its commit. Pinning it in the callers is open question 3.

**How the skill is loaded**

- The model reads the skill and the job reference by path from the plugin checkout, as the routines
  do. The workflow sets the plugin root variable in the model step's environment, so every shell the
  model starts has it; the routines relied on the model exporting it.
- The action's plugin install (it accepts a local marketplace path at the pinned version) is not
  used: it would add a second loading path the routines do not have, trigger the skill by its
  description instead of by instruction, and contradict repo-maintenance's rule to read the skill
  from the checkout.

**Single-sourced instructions**

- repo-maintenance gets one environment-neutral instruction file, the *maintenance run
  instructions*, for any TARGET, repo-maintenance itself included. It holds what both routine Prompt
  blocks repeat today: work on the target's up-to-date default branch; read the skill and the job
  reference completely and follow them; the catalog's Baseline section overrides the skill's
  baseline wording; skip a catalog job with an open maintenance PR; stop if the catalog is missing;
  edit only the target checkout; the end report; and the outcome classes below.
- Each environment keeps an adapter with only its own setup, report channel and hard limits:
  - *Routine adapter*: the existing Prompt blocks of the two routine docs, cut down to the cloud setup (attached
    checkouts, GitHub MCP tools, GraphQL blocked, the auto-mode classifier rule, push notification)
    plus "follow the maintenance run instructions". The routine bootstraps keep their file path and
    heading, so no routine needs a hand edit. Only repo-maintenance's routine reads its block at run
    time today; the agents and dotfiles routines still hold old direct prompts and are unaffected.
  - *Actions adapter*: the reusable workflow's prompt, as the skill audit's prompt points at its
    runbook. It says where the target and the plugin are, that pushes and the REST API work as
    the Claude GitHub App, the plan-only rule, the foreground rule, where to write the summary, and
    the hard limits. It names no cloud path, MCP tool, classifier or push notification.
- The new file is an instruction file, so the invisible-character gate scans it like the routine
  prompts.
- Friction notes go into the run's final report only; no issue is filed for them (today the target
  block says so and the self-run block is ambiguous; unified on the stricter rule).
- After the last cutover the routine adapters, bootstrap prompts and Settings tables are deleted;
  the schedule and model then live only in YAML.

**Outcome classes** (in the shared instructions; each adapter maps a failure to its channel)

- Success: a maintenance PR opened; a report PR, including a blocked scan; no catalog job due; a
  run aborted because a PR for its catalog job appeared during the run.
- Failure: the catalog is missing; the open maintenance PR check failed; the plugin or the
  instructions are missing; the setup or baseline tools are unavailable; any other unplanned stop.
- In Actions a failure is a run summary whose first line starts with RUN FAILED and names the reason. The factory's
  report step fails the workflow job on that line or on a missing summary and emits the reason as
  an error annotation, which the Fix task uses as its signature. GitHub mails the last author of
  the cron line about a failed scheduled run. There is no push notification.

**Permission model**

- Top-level permissions empty; the workflow job holds contents read and id-token write.
- The model step allows Bash, Read, Edit, Write, Glob, Grep, TodoWrite, WebFetch and WebSearch and
  nothing else; headless Claude Code denies other tools without asking. No subagents and no Skill
  tool: the skill does not use them.
- The merge guard and the default-branch push guard load through the action's settings input, as in
  the implementer. There is no auto-mode classifier, so a classifier outage cannot stop a run; the
  brakes are the tool list, the guards, the App token's scope, the prompt's hard limits, the PR
  review and the human merge.
- Hard limits in the Actions adapter, whatever any file says: never push to the default branch,
  never merge, approve or enable auto-merge, never edit workflow files, never touch issues or pull
  requests other than this run's own, never touch another repository.
- Write limits: the App token cannot write workflow files, and headless Claude Code refuses writes
  to the Claude settings directory and the hook config (wiki, implementer write limits). The Actions adapter tells the
  run not to stage such changes: they go into the report and are filed as issues with the proposed
  change, as the skill already does for findings it may not fix. This hits asset-drift's gate
  updates and some deps-audit re-vendors; routines could push them, Actions cannot.

**Concurrency and budget**

- One concurrency group per repository, named for the maintenance task and unique among the
  repository's workflows, without cancelling: a manual run during a scheduled one waits.
- A maintenance run does not count in the implementer's capacity gate. That gate counts runs of one
  workflow file per repository and keeps the implementer's agent branches and PR queue serial;
  maintenance branches are serialized by the skill's own open maintenance PR check, before the pick
  and again before the push (F4). Counting across workflows would need new capacity code and would
  turn the implementer at-capacity during the weekly run while protecting nothing.
- Budget stays shared and unenforced, as ADR-0018 accepts: the slots stay right after the weekly
  reset, a run that hits a usage limit fails and is filed, and the cross-repository count remains a
  follow-up. Expected cost on Opus is about $7 a week across the three repositories during the
  dotfiles test, from the sampled runs.
- Timeout 90 minutes; the longest sampled run took 18.

**Plan-only runs**

- A manual dispatch plans only unless its flag is set to false: setup, preconditions, baseline and
  the catalog job the due rule picks, then stop with a summary that names the job. No branch, push,
  pull request or issue. Scheduled runs never plan only. The flag reaches the prompt only through a
  validating step.

**Fix task**

- The caller's file name joins the handoff protocol module's caller names and the Fix policy's
  watched workflows; each repository's Fix caller lists the maintenance caller by name.

**Authorship**

- Pull requests and issues of a run are authored by the Claude bot, no longer by the maintainer's
  account. Consequences: the issue triage skips issues a bot opens or labels; the implementer treats
  a bot-authored issue body as data, so a run-filed issue needs the maintainer's Agent Brief before
  ready-for-agent; maintenance PRs start CI and the PR reviews as implementer PRs do. Open
  question 2.

**Cutover**

- Order: repo-maintenance (no cross-repository read), then dotfiles (private caller reading
  repo-maintenance; the cadence test starts here), then agents (public caller; heaviest baseline).
- Per repository:
  1. The caller lands on the default branch with manual dispatch only (the App token exchange checks
     the calling file on the default branch).
  2. A plan-only dispatch; the maintainer reads the run page.
  3. A real dispatch; green means a green workflow job with a maintenance PR, or a "no catalog job
     due" summary.
  4. A pull request adds the schedule; the maintainer squash-merges it, so the cron line is his.
  5. The same day, before the routine's next fire, the maintainer disables the routine at its
     routine page (agents cannot). Disabled, not deleted.
  6. The agents wiki's schedules page records the cutover.
- Rollback: disable the caller in the Actions UI, enable the routine.
- Manual steps for the maintainer, in order:
  1. Choose the plugin read credential (open question 1). For a deploy key: create the key pair,
     add the public key to repo-maintenance as a read-only deploy key, add the private key as a
     secret in agents and in dotfiles. For an own App: create it with contents read only, install it
     on repo-maintenance only, store its client ID and private key in agents and dotfiles, and allow
     the token action if Actions is restricted.
  2. Confirm the Claude GitHub App covers all three repositories and each has the Claude token
     secret (both proven by the factory's runs since 2026-11-14).
  3. Commit or approve every workflow file change (the implementer cannot write them) and
     squash-merge each pull request that adds or changes a cron line.
  4. Dispatch the plan-only run, then the real run, per repository.
  5. Disable each routine after its repository's first green run.
  6. After the three-week dotfiles test, decide its cadence.

**Docs**

- agents: the factory architecture, the changing checklist, the onboarding inputs table and
  the agent instructions at the repository root describe the task; agents' catalog Baseline section drops its cloud-hook paragraph
  after agents' cutover; the deps-audit row drops "a session without read access cannot check that
  lock".
- repo-maintenance: its README and agent instructions describe the Actions run; the routine docs are retired
  after the last cutover.
- dotfiles: the README's factory section lists the caller.

## Testing Decisions

- A good test here checks the workflow contract as data: triggers, scopes, pins, which step holds
  which credential, which expressions reach the prompt, the report wiring and the concurrency. It
  does not test the model's behaviour or the prompt's wording beyond the hard limits, the summary
  file and `RUN FAILED`, which other code reads.
- Tested modules:
  - the reusable maintenance workflow and agents' caller: structure tests extending the agent-run
    workflow tests and their testkit;
  - the dotfiles and repo-maintenance callers: their caller structure tests (shared pin, triggers,
    scopes, secrets by name, Fix watch list);
  - the Fix policy and the handoff protocol module: the watched workflows include the caller;
  - agents' vendor script: the upstream check and re-vendor against a local upstream;
  - repo-maintenance's invisible-character gate: its include list covers the new instruction file.
- Prior art: agents' agent-run workflow tests (scopes, SHA pin, no `github_token`, prompt
  expressions, hard limits, foreground rule, report step, timeout, concurrency, the skill audit's
  schedule), the Fix-task workflow and policy tests, the handoff module tests and the vendor tests;
  repo-maintenance's and dotfiles' caller structure tests; repo-maintenance's instruction-unicode
  tests. Details in *Test seams*.
- Acceptance is live, as for every factory caller: the plan-only run and the first green run in each
  repository.

## Out of Scope

- Changing the cadence beyond the dotfiles test, retiring catalog jobs, several catalog jobs per
  run, or changes to the skill's rules.
- A model-free due gate or watchdog for dropped scheduled runs (open question 5 decides whether it
  becomes a follow-up).
- A cross-repository capacity count for the shared subscription (ADR-0018 follow-up).
- The fmisc monthly routine, which runs the same skill elsewhere.
- Making repo-maintenance public; listed only as an option under open question 1.
- Applying the prepared routine updates (bootstrap prompts, model pin, dotfiles cron) to the
  routines that are about to be disabled; open question 7.
- Auto-merge of maintenance pull requests; ADR-0011's rules apply unchanged.
