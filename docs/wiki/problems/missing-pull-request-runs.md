# A required check that never starts

- 2026-11-14: for PR #826's head `fc2a7d3` (pushed 08:24 UTC by the implementer), GitHub started only CI's `push` run; no `pull_request` run started for any workflow. `secrets` comes only from `maintenance-gate.yml`, which runs on `pull_request`, so this required check (ruleset 18264711 since 2026-11-14) stayed "Expected — waiting" and the merge was blocked. Other PRs before and after got their `pull_request` runs (08:20, 08:44, 08:46 UTC).
- Recovery, 2026-11-14: `update-branch` returned 422 because of merge conflicts, so a subagent merged main into the branch (merge commit `60f94fd`). The push started the `pull_request` runs, all four checks passed, and the maintainer merged #826 at 11:37 UTC. Rules respected: no empty commit, no close/reopen.
- Not investigated: why GitHub dropped the `pull_request` events for that push. No incident was checked.

Related: [Actions runs stuck in queued](actions-runs-stuck-queued.md).
