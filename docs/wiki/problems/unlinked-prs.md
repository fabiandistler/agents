# PRs that do not close their issue

- 2026-10-19: #533 stayed open after its work merged via #531/#532,
  because the PR bodies did not carry a closing keyword. A worker was then
  sent to implement already-done work. The rule "Always connect issues
  with PRs" (`instructions/50-dev-practices.md`) has no enforcement as of
  `fabiandistler/agents@a9b3494`.
- Idea (2026-10-19, not decided): before dispatching a worker on an issue,
  search merged PRs and `git log` for the issue number and its keywords.
