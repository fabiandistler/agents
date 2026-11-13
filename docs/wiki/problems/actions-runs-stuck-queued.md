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
  the old stuck runs ever ended was not checked.
- Follow-up (2026-11-12): #797 (open, `ready-for-human`) cuts the no-op
  runs the factory workflows create for issue and comment events; 72 of
  the 95 runs queued at 20:41 UTC were such no-ops. #797 leaves the
  GitHub-side root cause out of scope.
- 2026-11-13: the stuck runs did not end on their own. A `status=queued`
  listing showed 108 runs, all created 2026-11-11 between 20:17:41 and
  20:47:04 UTC (`issue-triage` 36, `Claude Code` 18, `implementer` 18,
  `CI` 9, `Triage label` 9, 18 others); none newer. #797 removed the `issues` trigger from `claude.yml` and stopped
  `issue-triage.yml` from starting a runner for issues filed with a state
  label; a new issue with two labels and one comment now creates 8 runs, all
  skipped without a runner unless one of them has work to do.

Related: [cross-repo token exchange](cross-repo-token-exchange.md).
