---
managed-by: fabiandistler/agents build_project_claude.py
---

## Code review conventions

- Files under test fixtures / `fixtures/` / `bad_examples/` are INTENTIONALLY broken — do not flag their contents as bugs in reviews
- Always check the path/purpose of a file before reporting lint or correctness issues
- When a diff adds a helper, grep the rest of the repo for one with the same behaviour before accepting it. Reviews that stay inside the diff miss this duplication.
