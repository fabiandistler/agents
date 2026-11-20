# Spec: maintenance runs move from routines to GitHub Actions

*2026-11-20: Parked draft, not published as an issue; decision: option B (see
[decisions page](../decisions/2026-11-20-decisions.md)).*

Added to the wiki by the second chief-of-staff ingest of 2026-11-20. The
session wrote this draft that day and never filed it; the maintainer then
chose option B, so the maintenance runs stay claude.ai routines and this move
(option A) is parked. The draft's text below is copied unchanged: its claims
are as of 2026-11-20 and are not kept up to date. Read it with these notes
(2026-11-20):

- "The maintainer decided the move on 2026-11-20" in its first paragraph is
  *superseded* by the option B decision of the same day.
- F1's verdict that ADR-0014's reason "is obsolete as a blocker" means only
  that a new read credential could lift it. The fact it rests on holds: the
  Claude App token reaches only the repository it runs in. See the correction
  on the [decisions page](../decisions/2026-11-20-decisions.md).
- It names session scratchpad files (`maintenance-cadence.md`,
  `diag-maintenance-run.md`, `trigger-updates.md`) that are not kept. Their
  durable parts are in
  [2026-11-20 maintenance cadence](../snapshots/2026-11-20-maintenance-cadence.md),
  [runs without a trace](../problems/runs-without-trace.md) and
  [schedules](../schedules.md).
