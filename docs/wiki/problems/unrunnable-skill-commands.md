# Unrunnable commands in skills

- 2026-10-19: Recurring fix type in merged PRs: commands in SKILL.md that
  fail when an agent runs them (#457, #515). Open audit findings (#466) on
  `repo-status` (pagination walks full PR history) and `release-pr` (an exit
  code that can halt the agent).
- Idea (2026-10-19, not decided): a CI check that executes or at least
  shell-parses the snippets in SKILL.md files.

Related: [router cross-references](router-cross-references.md).
- 2026-10-20: repo-status pagination (403 on `--paginate` via a
  `repositories/<id>` link), release-pr exit code 3 on `open-heading`, and
  `gh pr list` in MAINTENANCE.md fixed in #542, each reproduced first.
  The general "execute snippets in CI" idea remains undecided.
