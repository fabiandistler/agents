# 2026-11-11 — New factory tasks: Rework, Fix, Retro

- **Decision (user, 2026-11-11, chief-of-staff session):** add three
  tasks to the software factory, each filed as an issue with an Agent
  Brief comment and labelled `ready-for-human`:
  - #782 Rework — act on a non-pass automated review of an
    `agent/issue-<n>` PR, capped at two rounds, then hand to a human.
  - #783 Fix — file each failed factory run as one deduplicated issue,
    model-free.
  - #784 Retro — about one merged agent PR in ten becomes a proposed change
    to the factory's own instruction texts.
- The maintainer moves each issue to `ready-for-agent` when it should be
  built. Suggested order (session, 2026-11-11): Fix, then Rework, then
  Retro.
- **Not chosen (2026-11-11):** a Ratchet task.
- **Constraint (2026-11-11):** the implementer's App token cannot write
  `.github/workflows/`. Each brief therefore asks for the workflow file and
  its guard tests in the PR body under "Workflow to add by hand"; the
  maintainer commits the YAML. Source: the Agent Brief comments on #782,
  #783 and #784.
- ADR numbers reserved in the briefs (2026-11-11): 0015 Rework, 0016 Fix,
  0017 Retro.

Related: [expansion order](2026-11-11-factory-expansion-order.md).
