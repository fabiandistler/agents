# Spec: maintenance runs on Actions, findings and test seams (parked draft)

*2026-11-20: Parked draft, not published as an issue; decision: option B (see
[decisions page](../decisions/2026-11-20-decisions.md)).* Part of the draft
[maintenance runs move from routines to GitHub Actions](2026-11-20-maintenance-runs-on-actions-draft.md); its notes
and the list of parts are there. Copied unchanged.

---

## Further Notes

### Findings F1–F5

**F1. Can the Claude GitHub App token, as the factory mints it, check out private
repo-maintenance from an agents or dotfiles workflow? No.**

- [verified] The action exchanges only the job's OIDC token and an optional permissions object;
  the request names no repository
  ([claude-code-action@4fa93a8, `src/github/token.ts:103-123`](https://github.com/anthropics/claude-code-action/blob/4fa93a88de49bbef68b10eb15aabedf28ca0e1ed/src/github/token.ts)).
  The factory pins this commit (v1.0.271; agents `factory-implementer.yml:194` [read]).
- [verified] Its docs at that commit: "Claude's GitHub app token is sandboxed to the current
  repository only" (`docs/faq.md:180-182`); "No Cross-Repository Access: Each action invocation is
  limited to the repository where it was triggered" (`docs/security.md:19-21`).
- [read] The token exists only inside the model step (`factory-implementer.yml:96-101`), so no
  checkout step before it could use it anyway.
- [read] The App is installed on repo-maintenance: the implementer ran there on 2026-11-14 (run
  43634321706; agents `docs/factory/architecture.md`, "Proven in the targets"). That installation
  serves workflows of repo-maintenance only.
- [verified] `actions/create-github-app-token` requires the App's client ID (or app ID) and private
  key; `owner` with `repositories` scopes the token to those repositories of the App's installation
  ([README](https://github.com/actions/create-github-app-token#inputs)).
- [inferred] The maintainer holds no private key of Anthropic's Claude App, so `owner` and
  `repositories` cannot mint a Claude App token for repo-maintenance. They work only for a
  maintainer-owned App installed on repo-maintenance. The action's own docs route a custom App
  through `github_token`
  ([`docs/setup.md:59-170`](https://github.com/anthropics/claude-code-action/blob/4fa93a88de49bbef68b10eb15aabedf28ca0e1ed/docs/setup.md)).
- [verified] Sharing a private repository covers "the actions and reusable workflows", and "Access
  is allowed only from private repositories"
  ([Managing GitHub Actions settings for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#allowing-access-to-components-in-a-private-repository)).
  So this setting cannot help agents, which is public. It could let dotfiles download a private
  action from repo-maintenance, but a second mechanism for one repository is rejected.
- [verified] A deploy key "grants access to a single repository", is read-only by default and has
  no expiry date; GitHub recommends an App for finer control
  ([Managing deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)).
- [read] agents' deps-audit reads repo-maintenance from inside the run: the vendor-lock check runs
  `git ls-remote` against the private upstream and reports "not checked" without access (agents
  `MAINTENANCE.md:165`, `scripts/vendor_repo_maintenance.py:53,193`).
- Verdict on ADR-0014 (`docs/adr/0014-agent-runs-in-github-actions.md:45-47`): the fact stands, no
  Actions token reaches private repo-maintenance. The reason is obsolete as a blocker: a read-only
  deploy key, a maintainer-owned App, or a public repo-maintenance would each do, none of them a
  personal access token. It never applied to repo-maintenance's own run, whose job token reads its
  own repository [inferred; every job of its `maintenance-gate.yml` checks out with the job token,
  read].

**F2. Where the reusable workflow lives: agents, per ADR-0018.**

- [verified] A private caller can use reusable workflows in private and public repositories; a
  public caller only public ones. A private host also needs its Access policy set
  ([Reusing workflow configurations, access](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#access-to-reusable-workflows)).
- [read] Private dotfiles and repo-maintenance call agents' factory workflows in production, pinned
  to `8afe860` (their `implementer.yml`), since 2026-11-14.
- So a workflow in private repo-maintenance would be unreachable from public agents. In public
  agents all three can call it.

**F3. Single source, and what changes from routine to Actions.**

- [read] Both routine `## Prompt` blocks mix the run's steps with cloud specifics: checkouts under
  the session's home directory, `add_repo`, GitHub MCP tools because GraphQL is blocked, the
  auto-mode classifier rule and push notifications (repo-maintenance
  `docs/agents/weekly-maintenance-routine.md:56-74`, `target-repo-maintenance-routine.md:61-78`).
- [read] The skill itself is environment-neutral: GitHub MCP tools if the session has them,
  otherwise `gh api` against REST (`SKILL.md:67-78`, `:258-266`).
- [read] Only repo-maintenance's routine reads its block at run time; the agents and dotfiles
  routines hold old direct prompts (`trigger-updates.md`, section 1).
- [verified] The pinned action accepts `plugins` and `plugin_marketplaces`, the latter also as a
  local path (`action.yml:160-166`, `base-action/src/install-plugins.ts:15-23` at `4fa93a8`).
  Rejected above.
- [read] Actions permission model: `--allowedTools` plus the guards through `settings`
  (`factory-implementer.yml:211-219`). [inferred] A headless run gets no auto-mode classifier unless
  auto mode is requested; the 2026-11-16 failure mode goes away.
- [verified] "Notifications for scheduled workflows are sent to the user who last modified the cron
  syntax in the workflow file"
  ([Events that trigger workflows, schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)).
- [read] Failure filing: `RUN FAILED` line, report step, annotation, Fix signature (ADR-0016).

**F4. Concurrency and budget: an own concurrency group; not in the capacity gate.**

- [read] The capacity gate lists runs of one workflow file
  (`scripts/agent_run_capacity.py:132`), with one implementer per repository
  (`scripts/implementer_capacity.py:18`; ADR-0018 "Billing and capacity").
- [read] The skill skips a catalog job with an open maintenance PR and re-checks before the push
  (`SKILL.md:53-55`, `:252-256`).
- [verified] A concurrency group allows one running and, by default, one pending run "in the
  repository"; group names must be unique across a repository's workflows
  ([Control the concurrency of workflows and jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)).
- [read] One subscription serves everything (`docs/wiki/problems/shared-usage-limit.md`).

**F5. Cutover facts.**

- [read] Precedent: each routine is disabled, not deleted, after its workflow's first green manual
  run (ADR-0014:115-116; `docs/wiki/schedules.md`, 2026-11-10).
- [read] Default-branch rule for the App token exchange (ADR-0018:98-104).
- [read] A cron line the `claude` account wrote never fired; a squash merge by the maintainer fixed
  it (#864; `docs/factory/changing-a-task.md`, item 9).
- [verified] Scheduled runs use the default branch, accept an IANA time zone, "can be delayed during
  periods of high loads", may be dropped, and are disabled in a public repository after 60 days
  without activity (same schedule page as above).
- [read] Scheduled runs in agents started hours late (retro at 14:16–14:39 UTC for a 06:23 Berlin
  cron) and the hourly queue fired 10 times in about 79 slots (`docs/wiki/schedules.md`,
  2026-11-20). Routines fired on time (`diag-maintenance-run.md`).
- [read, from the brief] Agents cannot edit the routines: `update_trigger` refuses routines created
  through the HTTP API.

### Risks to watch

- Dropped or late scheduled runs leave no failed run, so the Fix task cannot file them (F5).
- deps-audit's Dependabot check calls the Actions runs, jobs and runners APIs
  (`maintenance-scan.sh:142-166`). [inferred] The App token may lack the scope for the runners list,
  which would make the scan report "blocked" and file "Maintenance scan blocked: gh". The first
  deps-audit in Actions shows it.
- Write limits turn some catalog job fixes into issues (decision above).
- Bot authorship changes triage and the implementer's contract for run-filed issues (decision
  above).

## Test seams

Fewest seams, highest first. All but the last exist today.

1. **Workflow contract of the reusable maintenance workflow and agents' caller** (agents, highest
   seam). Extend `scripts/test_agent_run_workflows.py` and `scripts/agent_run_workflow_testkit.py`,
   which already pin the implementer and the skill audit. Reused assertions: empty top-level
   permissions and the narrow job scopes; SHA-pinned action; no `github_token`; prompt expressions
   limited to validated outputs and the repository name; hard limits, `RUN FAILED` and the summary
   file in the prompt; foreground rule; report step `if: always()`; timeout; concurrency without
   cancel; schedule with `timezone` (as `test_skill_audit_keeps_its_schedule`). New assertions:
   the plugin is fetched outside the workspace with no persisted credential; the plugin credential
   appears only in that fetch step, never in the model step's `env` or `with`; the prompt names the
   instructions file by path and heading; the plan-only flag passes a validating step; the group
   name is unique among agents' workflows.
2. **Caller contracts in the targets.** Add the caller to `CALLERS` in repo-maintenance's
   `tests/test_factory_callers.py` and dotfiles' `tests/test_factory_callers.py`: triggers
   (`schedule`, `workflow_dispatch`), scope cap, shared agents pin (and dotfiles' `AGENTS_COMMIT`),
   secrets by name, and the Fix caller's watch list naming it.
3. **Fix policy and handoff names** (agents). `scripts/test_factory_failure_policy.py`,
   `scripts/test_factory_handoff.py` and `scripts/test_fix_task_workflow.py`: the caller's path is
   watched and comes from the handoff protocol module.
4. **Instruction file gate** (repo-maintenance). Extend the routine-prompt list in
   `tests/test_instruction_unicode.py`, whose `RoutinePromptsInThisRepo` test already runs the
   gate's real command line, to the new instruction file.
5. **Vendor check with a local upstream** (agents). `scripts/test_vendor_repo_maintenance.py`: the
   upstream check and the re-vendor read the plugin checkout when given one.
6. **Live acceptance** (new per repository, no code): the plan-only dispatch and the first green
   run, read on the run page, as the onboarding runbook does for every factory caller.

No seam for the model's behaviour: the run summary on the run page is its observable output.
