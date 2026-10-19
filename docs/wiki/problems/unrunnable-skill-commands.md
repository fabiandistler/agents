# Unrunnable commands in skills

- 2026-10-19: Recurring fix type in merged PRs: commands in SKILL.md that
  fail when an agent runs them (#457, #515). Open audit findings (#466) on
  `repo-status` (pagination walks full PR history) and `release-pr` (an exit
  code that can halt the agent).
- Idea (2026-10-19, not decided): a CI check that executes or at least
  shell-parses the snippets in SKILL.md files.

Related: [router cross-references](router-cross-references.md).
