# Actions runs stuck in `queued`

- 2026-11-11: from about 20:17 UTC, new workflow runs in agents stayed
  `queued` with zero jobs; by 20:43 UTC about 100 were queued. The cancel
  API refused them with 409 ("Cannot cancel a workflow run that has not
  been queued yet"). The dotfiles token-probe run 43096185342 was stuck the
  same way. Sources: #797 (section "Incident, 2026-11-11"), #796.
- 2026-11-12: githubstatus.com history (read 2026-11-12) lists two GitHub
  incidents that evening: "Incident with Webhooks", Nov 11 20:22–20:26 UTC,
  and "Impact across multiple GitHub products including Actions, Pages,
  and Copilot products", Nov 11 20:48–21:21 UTC. The stall had a GitHub
  incident behind it. The first stuck run (about 20:17 UTC) predates both
  posted windows; the link rests on the timing, GitHub's notes name no
  cause yet.
- 2026-11-12: recovery: the maintainer used "Update branch" on #791 and
  #795 (merge commits `4778eaf`, `7c0353b`, 08:36 UTC), which gave both PRs
  fresh runs; for #795, CI and pr-review jobs ran 08:36–08:39 UTC. Whether
  the old stuck runs ever ended was not checked. *Superseded 2026-11-13,
  see below.*
- Follow-up (2026-11-12): #797 (open, `ready-for-human`) cuts the no-op
  runs the factory workflows create for issue and comment events; 72 of
  the 95 runs queued at 20:41 UTC were such no-ops. #797 leaves the
  GitHub-side root cause out of scope.
- 2026-11-13 (supersedes the 2026-11-12 "not checked"): the old runs had
  not ended. 108 runs in agents, among them 18 implementer runs for
  #786–#794 and #797, and 5 in dotfiles, among them the token-probe run
  43096185342, were still `queued` with zero jobs since the 2026-11-11
  stall. All 40 runs started since 2026-11-12 had completed.
  Source: [2026-11-13 triage](../snapshots/2026-11-13-triage.md).
- 2026-11-13 (`fabiandistler/agents@0585e8e`): the implementer's capacity
  gate counts only runs whose implement job has started
  (`scripts/implementer_claim.py:341-351`), so the zero-job runs do not
  cause an `at-capacity` stop. Not verified: whether such a run holds back
  a new run in the same per-issue concurrency group (`implementer-<issue>`,
  `.github/workflows/implementer.yml:55-57`).
- 2026-11-13 (#797, PR #805): `claude.yml` no longer triggers on
  `issues`, and `issue-triage.yml` starts no runner for an issue filed
  with a state label or by a bot. A new issue with two labels and one
  comment now creates 8 runs, all skipped without a runner unless one has
  work to do; the per-event count is in
  [issue tracker](../../agents/issue-tracker.md) ("Create many issues").

Related: [cross-repo token exchange](cross-repo-token-exchange.md).
