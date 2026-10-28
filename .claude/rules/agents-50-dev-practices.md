---
managed-by: fabiandistler/agents build_project_claude.py
---

## Development best practices

- A PR body names its issue (`Closes #n`); with no issue, write `No issue: <reason>`.
- Put refactoring in its own commit.
- Include tests with the change they cover.
- Before pushing to a PR branch, check that the PR is still open: commits pushed after the merge never reach the default branch.
- If it is merged or closed, branch from the current default branch, carry the unmerged commits over, and open a new PR that links the old one.
