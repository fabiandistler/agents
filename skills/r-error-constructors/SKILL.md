---
name: r-error-constructors
category: r-development
environments: coding
description: Design custom condition/error constructors for R packages the tidyverse/rlang way — standardized functions that turn a recurring `stop()` call into a testable, documentable, and inheritable error type. Use this whenever an R package raises the same error at three or more call sites, whenever tests assert on error message text with a regex, or when a user asks about `rlang::abort()`, custom conditions, `conditionMessage()` methods, or building an error-class hierarchy in R.
compatibility: R packages using rlang for condition signaling and testthat for testing; assumes tidyverse-style package conventions (roxygen2 `@export`, `NAMESPACE`-managed S3 methods).
metadata:
  version: "1.0"
---

# R Error Constructors

An error constructor is a small function that wraps `rlang::abort()` to produce
a standardized, named, structured condition instead of an ad-hoc `stop()` call.
The goal is not to gold-plate every error path — it is to stop duplicating the
same error text across the codebase and to make tests assert on *what kind of
error happened* instead of *what string it printed*.

## When to build one — the Rule of Three

Do not create a constructor the first time an error appears. Wait until the
same error is generated at three or more call sites. Before that point the
overhead of a named class, a `conditionMessage()` method, and dedicated tests
outweighs the benefit of a plain `stop()` or `rlang::abort()` call. The
constructor pays for itself only once duplication is real.

| Repetitions of the same error | Action |
|---|---|
| 1–2 | Use `rlang::abort()` (or `stop()`) inline; no constructor yet. |
| 3+ | Extract a `stop_{error_type}()` constructor. |

## Naming conventions

Consistent naming is what makes constructors predictable across a package and
across `tryCatch()` handlers written by callers who never read the source.

- **Function name**: `stop_{error_type}()` — e.g. `stop_not_found()`.
- **Error class**: `{package}_error_{error_type}` — e.g. `my_package_error_not_found`.

## Basic constructor

```r
stop_not_found <- function(path) {
  rlang::abort(
    class = "my_package_error_not_found",
    path = path
  )
}
```

(`class` superseded the older `.subclass` argument name; `.subclass` is
deprecated in current rlang.)

`rlang::abort()` with `class` produces a condition object that is:

- **Classed** — precise `tryCatch()` dispatch instead of matching on message text.
- **Structured** — arbitrary attributes (`path`, in the example) are attached to
  the condition and can be inspected programmatically.
- **Inheriting** — the condition still descends from R's own
  `condition` → `error` → `rlang_error` hierarchy, so generic handlers keep
  working.

This is the core reason to prefer `rlang::abort()` over base `stop()`: `stop()`
is string-based and unstructured, while `abort()` is object-based, typed, and
hierarchical.

## Separate structure from presentation with `conditionMessage()`

Do not hand-format the message inside the constructor. Store the structured
data on the condition, and let an exported `conditionMessage()` S3 method
render it:

```r
#' @export
conditionMessage.my_package_error_not_found <- function(c) {
  glue::glue_data(c, "'{path}' not found")
}

stop_not_found("a.csv")
#> Error: 'a.csv' not found
```

Two things matter here:

1. The method **must be exported** (`@export`) — it is dispatched on the
   external `conditionMessage()` generic, so without exporting it the custom
   message will not be found by callers.
2. `glue::glue_data()` is the common tool for building the message from the
   condition's own fields.

This split is the whole point of the pattern: the *condition* (class +
attributes) is what tests and `tryCatch()` handlers key on and what stays
stable; the *message* (what a human reads) can be reworded freely without
breaking anything that depends on the condition's structure.

## Building an error hierarchy

For related error types, thread a `class` parameter through the constructor so
specialized constructors can extend the base one instead of duplicating it:

```r
stop_not_found <- function(path, ..., class = character()) {
  rlang::abort(
    class = c(class, "my_package_error_not_found"),
    path = path,
    ...
  )
}

stop_file_not_found <- function(path) {
  stop_not_found(path, class = "my_package_error_file_not_found")
}
```

Resulting class chain (most specific first):

```
condition
└── error
    └── rlang_error
        └── my_package_error_not_found
            └── my_package_error_file_not_found
```

This buys two things:

- **Code reuse** — shared logic and shared attributes live once, in the base
  constructor.
- **Differentiated handling** — callers choose their precision:

```r
# Catch every "not found" error, regardless of specific type
tryCatch(
  ...,
  my_package_error_not_found = function(e) { ... }
)

# Or discriminate by specific subtype, with a fallback
tryCatch(
  ...,
  my_package_error_file_not_found = function(e) { ... },
  my_package_error_not_found      = function(e) { ... }
)
```

Only build a hierarchy when there is a genuine family of related errors to
model. A single constructor with no `class` parameter is the right default.

## Testing strategy: two kinds of test, not one

Robust testing separates **constructor tests** (does the error look right?)
from **usage tests** (does calling code raise the right error?). Conflating
them tends to produce fragile, string-matching tests. (For the general
testthat/fixture/snapshot strategy beyond error conditions, see the
r-package-dev skill; this section covers only error-condition testing.)

### Constructor tests — regression via snapshot tests

Use a testthat 3e snapshot test to record the printed error. These tests are
independent of the message text changing on purpose — they just document what
the current output looks like and flag unintended drift:

```r
testthat::expect_snapshot(
  stop_not_found("missing-file.txt"),
  error = TRUE
)
```

(Snapshot tests superseded `testthat::verify_output()`; use
`expect_snapshot(..., error = TRUE)` in testthat 3e code.)

### Usage tests — assert on class, not on message text

| Approach | Example | Verdict |
|---|---|---|
| Regex on message (old) | `expect_error(read_lines("missing-file.txt"), "not found")` | Fragile — breaks the moment the message is reworded. |
| Class-based (preferred) | `expect_error(read_lines("missing-file.txt"), class = "my_package_error_not_found")` | Robust — tests the error *type*, survives message rewording. |

When a test needs to check specific error attributes rather than just its
class, capture the condition object and assert on its fields directly:

```r
error <- expect_error(
  read_lines("missing-file.txt"),
  class = "my_package_error_not_found"
)
expect_equal(error$path, "missing-file.txt")
```

### Why the split matters

- Message wording can be refactored freely without breaking usage tests.
- Usage tests stay precise about error *logic*, not phrasing.
- Snapshot tests give a durable, reviewable record of what users see.
- Overall test suite becomes robust against copy-editing the error text.

## Decision checklist

Work through this before adding a constructor to a package:

1. **Has this exact error occurred at 3+ call sites?** If no, keep the inline
   `rlang::abort()` / `stop()` call.
2. **Name it**: function `stop_{error_type}`, class `{package}_error_{error_type}`.
3. **Attach structured data** as named arguments to `rlang::abort()` — whatever
   a caller or a test would need to inspect (e.g. `path`).
4. **Write and export a `conditionMessage()` method** that renders the message
   from those attributes via `glue::glue_data()`.
5. **Decide if a hierarchy is needed.** Only add the `class` passthrough
   parameter if there is a real family of specialized errors to build; do not
   add it speculatively.
6. **Write both kinds of test**: an `expect_snapshot(..., error = TRUE)`
   regression test for the constructor itself, and
   `expect_error(..., class = ...)` usage tests wherever the error is
   triggered.
7. **Document the throw** in the calling function's `@section Throws:` if the
   package documents error contracts.
