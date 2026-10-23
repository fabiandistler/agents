---
title: Coding standards
targets: all
---

## Coding standards

- All text in code, comments, and README files should be in English.
- Before writing a helper, or accepting one in review, search the codebase (`git grep`) for one with the same behaviour. Duplicate-code checks miss the same logic written differently.
- Do not catch broad exceptions or return a default (`None`, `NULL`, `NA`, `{}`) just to make code run. Let the error surface unless there is a real recovery path. In R, that means no `tryCatch(..., error = function(e) NULL)`.
- Never put record values into error or log messages (salaries, names, person IDs, free-text fields). Name the field and the expected type or range instead.
- Either raise an error (`stop()`, `raise`) or log it, never both. The top-level handler logs it once.
- Before adding a dependency or component library, check the standard library, a native platform feature (`<input type="date">`, a CSS rule, a DB constraint), and an already-installed dependency, in that order. Add a new one only if none covers the task, and confirm in the index (PyPI, CRAN) that it exists and is the intended package; never add one from memory, because hallucinated names get squatted.
- Name variables and functions by domain meaning, not `data`, `result`, `tmp`, `process()`, `handle()`.
- No option, parameter, or strategy hook until a caller passes it.
- External or user input enters a template only as a variable, never as template source: no `Template(user_input)`, no `env.from_string(user_input)`. Rendering untrusted text as a template is code execution, and a sandboxed environment is not a defense (CVE-2026-90970).
