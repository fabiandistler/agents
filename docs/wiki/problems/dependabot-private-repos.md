# Dependabot never runs on private repos

- 2026-11-10: Every Dependabot update job on the private repos dotfiles,
  repo-maintenance, escoRAG, def, rrefactor, gtd-cli and dnd-solo requested
  the runner label `dependabot`, waited 24 h for a runner and was cancelled.
  None ever opened a PR; the oldest cancelled run found is from 2025-11-16.
  The public repos agents and fmisc request `ubuntu-latest` and succeed.
  Sources: diagnosis comments on fabiandistler/dotfiles#52 and
  fabiandistler/repo-maintenance#142.
- 2026-11-10: Inferred cause, not yet verified: the repo setting
  Settings → Advanced Security → Dependabot version updates → Runner type
  is "Labeled runner". The API does not expose it. GitHub documents the
  setting per repository and per organization; no personal-account default
  was found, so each private repo has to be checked by hand.
- 2026-11-10: Changing the setting starts no run, and a re-run of a
  cancelled job reportedly stays stuck; verify on the next scheduled run.
- Idea (2026-11-10, not decided): a maintenance check that flags a repo
  whose recent Dependabot runs all ended `cancelled`. The failure stayed
  silent for about a year because a cancelled bot run notifies nobody.

Related: [2026-11-10 ready-for-human queue](../snapshots/2026-11-10-ready-for-human.md).

## 2026-11-14: setting changed, jobs still request `dependabot`

- 2026-11-14 ~07:00–07:15 UTC: the maintainer set Runner type → Standard GitHub runner in dotfiles and repo-maintenance. After a reload the page showed it, but the manually started runs 43570313662 (repo-maintenance) and 43570268659 (dotfiles) still requested `labels=dependabot` and stayed `queued` with no runner (watched until 07:21 UTC).
- 2026-11-14: for comparison, the public agents repo's Dependabot jobs request `ubuntu-latest` and run on GitHub-hosted runners (e.g. run 43563336916, 05:49 UTC). GitHub's docs ([configure on GitHub-hosted runners](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-on-github-hosted-runners), [Dependabot on Actions](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-on-actions), read 2026-11-14) name no private-repo restriction, and say standard runners rely on `ubuntu-latest`.
- So the 2026-11-10 diagnosis (Runner type set to Labeled runner) is **not confirmed**: the setting does not reach the jobs. Suggested next steps given to the user: toggle Labeled → save → Standard → save; then turn version updates off and on; then a GitHub Support ticket, or drop Dependabot in the private repos. The scheduled check of 2026-11-15 09:07 UTC was told to count only runs after 2026-11-14T07:00Z.
