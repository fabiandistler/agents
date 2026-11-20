# Spec: maintenance runs on Actions, open questions and tickets (parked draft)

*2026-11-20: Parked draft, not published as an issue; decision: option B (see
[decisions page](../decisions/2026-11-20-decisions.md)).* Part of the draft
[maintenance runs move from routines to GitHub Actions](2026-11-20-maintenance-runs-on-actions-draft.md); its notes
and the list of parts are there. Copied unchanged.

---

## Open questions for the maintainer

1. **Plugin read credential for agents and dotfiles**: a read-only deploy key on repo-maintenance
   (recommended: no new action or App; used only before the model step), a maintainer-owned App
   with contents read installed on repo-maintenance only (hour-long tokens, one more pinned action),
   a fine-grained personal access token (what ADR-0014 avoided), or make repo-maintenance public
   (no credential; but a public repository's schedules stop after 60 idle days and
   `pull_request_target` needs an event policy from 2026-12-02)?
2. **Bot authorship**: accept that run-filed issues get no automated triage and need your Agent
   Brief before `ready-for-agent`?
3. **Plugin version**: follow repo-maintenance `main` at run start (recommended, as the routines
   do), or pin a repo-maintenance commit in the callers and bump it like the agents pin?
4. **Model ID**: the alias `opus` (follows releases, as the implementer) or the full ID the
   repo-maintenance routine uses?
5. **Dropped schedules**: accept the Actions schedule as is and check the run list during the
   three-week test, or add a backstop now (for example a model-free due gate on a daily slot)?
6. **Cutover order**: repo-maintenance, dotfiles, agents? Or dotfiles first, so the cadence test
   starts sooner?
7. **Routines until cutover**: leave them as they are, or still apply the prepared updates
   (bootstrap prompts, Opus, dotfiles Sunday and Wednesday)?
8. **Write-limited fixes**: accept that fixes to workflow files, `.claude/` and the hook config
   arrive as issues instead of diffs?

## Ticket sketch

Thin vertical slices in merge order. "Implementer" says whether the factory implementer may do it:
it cannot write `.github/workflows/`, `.claude/` or `.pre-commit-config.yaml`
(`docs/wiki/problems/implementer-write-limits.md`); those go to an interactive `claude/*` session or
the maintainer. Blockers inside one repository become `Blocked by #<n>` once filed. Blockers across
repositories are written as prose with no URL ("waits for agents ticket 5 merged on main"), because a
cross-repository `Blocked by` URL blocks the implementer until a person removes it
(`docs/wiki/problems/cross-repo-blocked-by.md`); check them by hand before starting.

