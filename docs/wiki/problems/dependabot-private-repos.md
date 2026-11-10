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
