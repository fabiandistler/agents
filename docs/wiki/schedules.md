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
