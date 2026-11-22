# Schedules

- 2026-10-19: User approved recurring schedules.
  - **Wiki lint**, weekly Mon 08:51 Europe/Berlin (timezone assumed, not
    confirmed by the user), fresh session per run, push notification on.
    Stored without MCP connectors; the prompt attaches the repo via
    `add_repo` and falls back to `gh api`. Scheduled-task id
    `trig_01RYoSCeYww5X82TSzSkGh4r`.
  - Weekly skill audit (pre-existing, see `docs/agents/skill-audit.md`):
    rotation observed stuck on slice 2/4; diagnosis dispatched 2026-10-19
    (branch `claude/audit-rotation`, refs #466).
  - 2026-10-19 superseded: diagnosis found no stuck rotation; slice is
    `ISO week % 4`, and manual fires within one week repeat the slice.
    Week 53/1 collision noted. No repo change made; options put to the user.
  - 2026-10-19: User chose to leave `scripts/skill_audit_select.py` as is
    (option A). Manual fires within a week should pass `--week <next>`;
    the week 53/1 collision is accepted.
- 2026-11-01 superseded (wiki-lint setup line): the wiki-lint prompt no
  longer attaches the repo via `add_repo`. The auto-mode classifier blocked
  that call in an unattended run on 2026-10-28; the repo is now attached to
  the scheduled task and cloned at session start, with `gh api` as fallback
  and a "RUN FAILED" notification if the checkout is missing. Source: the
  stored prompt of the 2026-11-01 run.
- 2026-11-10: User decided to move this repo's agent runs to GitHub Actions
  (ADR-0014). The implementer (scheduled task "Software factory",
  `trig_013XPWNtycFd7A95gpEJDdf6`) and the skill audit
  (`trig_0134B5GMw25GGcMHrtNLmtVj`) get `implementer.yml` and
  `skill-audit.yml`; each scheduled task is disabled after its workflow's
  first green manual run. "agents repo-maintenance"
  (`trig_016FpvZkZFm5tPdbFCrXebbT`) stays a scheduled task: it needs the
  private repo-maintenance plugin. Wiki lint was already disabled
  (2026-11-09) and is not moved.
- 2026-11-13: all three scheduled tasks named "Weekly issue sweep" were
  disabled: `trig_017XrHjyAa3owGmFmCpAr2S1` (disabled 2026-11-09),
  `trig_01FDujccZqWMu6pBji59YmBW` and `trig_01XCRCjbPZpkusCJ6EDhKdD9`
  (disable dates not recorded). With no implementer workflow in
  repo-maintenance and dotfiles, nothing there consumes `ready-for-agent`:
  [no agent consumer outside agents](problems/no-agent-consumer-outside-agents.md).
  *Superseded 2026-11-20 for the implementer, see below.*
- 2026-11-13: one-off scheduled check `trig_01HdS5BtHMcP5ris2tjwviwh` for
  the Dependabot runner-type setting (repo-maintenance#142, dotfiles#52),
  due 2026-11-15 09:07 UTC. The scheduled maintenance run of 2026-11-16
  07:32 UTC is expected to open repo-maintenance's first deps-audit PR
  (repo-maintenance#137). *Superseded 2026-11-20 for the maintenance run,
  see below.*
- 2026-11-14: one-off scheduled check `trig_0159BdYMZ82Lzb9o2aTGk19Y`
  ("Verify #763 during pr-review brownout"), due 2026-11-16 17:40 UTC
  ([2026-11-14 decisions](decisions/2026-11-14-decisions.md)).
- 2026-11-20, result of that check [read]: it fired 2026-11-16 17:41:50 UTC
  with status FAILED and `ended_reason: auto_disabled_session_gone`; the
  verification never ran. No run of any workflow was created in agents
  between 16:00 and 18:00 UTC that day, and no pr-review run between 15:30
  and 18:30, so the brownout gave no evidence either. No other wiki page
  recorded this result. The event policy (#763) stays unverified, with
  GitHub's default block from 2026-12-02; see
  [2026-11-20 status sweep](snapshots/2026-11-20-status.md) and
  [runs without a trace](problems/runs-without-trace.md).
- 2026-11-20 (supersedes the 2026-11-13 "nothing there consumes
  `ready-for-agent`") [read]: repo-maintenance and dotfiles had implementer
  callers since 2026-11-14; see
  [no agent consumer outside agents](problems/no-agent-consumer-outside-agents.md).
- 2026-11-20 [read]: the weekly maintenance run on repo-maintenance is the
  scheduled task `trig_01XPRmF1GFqjd1qFoWGvCi1G` ("repo-maintenance weekly
  maintenance run", `CRON_TZ=Europe/Berlin 32 8 * * 1`, enabled, model
  `claude-opus-5-5`, no connectors, push on; created 2026-10-31, updated
  2026-11-10 09:38 UTC). This page had not named it before. Its schedule
  matches `docs/agents/weekly-maintenance-routine.md:29` at
  `fabiandistler/repo-maintenance@bacc59d`. Next run 2026-11-23 07:32 UTC.
- 2026-11-20 [read]: `trig_016FpvZkZFm5tPdbFCrXebbT` ("agents
  repo-maintenance", 2026-11-10 above) runs the skill on
  `fabiandistler/agents`, Sundays 01:34 Europe/Berlin
  (`CRON_TZ=Europe/Berlin 34 1 * * 0`; last run 2026-11-15 00:35 UTC), not on
  repo-maintenance. Its stored prompt, and that of the dotfiles task
  `trig_01XtaNXwvNSQbiDAZJq2vBPV`, is an older direct prompt, not the
  bootstrap that repo-maintenance's
  `docs/agents/target-repo-maintenance-routine.md` says the prompt field
  holds.
- 2026-11-20 (supersedes the 2026-11-13 expectation for the 2026-11-16
  maintenance run) [read]: `trig_01XPRmF1GFqjd1qFoWGvCi1G` fired 2026-11-16
  07:32:42 UTC (session `cse_0154VwoYH6snGir8pi7WAc75`), stopped when the
  auto-mode classifier gave no verdict on seven Bash calls in a row, and sent
  a "RUN FAILED" push notification at 07:34:59 UTC. No repo trace; its
  `last_run.status` reads `SUCCEEDED`. [inferred] A transient classifier
  outage. repo-maintenance#137 still waits; see
  [runs without a trace](problems/runs-without-trace.md).
- 2026-11-20 [read]: repo-maintenance#142 and dotfiles#52 closed
  2026-11-14 17:58 UTC, before the check `trig_01HdS5BtHMcP5ris2tjwviwh` was
  due; that check's outcome was not read in the 2026-11-20 sweep.
- 2026-11-20, skill audit on Actions [read]: `.github/workflows/skill-audit.yml:16`
  (`fabiandistler/agents@acbd1c9`) has cron `41 13 8,22 * *` with
  `timezone: Europe/Berlin`. No scheduled run yet; only the manual
  dispatches 42791057621 (failure) and 42793271828 (success), both
  2026-11-10. First scheduled run due 2026-11-22 13:41 Europe/Berlin.
- 2026-11-20 [read]: scheduled Actions runs in agents started late. retro
  (cron `23 6 * * *`, `timezone: Europe/Berlin`, `.github/workflows/retro.yml:17-18`)
  started 14:16–14:39 UTC on 2026-11-17 to -19; the hourly implementer-queue
  fired 10 times since 2026-11-17 against about 79 slots. [inferred] The
  skill audit may start hours late or be dropped; look on the evening of
  2026-11-22 and dispatch it by hand if no run exists.
- 2026-11-20, the three maintenance routines [read: `get_trigger`; sources
  from `get_session`, which `get_trigger` does not show]. Each starts a new
  session per fire, has push on and is bound to no device:
  - agents, `trig_016FpvZkZFm5tPdbFCrXebbT` ("agents repo-maintenance"):
    `CRON_TZ=Europe/Berlin 34 1 * * 0`, next run 2026-11-22 00:34 UTC. No
    model pinned (`""`), connector Claude-Docs. Prompt last updated
    2026-11-02 06:56 UTC. Sources: agents and repo-maintenance.
  - dotfiles, `trig_01XtaNXwvNSQbiDAZJq2vBPV` ("Dotfiles repo maintenance"):
    `36 1 * * 0` (no `CRON_TZ`, so UTC), next run 2026-11-22 01:36 UTC. No
    model pinned, connector Claude-Docs. Prompt last updated 2026-10-27
    14:47 UTC. Sources: dotfiles, repo-maintenance and agents.
  - repo-maintenance, `trig_01XPRmF1GFqjd1qFoWGvCi1G`:
    `CRON_TZ=Europe/Berlin 32 8 * * 1`, next run 2026-11-23 07:32 UTC. Model
    `claude-opus-5-5`, no connectors. Its prompt is the bootstrap.
- 2026-11-20, decided ([2026-11-20 decisions](decisions/2026-11-20-decisions.md)):
  pin Opus and the bootstrap prompt on the agents and dotfiles routines. Run
  dotfiles twice a week for three weeks; the prepared cron is
  `CRON_TZ=UTC 36 1 * * 0,3` (Sundays and Wednesdays 01:36 UTC). For the
  2026-11-22 runs to use the new settings, they must be applied before
  00:34 UTC (agents) and 01:36 UTC (dotfiles) that day. The maintainer
  applies them by hand; whether the maintainer had done so was not read on
  2026-11-20.
- 2026-11-20, limitation [read]: agents cannot change these routines.
  `update_trigger` failed with an error because the routines were created via
  `http_api`. Prompt, model and cron changes go through the routine's page
  (`claude.ai/code/routines/<id>`) by hand.
- 2026-11-20: one-shot evaluation task `trig_01Hmdw7paA38BPcfNMoQhGhF`,
  created that day. It fires 2026-12-10 09:23 UTC in a fresh session, with a
  push notification. It was created with no sources and no connectors.
  [inferred] It likely cannot read dotfiles unless the maintainer adds
  sources on its page. An agent's call to disable it was refused by the
  auto-mode classifier on 2026-11-20.
- 2026-11-20: the dotfiles test does not revert by itself. To end it, set the
  cron back to `36 1 * * 0` after the 2026-12-09 run and before Wednesday
  2026-12-16 01:36 UTC, when the first unwanted run would fire. Doing this is
  a manual step. If the test cron is applied before 2026-11-22, the test runs
  on 2026-11-22, -25 and -29, 2026-12-02, -06 and -09: six runs, three of
  them added [inferred].
- 2026-11-22 [read]: the first scheduled `skill-audit.yml` run (22nd, 13:41
  Europe/Berlin) had not started by 19:05; it was dispatched by hand
  (run 45053131557, success). Scheduled runs in this repo start late across
  the board: `retro.yml` (06:23 Berlin) started 7–9 hours late every day
  2026-11-15 to -22, and the hourly `implementer-queue.yml` ran 2–4 times a
  day. The skill audit therefore gets two catch-up days after the 8th and the
  22nd and a model-free gate (`scripts/skill_audit_gate.py`) that skips a
  scheduled run once an audit has succeeded in the half-month.
- 2026-11-22 superseded (skill audit, 2026-10-19 lines): `--week` no longer
  exists. `scripts/skill_audit_select.py` derives the slice from the run
  date's half-month (`--date`), so a manual run needs no flag, and the
  workflow's manual run takes no inputs.
