---
managed-by: fabiandistler/agents build_project_claude.py
---

## Coding standards

- [rule] All text in code, comments, and README files should be in English
- [rule] Before writing a helper, search the codebase (`git grep`) for one with the same behaviour. Duplicate-code checks miss the same logic written differently.
- [rule] Do not catch broad exceptions or return a default (`None`, `NULL`, `NA`, `{}`) just to make code run. Let the error surface unless there is a real recovery path. In R, that means no `tryCatch(..., error = function(e) NULL)`.
- [rule] Before adding a dependency, confirm in the index (PyPI, CRAN) that it exists and is the intended package. Never add one from memory, because hallucinated names get squatted.
- [rule] Name variables and functions by domain meaning, not `data`, `result`, `tmp`, `process()`, `handle()`.
- [rule] No option, parameter, or strategy hook until a caller passes it.