| # | Repo | Slice and deliverables | Implementer | Blockers |
|---|---|---|---|---|
| 1 | agents | ADR "maintenance runs in GitHub Actions": credential, location, plugin version, concurrency, cutover; amend ADR-0014 status and ADR-0018's table; ADR index. `docs/adr/00NN-maintenance-runs-in-github-actions.md`, `docs/adr/0014-…md`, `docs/adr/0018-…md`, `docs/adr/README.md` | Yes | Maintainer answers to questions 1–3 |
| 2 | repo-maintenance | Shared maintenance run instructions with outcome classes; both routine `## Prompt` blocks cut to their cloud adapter that points at it (paths and headings unchanged); the gate scans the new file. Refactor in its own commit. `docs/agents/maintenance-run-instructions.md`, `docs/agents/weekly-maintenance-routine.md`, `docs/agents/target-repo-maintenance-routine.md`, `.github/workflows/maintenance-gate.yml` (`--include`), `tests/test_instruction_unicode.py`, `MAINTENANCE.md` (gate row) | No (gate workflow line) | None; merge between routine fires and watch the next repo-maintenance routine run |
| 3 | agents | Fix task and handoff names learn the maintenance caller. `scripts/factory_handoff.py`, `scripts/factory_failure_policy.py`, `scripts/test_factory_handoff.py`, `scripts/test_factory_failure_policy.py` | Yes | None |
| 4 | agents | Vendor-lock check and re-vendor accept a local upstream (the plugin checkout); deps-audit row updated. `scripts/vendor_repo_maintenance.py`, `scripts/vendoring.py`, `scripts/test_vendor_repo_maintenance.py`, `MAINTENANCE.md` (deps-audit row) | Yes | None |
| 5 | agents | Reusable maintenance workflow and agents' caller with manual dispatch only; agents' Fix caller watches it; structure tests; factory docs. `.github/workflows/factory-maintenance-run.yml`, `.github/workflows/maintenance-run.yml`, `.github/workflows/fix-task.yml`, `scripts/test_agent_run_workflows.py`, `scripts/agent_run_workflow_testkit.py`, `docs/factory/architecture.md`, `docs/factory/changing-a-task.md`, `docs/agents/factory-onboarding.md`, `AGENTS.md` | No | Blocked by 3 and 1 (same repo); waits for repo-maintenance ticket 2 merged |
| 6 | repo-maintenance | Caller with manual dispatch only, Fix watch list, caller structure test, all callers bumped to one agents SHA. `.github/workflows/maintenance-run.yml`, `.github/workflows/fix-task.yml`, the six caller pins, `tests/test_factory_callers.py`, `AGENTS.md`. Then the maintainer's plan-only and first real dispatch | No | Blocked by 2 (same repo); waits for agents ticket 5 merged |
| 7 | repo-maintenance | Cutover: schedule Mondays 08:32 Europe/Berlin (squash merge), routine disabled the same day, README's run section rewritten. `.github/workflows/maintenance-run.yml`, `tests/test_factory_callers.py`, `README.md` | No | Blocked by 6 and its first green run |
| 8 | dotfiles | Caller with manual dispatch only (setup command as the implementer's), Fix watch list, caller structure test, one agents SHA for all callers and `AGENTS_COMMIT`. `.github/workflows/maintenance-run.yml`, `.github/workflows/fix-task.yml`, the six caller pins, `scripts/install-runner-standards.sh` pin, `tests/test_factory_callers.py`, `README.md`. Then the two dispatches | No | Waits for agents ticket 5 merged and the plugin read secret (manual step 1) |
| 9 | dotfiles | Cutover and start of the three-week test: schedule Sundays and Wednesdays 01:36 UTC (squash merge), routine disabled the same day. `.github/workflows/maintenance-run.yml`, `tests/test_factory_callers.py` | No | Blocked by 8 and its first green run |
| 10 | agents | Cutover: schedule Sundays 01:34 Europe/Berlin (squash merge), routine disabled the same day; catalog Baseline drops the cloud-hook paragraph; wiki schedules entry for all cutovers. `.github/workflows/maintenance-run.yml`, `scripts/test_agent_run_workflows.py`, `MAINTENANCE.md` (Baseline), `docs/wiki/schedules.md` | No | Blocked by 4 and 5, and 5's first green run; plugin read secret in agents (manual step 1); after dotfiles ticket 9 by the chosen order |
| 11 | dotfiles | End of the cadence test: apply the maintainer's decision (keep Wednesday or drop it). `.github/workflows/maintenance-run.yml`, `tests/test_factory_callers.py` | No | Blocked by 9; due three weeks after 9's merge |
| 12 | repo-maintenance | Retire the routine docs: delete bootstrap prompts, cloud adapters and Settings tables; drop the routine files from the gate's include list; README and plugin README mention Actions only. `docs/agents/*routine*.md`, `.github/workflows/maintenance-gate.yml`, `tests/test_instruction_unicode.py`, `README.md`, `plugins/repo-maintenance/README.md`, `MAINTENANCE.md` | No (gate workflow line) | Blocked by 7; waits for dotfiles ticket 9 and agents ticket 10 |

12 tickets. Order: 1, 2, 3 and 4 in parallel; then 5; then 6 and 7; then 8 and 9; then 10; 11 when
the test ends; 12 last. Only tickets 1, 3 and 4 are for the implementer; the other nine touch
workflow files and go to an interactive session or the maintainer.
