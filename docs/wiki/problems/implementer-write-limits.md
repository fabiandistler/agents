# What the AFK implementer cannot write

- 2026-11-11: the implementer's App token cannot write `.github/workflows/`. Briefs therefore ask for the YAML under "Workflow to add by hand" in the PR body ([new factory tasks](../decisions/2026-11-11-new-factory-tasks.md)).
- 2026-11-14: the run for #806 (PR #812) found a second limit: the run's tool permissions refuse every write under `.claude/` and to `.pre-commit-config.yaml` (bot comment on #806, 05:47 UTC). `implementer.yml` passes `--allowedTools` with Edit and Write, so the block is most likely Claude Code's own protection of its config files in headless mode. This was inferred, not checked in the Claude Code docs.
- Consequence, 2026-11-14: tickets whose deliverable lies under `.github/workflows/`, `.claude/` or `.pre-commit-config.yaml` go to interactive `claude/*` sessions, or deliver that part as text in the PR body for the maintainer to commit. Triage has to check the brief's file list for these paths before setting `ready-for-agent`.
- 2026-11-14: Rework (#809) and Retro (#814, #825) are merged, but on main there was no `rework.yml`, no Retro workflow and no Retro `run-name` in `implementer.yml` (checked 08:24 UTC). Both tasks stay inactive until the maintainer commits their YAML.

For a split ticket, put each human deliverable under an unindented `##` PR heading
ending in "to add by hand", for example `## Hook config to add by hand`. When
the implementer PR merges in this repository, the
[hand-applied follow-up workflow](../../../.github/workflows/hand-part-follow-up.yml)
copies each section into its own `ready-for-human` issue and links it from the
closed issue.

Related: [implementer lint rounds](implementer-lint-rounds.md), [2026-11-14 decisions](../decisions/2026-11-14-decisions.md).