- The repository's 5000-token file limit split the draft by section into four
  pages. Sections refer to each other by name ("Findings F1–F5", "decision
  above"):
  - this page: opening, Problem Statement, Solution, User Stories;
  - [decisions](2026-11-20-maintenance-runs-on-actions-draft-decisions.md): Implementation Decisions, Testing
    Decisions, Out of Scope;
  - [findings](2026-11-20-maintenance-runs-on-actions-draft-findings.md): Further Notes (Findings F1–F5, Risks to
    watch), Test seams;
  - [tickets](2026-11-20-maintenance-runs-on-actions-draft-tickets.md): Open questions for the maintainer, Ticket
    sketch.

---

Draft, 2026-11-20. Not published, no issue filed. Scope: `fabiandistler/agents`,
`fabiandistler/dotfiles`, `fabiandistler/repo-maintenance`. The maintainer decided the move on
2026-11-20. Evidence for that decision (cadence, reliability, cost, drift) is in
`maintenance-cadence.md`, `diag-maintenance-run.md` and `trigger-updates.md` in this scratchpad
and is not repeated here. The facts behind each decision below are in *Further Notes*,
"Findings F1–F5", tagged **[verified]** (read in a primary source, URL given), **[read]** (read in
these repositories at `origin/main`: agents `68dcf08`, repo-maintenance `9a5c5e3`, dotfiles
`50f4dd6`) or **[inferred]**.

Vocabulary: *routine* is a claude.ai scheduled task. *Maintenance task*, *run*, *trigger* and
*runner* are the software-factory terms. A *catalog job* is a row of `MAINTENANCE.md`
(deps-audit, doc-drift, ...); a *workflow job* is the GitHub Actions unit. *Gate* and
*instruction file* are repo-maintenance's glossary terms. *Merge guard* and *push guard* are the
agents hooks; repo-maintenance's glossary uses *guard* for a structure test, so this spec says
*structure test* for those.

## Problem Statement

The weekly maintenance runs of the three repositories are routines in the maintainer's claude.ai
account. The maintainer cannot see, change or trust them the way the rest of the factory works:

- Their schedule, model, sources and connectors live in a web UI. Agents cannot edit them
  (`update_trigger` refuses: the routines were created through the HTTP API), so every cron or
  model change waits for the maintainer to click through three routine pages. The live settings
  already drift from the versioned docs: two routines still hold old direct prompts, and two have no
  model pinned, so their cost swung about 3x when the account default changed.
- A run that fails leaves no trace in any repository. The 2026-11-16 repo-maintenance run stopped
  when the auto-mode classifier gave no verdict on seven Bash calls in a row; its status read
  `SUCCEEDED`, and only a push notification said otherwise. Nothing filed it, and the catalog job it
  should have run still waits.
- The rest of the factory (implementer, review, triage, Rework, Fix, Retro, skill audit) already
  runs in GitHub Actions, with versioned prompts, run pages, structure tests and a Fix task that
  files failures. The maintenance runs are the last agent runs outside it, so the maintainer reads
  two orchestrators and cannot apply the factory's brakes and failure filing to them.
- The maintainer wants to test more runs per week (dotfiles twice a week for three weeks) and pin
  Opus for all three repositories right after the move. Doing that in routines means more hand edits
  in the web UI.

## Solution

Each repository runs its maintenance run as a GitHub Actions workflow on the same slot as its
routine. One reusable factory workflow in agents holds how a run runs: the checkouts, the setup, the
guards, the model step with the Claude GitHub App token, the report. Each repository holds a thin
caller with its schedule and setup. What a run does stays in repo-maintenance: the
`maintenance-run` skill and one environment-neutral instruction file that both the routines (until
they are disabled) and the workflow follow, so no prompt text is copied.

A failed run turns its workflow job red, GitHub notifies the maintainer, and the Fix task files it
as one deduplicated `factory-failure` issue. The schedule and the model are lines in versioned YAML
that a pull request changes. The cutover goes one repository at a time: a plan-only manual run, then
the first real run, then the maintainer disables that routine.

## User Stories

1. As the maintainer, I want each repository's maintenance schedule in versioned YAML, so that I
   change the cadence by a reviewed pull request instead of a web page only I can edit.
2. As the maintainer, I want the model named in versioned YAML, so that a run's cost no longer
   follows the account default.
3. As the maintainer, I want Opus for all three repositories, so that the runs are comparable and
   their cost is known in advance.
4. As the maintainer, I want each run on the slot its routine has today, so that the move changes
   the orchestrator, not the cadence or the runs' place after the weekly usage reset.
5. As the maintainer, I want dotfiles to run on Sundays and Wednesdays for three weeks after its
   cutover, so that I can measure whether a second weekly run pays off.
6. As the maintainer, I want the end of that test to be a ticket with a date, so that the extra slot
   does not keep running unnoticed.
7. As the maintainer, I want a failed run to turn its workflow job red, so that a failure is visible
   in the Actions list without a push notification.
8. As the maintainer, I want GitHub to notify me about a failed scheduled run, so that I learn of it
   the same day.
9. As the maintainer, I want the Fix task to file a failed run as one deduplicated `factory-failure`
   issue, so that a recurring failure shows up once, with every run linked.
10. As the maintainer, I want each run's summary (the skill's five-line block, the target's commit
    and the plugin's commit) on the run page, so that I see what a run did without a session
    transcript.
11. As the maintainer, I want "no job due" to be a green run, so that a quiet week does not file a
    failure.
12. As the maintainer, I want a manual run to plan only by default, so that I can test a
    repository's setup without opening a pull request.
13. As the maintainer, I want to start a real run by hand, so that I can recover a dropped or failed
    slot without waiting a week.
14. As the maintainer, I want the move to go one repository at a time, so that a problem in one does
    not stop the other two.
15. As the maintainer, I want each routine disabled only after that repository's first green
    Actions run, so that no week goes without a run during the move.
16. As the maintainer, I want the routine disabled, not deleted, so that I can switch back if the
    workflow breaks.
17. As the maintainer, I want a rollback per repository (disable the caller, enable the routine), so
    that a broken workflow costs at most one slot.
18. As the maintainer, I want one ordered list of the manual steps per repository (secret, App,
    routine), so that I can do them in one sitting.
19. As the maintainer, I want the cron lines authored by me through a squash merge, so that the
    schedules fire and their failure notifications reach me.
20. As the maintainer, I want a maintenance run to need no auto-mode classifier, so that a
    classifier outage like 2026-11-16 cannot stop it.
21. As the maintainer, I want the run to read the skill and its instructions from repo-maintenance
    `main` at run start, so that a merged change applies from the next run in all three
    repositories, as it does today.
22. As the maintainer, I want one copy of the run instructions that routines and workflows both
    follow, so that the two cannot drift during the move.
23. As the maintainer, I want to change what a maintenance run does with one pull request in
    repo-maintenance, so that agents and dotfiles need no pin bump for it.
24. As the maintainer, I want to change how a maintenance run runs once in agents, so that all three
    repositories get it with the next shared pin bump.
25. As the maintainer, I want the credential that reads private repo-maintenance to be read-only and
    limited to that repository, so that a leak exposes nothing writable.
26. As the maintainer, I want that credential kept out of the model step, so that a prompt injection
    in a target repository cannot exfiltrate it.
27. As the maintainer, I want agents' deps-audit to keep checking its repo-maintenance vendor lock
    without that credential, so that the check does not degrade to "not checked".
28. As the maintainer, I want repo-maintenance's own run to need no extra credential, so that its
    cutover has the fewest moving parts.
29. As the maintainer, I want the maintenance runs to keep their own place in the shared Claude
    subscription, so that they neither block the implementer nor get blocked by it.
30. As the maintainer, I want to know that run-filed issues and pull requests will carry the Claude
    bot as author, and what that changes for triage and the implementer, so that I am not surprised
    when a run-filed issue needs my Agent Brief.
31. As the maintainer, I want the routine docs retired after the last cutover, so that no agent
    follows a stale cloud prompt.
32. As the maintainer, I want an ADR that says why the reason for keeping maintenance a routine no
    longer holds, so that nobody re-argues it later.
33. As a maintenance run, I want the target checked out on its default branch with its setup done,
    so that the baseline runs with CI's tools.
34. As a maintenance run, I want the plugin root set in every shell I start, so that the skill's
    commands find the scanner and its helpers.
35. As a maintenance run, I want `git push` and the GitHub REST API authenticated as the Claude
    GitHub App, so that the open maintenance PR check, the push and the pull request work.
36. As a maintenance run, I want the instructions to say which outcomes are failures, so that I
    write `RUN FAILED` for a lost slot and not for a quiet week.
37. As a maintenance run, I want to be told that changes to workflow files, `.claude/` and the hook
    config go into the report, so that my push is not refused and my turn not blocked.
38. As a maintenance run, I want to be the only maintenance run in my repository at a time, so that
    two runs never pick the same catalog job.
39. As a maintenance run, I want hard limits in the workflow's own prompt, so that a bad merge in
    repo-maintenance cannot widen what I may do.
40. As a maintenance run, I want to run every command in the foreground, so that the headless
    runner does not kill work I left in the background.
41. As the Fix task, I want the maintenance caller in each repository's watch list and in my policy,
    so that its failed runs are filed.
42. As the Fix task, I want the run's `RUN FAILED` reason as an error annotation, so that my
    signature groups recurring failures.
43. As the PR review and CI, I want maintenance pull requests opened with the App token, so that
    the pull request workflows start on them.
44. As the implementer, I want an issue filed by a maintenance run to count as untrusted text until
    the maintainer posts an Agent Brief, so that model-written text alone never steers a write run.
45. As an agent changing the maintenance task, I want structure tests that pin its scopes, pins,
    prompt inputs, credential placement and report wiring, so that a regression fails CI instead of
    a weekly run.
46. As an agent changing the maintenance task, I want it in the factory architecture, the changing
    checklist and the onboarding inputs table, so that I can change it or add a repository safely.
47. As a target repository's caller structure test, I want the maintenance caller to pin the same
    agents commit as the other callers, so that one bump moves them all.
48. As the maintainer, I want late or dropped scheduled runs to be visible within the test period,
    so that I can decide whether the Actions schedule is reliable enough.
