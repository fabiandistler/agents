---
managed-by: fabiandistler/agents build_project_claude.py
---

## Bug fixing

- Before editing the function a bug report points at, grep all of its callers. Fix it once in the shared function, not at the one call site the report names: a call-site patch leaves the sibling callers broken.
- Count failed fix attempts. After the third, stop: if each fix exposed new coupling elsewhere, the design is the bug — list attempts, ask before fix #4.
