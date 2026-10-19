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
