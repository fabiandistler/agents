# Dependabot never runs on private repos

- 2026-11-10: Every Dependabot update job on the private repos dotfiles,
  repo-maintenance, escoRAG, def, rrefactor, gtd-cli and dnd-solo requested
  the runner label `dependabot`, waited 24 h for a runner and was cancelled.
  None ever opened a PR; the oldest cancelled run found is from 2025-11-16.
  The public repos agents and fmisc request `ubuntu-latest` and succeed.
  Sources: diagnosis comments on fabiandistler/dotfiles#52 and
  fabiandistler/repo-maintenance#142. *Superseded 2026-11-20 for dotfiles
  and repo-maintenance, see below.*
- 2026-11-10: Inferred cause, not yet verified: the repo setting
  Settings → Advanced Security → Dependabot version updates → Runner type
  is "Labeled runner". The API does not expose it. GitHub documents the
  setting per repository and per organization; no personal-account default
  was found, so each private repo has to be checked by hand. *Superseded
  2026-11-20 for dotfiles and repo-maintenance, see below.*
- 2026-11-10: Changing the setting starts no run, and a re-run of a
  cancelled job reportedly stays stuck; verify on the next scheduled run.
- Idea (2026-11-10, not decided): a maintenance check that flags a repo
  whose recent Dependabot runs all ended `cancelled`. The failure stayed
  silent for about a year because a cancelled bot run notifies nobody.

Related: [2026-11-10 ready-for-human queue](../snapshots/2026-11-10-ready-for-human.md).

## 2026-11-14: setting changed, jobs still request `dependabot`

- 2026-11-14 ~07:00–07:15 UTC: the maintainer set Runner type → Standard GitHub runner in dotfiles and repo-maintenance. After a reload the page showed it, but the manually started runs 43570313662 (repo-maintenance) and 43570268659 (dotfiles) still requested `labels=dependabot` and stayed `queued` with no runner (watched until 07:21 UTC).
- 2026-11-14: for comparison, the public agents repo's Dependabot jobs request `ubuntu-latest` and run on GitHub-hosted runners (e.g. run 43563336916, 05:49 UTC). GitHub's docs ([configure on GitHub-hosted runners](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-on-github-hosted-runners), [Dependabot on Actions](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-on-actions), read 2026-11-14) name no private-repo restriction, and say standard runners rely on `ubuntu-latest`.
- So the 2026-11-10 diagnosis (Runner type set to Labeled runner) is **not confirmed**: the setting does not reach the jobs. Suggested next steps given to the user: toggle Labeled → save → Standard → save; then turn version updates off and on; then a GitHub Support ticket, or drop Dependabot in the private repos. The scheduled check of 2026-11-15 09:07 UTC was told to count only runs after 2026-11-14T07:00Z. *Superseded 2026-11-20, see below.*

## 2026-11-20: fixed in dotfiles and repo-maintenance on 2026-11-14

Read in the [2026-11-20 status sweep](../snapshots/2026-11-20-status.md).

- 2026-11-20 (supersedes the 2026-11-14 "not confirmed" and, for these two
  repositories, the 2026-11-10 "not yet verified") [read]: the closing
  comment of repo-maintenance#142 says the Runner type was Labeled runner and
  the maintainer saved Standard GitHub runner again; run 43623710902
  (2026-11-14 17:55 UTC) then requested `ubuntu-latest` and succeeded. In
  dotfiles, run 43596914050 (2026-11-14 12:52 UTC) requested `ubuntu-latest`
  and succeeded (dotfiles#52). Both issues closed completed 2026-11-14
  17:58 UTC.
- 2026-11-20 (supersedes "none ever opened a PR" for these two repositories)
  [read]: the Dependabot PRs repo-maintenance#155 and dotfiles#64 merged
  2026-11-14.
- 2026-11-20: the first scheduled Dependabot runs after the fix had not
  happened yet; only the manual fix runs existed [read]. Expected about
  2026-11-20 20:44 UTC in repo-maintenance and 2026-11-21 12:52 UTC in
  dotfiles [inferred from the weekly cadence of past runs]. Open: whether
  they bump the callers' `fabiandistler/agents/...@<sha>` pins, as asked in
  the closing comments of repo-maintenance#153 and dotfiles#61 [read].
- 2026-11-20: escoRAG, def, rrefactor, gtd-cli and dnd-solo were outside the
  sweep; nothing newer than 2026-11-10 is recorded for them.
