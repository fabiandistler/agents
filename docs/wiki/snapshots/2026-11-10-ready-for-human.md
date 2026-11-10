# 2026-11-10 ready-for-human queue

Open issues labelled `ready-for-human` across agents, repo-maintenance and
dotfiles on 2026-11-10, and the order recommended to the user that day.

1. fabiandistler/dotfiles#52 and fabiandistler/repo-maintenance#142: one
   cause, a repo setting only a person can change. See
   [Dependabot on private repos](../problems/dependabot-private-repos.md).
   First because it takes minutes and the verification runs are weekly.
2. fabiandistler/agents#753: needs design decisions before an agent can
   build it (standards-file interface, where caller risk rules come from,
   size budget, repo description). It blocks fabiandistler/dotfiles#56,
   whose scope excludes risk gating and auto-merge, so caller risk rules
   were suggested as a separate, deferred ticket.
3. fabiandistler/repo-maintenance#137: not actionable before a maintenance
   PR exists; the next weekly maintenance run was expected 2026-11-16.

Observation, 2026-11-10: agents#753 received two triage-bot comments 46 s
apart (runs 42801703151 and 42801703334); cause not investigated.
