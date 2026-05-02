Write `solution.R` containing the scaffold for a package-private state
environment, suitable to live in an R package's `R/aaa.R`.

Define:
  - an internal environment `.state` whose parent is `emptyenv()`
  - `set_state(key, value)` — stores a value under `key`
  - `get_state(key, default = NULL)` — returns the value, or `default` if missing
  - `clear_state()` — removes everything from the env, returns invisibly

Requirements:
  - Follow tidyverse / CRAN package conventions for package-private state.
  - Do **not** call `library()` or `require()` anywhere.
  - Do **not** use `<<-` or `assign(..., envir = globalenv())`.
  - Do **not** use `options()` for the state.
  - The state must survive across calls within an R session but not leak to
    the global environment.
  - `clear_state()` must return `invisible(NULL)` (or invisibly empty).

Only write `solution.R`. Do not run code.
