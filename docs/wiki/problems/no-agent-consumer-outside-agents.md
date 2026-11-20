# No agent consumes `ready-for-agent` outside agents

- 2026-11-13 (`fabiandistler/repo-maintenance@8d48bb2`,
  `fabiandistler/dotfiles@83376fb`): neither repository has an implementer
  workflow, so a `ready-for-agent` label there starts no run. The thin
  caller workflows of the
  [factory rollout](../decisions/2026-11-11-factory-rollout.md) had not
  landed; the onboarding issues dotfiles#61 and repo-maintenance#153 were
  open and `ready-for-human`. *Superseded 2026-11-20, see below.*
- 2026-11-13: all three scheduled tasks named "Weekly issue sweep" were
  disabled: `trig_017XrHjyAa3owGmFmCpAr2S1` (disabled 2026-11-09),
  `trig_01FDujccZqWMu6pBji59YmBW` and `trig_01XCRCjbPZpkusCJ6EDhKdD9`
  (disable dates not recorded). See [schedules](../schedules.md).
- Example (2026-11-13): repo-maintenance#150 carries `ready-for-agent`; the
  triage judged the label premature and left it in place, since nothing
  picks it up ([2026-11-13 triage](../snapshots/2026-11-13-triage.md)).
  *Superseded 2026-11-20, see below.*
- Consequence (2026-11-13): until the rollout lands, work on issues in
  these two repositories needs an interactive session or a person; labelling
  alone moves nothing. *Superseded 2026-11-20, see below.*

## 2026-11-20: callers landed on 2026-11-14

Read in the [2026-11-20 status sweep](../snapshots/2026-11-20-status.md).

- 2026-11-20 (supersedes the 2026-11-13 claims above) [read]: both
  repositories have an implementer caller since 2026-11-14 (PR
  repo-maintenance#156, merged 18:36 UTC; PR dotfiles#65, merged 18:35 UTC),
  plus `rework.yml` and `fix-task.yml` since 2026-11-15 (PR
  repo-maintenance#163, PR dotfiles#72). Since 2026-11-19 the callers pin
  `fabiandistler/agents@8afe860` (PR repo-maintenance#173, PR dotfiles#73).
  Read at `fabiandistler/repo-maintenance@bacc59d` and
  `fabiandistler/dotfiles@50f4dd6`.
- 2026-11-20 [read]: implementer runs had opened PRs for repo-maintenance#159
  (PR #160), #147 (PR #158) and #151 (PR #164), and for dotfiles#66 (PR #67)
  and #69 (PR #70).
- 2026-11-20 [read]: repo-maintenance#150 closed 2026-11-14 07:11 UTC via PR
  repo-maintenance#154, from an interactive branch before any implementer
  existed there. dotfiles#61 and repo-maintenance#153 closed completed
  2026-11-14 20:01 UTC.
- 2026-11-20 [read]: no `ready-for-agent` issue was open in either
  repository.

Related: [cross-repo token exchange](cross-repo-token-exchange.md),
[cross-repo `Blocked by` URLs](cross-repo-blocked-by.md).
