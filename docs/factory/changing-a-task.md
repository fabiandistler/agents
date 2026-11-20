# Changing a factory task

For a developer, usually an agent session, about to change a factory
workflow, a gate or a guard. The [architecture](architecture.md) explains how
the tasks fit together and which brake each part holds; read it first. This
page is the checklist. Line numbers are at `fabiandistler/agents@33f9445`.

A change can pass its tests in agents and still break a target repository
weeks later, when that target's pin is bumped to it. A reusable workflow runs
in three repositories, and a rename or a lost scope fails only where nobody
is watching. So check each layer before you push:

1. **Tests.** Structure tests pin each workflow's scopes, triggers, pins
   and prompt inputs (`scripts/test_*_workflow.py`, `test_pr_workflow_*.py`,
   `test_agent_run_workflows.py`); guard tests are `test_pr_merge_guard.py`,
   `test_default_branch_push_guard.py` and `test_agent_run_settings.py`. Run
   `scripts/check_all.sh`, or `--only pytest,zizmor` while iterating.
2. **zizmor** audits `.github/workflows/` offline. Suppress a deliberate
   finding inline with its reason, as `# zizmor: ignore[dangerous-triggers]`
   does.
3. **Pins.** Every `uses:` names a 40-hex SHA with a `# vX.Y.Z` comment
   (`test_workflow_action_pins.py`). The Claude Code CLI is pinned exactly
   (`factory-pr-review.yml:275`); rerun ADR-0013's sandbox check before a bump.
4. **Event text stays data.** Event values reach shells through `env:`, and
   prompts only as validated values and the repository name.
5. **Names are interfaces.** The claim counts runs by the called job's name,
   passed as `--job-name implement` in the prompt and listed by the jobs API
   as `<caller job> / implement`; Rework and Fix match workflow names; the
   event policy names `pr-review.yml`; Fix, Retro and the implementer queue
   read the `run-name`; a renamed job or step files a new Fix issue. The
   handoff protocol module (`factory_handoff.py`) is the one place to change a
   run name, marker, agent branch name, caller workflow file name or issue
   state label; every task imports it from there.
6. **A new task** gets `permissions: {}`, the narrowest job scopes, a
   structure test, and its workflow name in `fix-task.yml` plus its path in
   `WATCHED_WORKFLOWS` (`factory_failure_policy.py:49`). A model step that
   pushes uses `claude-code-action` without `github_token`, writes
   `RUN FAILED: <reason>` into its run summary, is followed by an
   `agent_run_report.py` step, and loads both guards as the implementer does:
   `agent_run_settings.py` renders `agent_run_settings.json` for the action's
   `settings` input (`factory-implementer.yml:179-219`). The older
   agents-only tasks rely on the ruleset instead of the push guard; a new
   task should not.
7. **Roll out.** `pull_request_target` runs `main`'s pipeline, so a pull
   request that edits the review is reviewed by the old one. After the merge,
   bump each target (as of 2026-11-14 `fabiandistler/dotfiles` and
   `fabiandistler/repo-maintenance`) to the SHA of agents `main`, which now
   holds your change: its four callers `triage-label.yml`, `issue-triage.yml`,
   `pr-review.yml` and `implementer.yml` in one pull request, merged there.
   As of 2026-11-14 no Dependabot bump of these pins has been seen (ADR-0018,
   open question 5), so bump by hand. Then run the onboarding check; its
   `pin` line reads `OK` when all four callers pin one SHA on agents `main`:

   ```bash
   gh api repos/fabiandistler/agents/commits/main --jq .sha
   GH_TOKEN=$(gh auth token) python3 scripts/factory_onboarding_check.py --repo OWNER/NAME
   ```

8. **Interactive session needed** for `.github/workflows/`, `.claude/` and
   `.pre-commit-config.yaml`: an implementer run cannot write there. Or write
   a brief that asks the implementer for that YAML in its pull request body,
   for the maintainer to commit, as #847 left `implementer-queue.yml` and
   `factory-implementer-queue.yml`
   ([write limits](../wiki/problems/implementer-write-limits.md)).
9. **Cron lines.** A schedule whose `cron:` line the `claude` account wrote
   never fired; the same schedule ran once a squash merge made the
   maintainer the line's author (#864). So a pull request that adds or changes a `cron:` line says in
   its body that it must be merged with **Squash and merge**; a merge commit
   keeps the agent as the line's author. Changes elsewhere in the file do
   not matter: retro ran although `claude` last changed `retro.yml`.
10. **Docs.** Update the [architecture](architecture.md), this page and the
   source tables in `docs/agents/` in the same pull request.

`scripts/pr_*` and `.github/` are `risk:high`, so such a pull request always
waits for the maintainer.

## Keeping this page current

The test file names, the cited lines and the dated Dependabot claim drift
first. `test_workflow_action_pins.py` and the structure tests fail when a pin
or a scope changes, but no check reads this page; re-read it when a check is
added to `scripts/check_all.sh` or a factory workflow gains a job.
