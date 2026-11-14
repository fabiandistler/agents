# Implementer spends its check rounds on lint

- 2026-11-13: retro of implementer run 43500665465 (issue #783, PR #800),
  run by a chief-of-staff subagent. The run delivered the whole feature in
  15 minutes and 43 turns ($2.40), but all three `scripts/check_all.sh`
  rounds were red on `prek` only: ruff format, then `ty`, then ruff ISC004.
  The stop rule counted three red rounds and opened #800 as a draft, so
  pr-review skipped it; CI on the final head was green.
- Causes found, as of `fabiandistler/agents@0585e8e`:
  - `implementer.yml:128-129` names the 3-round limit but does not define
    a round; a failure the hook already fixed counts.
  - `check_all.sh:146` runs prek with `--show-diff-on-failure`, and a
    failing check shows only its last 40 lines; a long diff pushes the
    hooks' Failed lines out of view (reproduced in #807).
  - No PostToolUse hook formats or lints a file when the agent edits it.
  - ISC004's fix is unsafe, so `ruff check --fix` leaves it.
- 2026-11-13: earlier agent PRs (#750 to #779) show no fix-up commits;
  #800 was the first stop-rule hit since the move to Actions.
- Follow-ups filed 2026-11-14: #806 (lint on edit, agent), #807 (show all
  hook failures, agent), #808 (define a round in the stop rule, workflow,
  interactive session).

Related: [shared usage limit](shared-usage-limit.md).
