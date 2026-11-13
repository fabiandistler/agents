# No agent consumes `ready-for-agent` outside agents

- 2026-11-13 (`fabiandistler/repo-maintenance@8d48bb2`,
  `fabiandistler/dotfiles@83376fb`): neither repository has an implementer
  workflow, so a `ready-for-agent` label there starts no run. The thin
  caller workflows of the
  [factory rollout](../decisions/2026-11-11-factory-rollout.md) had not
  landed; the onboarding issues dotfiles#61 and repo-maintenance#153 were
  open and `ready-for-human`.
- 2026-11-13: all three scheduled tasks named "Weekly issue sweep" were
  disabled: `trig_017XrHjyAa3owGmFmCpAr2S1` (disabled 2026-11-09),
  `trig_01FDujccZqWMu6pBji59YmBW` and `trig_01XCRCjbPZpkusCJ6EDhKdD9`
  (disable dates not recorded). See [schedules](../schedules.md).
- Example (2026-11-13): repo-maintenance#150 carries `ready-for-agent`; the
  triage judged the label premature and left it in place, since nothing
  picks it up ([2026-11-13 triage](../snapshots/2026-11-13-triage.md)).
- Consequence (2026-11-13): until the rollout lands, work on issues in
  these two repositories needs an interactive session or a person; labelling
  alone moves nothing.

Related: [cross-repo token exchange](cross-repo-token-exchange.md),
[cross-repo `Blocked by` URLs](cross-repo-blocked-by.md).
