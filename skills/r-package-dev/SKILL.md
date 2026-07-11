---
name: r-package-dev
category: r-development
environments: coding
description: Design and develop R packages. Use this when building or refactoring R packages, including package-private state and persistence, loading/attaching behavior, lifecycle staging and deprecation, interface-focused testing with reliable fixtures, and the single-function development workflow from interface design to docs.
compatibility: Requires R 4.0+ for tools::R_user_dir() (use rappdirs fallback on older R). No network required. Diagram generation uses DiagrammeR if installed.
metadata:
  version: "1.0"
---

Purpose
- Help agents implement safe and testable package-level state and persistence in R, aligned with tidyverse/CRAN practices.
- Minimize cognitive load and environmental side effects by using deep modules (simple interface, rich internals), stable interfaces, and predictable loading behavior.

Quick decision tree
1) Do you need data across R sessions?
- No → Use a package-private environment (session-scoped state).
- Yes → Use tools::R_user_dir("<pkg>", which = "data" | "config" | "cache").
2) Are data sensitive (tokens/credentials)?
- Yes → Use OS-native secrets via keyring/gitcreds; require interactive consent.
3) Will you modify the user’s search path?
- In package code: Never. Prefer Imports + package::fn and requireNamespace().
- In user scripts: library(yourpkg) is fine (user choice).
4) Will you show user-facing messages?
- Use .onAttach() for startup messages; .onLoad() for non-interactive init.

Core principles (from the notes)
- Environments for internal state have reference semantics and reset each session (“Groundhog Day”); define once, mutate safely.
- Persist only when truly necessary; manage small, XDG-compliant files via tools::R_user_dir().
- Never call library() in package code; avoid search path pollution. Prefer Imports and namespace qualification.
- Test interfaces and behavior, not internals. Use testthat with clear Arrange–Act–Assert and snapshots for messages.
- Favor deep modules: maximize internal functionality while keeping user-facing surface minimal and stable.
- Document architecture with lightweight C4 diagrams when helpful.

Workflow A — Session-scoped state (package-private environment)
1) Define a top-level environment
- Name: the (ergonomic), parent = emptyenv(), placed before first use (often R/aaa.R).
2) Expose behavior via public functions; keep internals hidden.
3) Initialize non-interactively in .onLoad(); show messages (if any) in .onAttach().
   Top-level assignment (as in the example) is fine for build-time constants;
   values that must be computed fresh each session belong in .onLoad().

Example
See assets/example-state.R

Key do’s/don’ts
- Do: the <- new.env(parent = emptyenv()); use the$… for state.
- Do: keep the env unexported; mutate via dedicated functions.
- Don’t: rely on build-time values that must change at runtime.
- Don’t: use options() for mutable shared state unless it’s explicitly user-facing configuration.

Workflow B — Persistent user data (CRAN-compliant)
1) Choose the correct scope
- data: end-user data saved by the package
- config: user/package configuration
- cache: recomputable artifacts
2) Use tools::R_user_dir("<pkg>", which = "...") on R 4.0+; use rappdirs as fallback for older R.
3) For secrets/tokens
- Use keyring/gitcreds/credentials; require interactive consent; don’t write secrets to disk in plain text.
4) Actively manage storage
- Provide list/read/write/clear helpers; keep files small; document what’s stored and how to clean it.

Examples
- Path helpers and read/write helpers: assets/example-persistence.R
- Cleanup utility: scripts/clean-user-data.R

Loading vs attaching (correct usage)
- library(pkg): loads and attaches; never use in package code.
- requireNamespace("pkg", quietly = TRUE): loads without attaching; returns TRUE/FALSE; ideal for optional/suggested deps.
- require(): like library() but returns logical; generally avoid.
- loadNamespace(): low-level; rarely needed directly.

Imports vs Depends
- Prefer Imports: dependency is loaded, not attached; always qualify calls (dep::fn()).
- Depends: only when your package is a true extension tightly bound to the dependency.

Package lifecycle hooks
- .onLoad(): non-interactive initialization, register dynamic methods, set package options, prepare internal state.
- .onAttach(): user-facing startup messages, conflict notices.

API lifecycle stages and deprecation (distinct from the load/attach hooks above — this is about the maturity stage of a function, argument, or package over time)
- Stages and typical path: Experimental → Stable → Deprecated or Superseded.
  - Experimental: early, unstable API; maintainer may change it quickly; implicit for any 0.x.x package.
  - Stable: the default stage; breaking changes should be rare and gradual, with time to adapt.
  - Deprecated: still works but warns; alternative is pointed to; removed after a suitable version/time window.
  - Superseded: a softer deprecated — functionality is kept working ("time capsule") with only critical bugfixes, no active development (e.g. tidyr::spread() superseded by pivot_wider()); use this when too much existing code depends on it to justify removal.
- Lifecycle badges (usethis::use_lifecycle() sets up SVG badges in man/figures/); only add a badge when a component's stage differs from its parent's (stable packages usually need none; a function only needs one if it diverges from the package's stage; an argument only needs one if it diverges from its function's). In roxygen: #' `r lifecycle::badge("experimental")` for a function description, #' @param old_arg `r lifecycle::badge("deprecated")` Use new_arg instead. for an argument.
- Deprecation warning functions — pick based on who should see the warning:
  - deprecate_warn(): always warns on use (throttled to roughly once per 8 hours per session; pass always = TRUE for the final deprecation phase before removal).
  - deprecate_soft(): warns only when the end user calls the deprecated function directly; stays silent when another package calls it indirectly, so users aren't warned about choices made deep in a dependency chain.
  ```r
  plus3 <- function(x, y, z) {
    lifecycle::deprecate_warn("1.0.0", "plus3()", "add3()")
    add3(x, y, z)
  }
  ```
- Argument deprecation pattern: default the argument to lifecycle::deprecated(), check with lifecycle::is_present(), warn, then fall back to the old value for backward compatibility during the transition.
- Communicate the what/since-when/alternative/how-to-migrate for every deprecation; timeline (e.g. deprecate in a minor version, remove at the next major) should scale with user base size and how costly the change is to adopt, not follow a rigid schedule.

Testing strategy (interface-focused)
- Test exported interfaces and observable behavior (returns, errors, warnings, side effects).
- Use testthat (3rd edition), Arrange–Act–Assert structure, deterministic tests with set.seed() if needed.
- Snapshot startup messages and complex outputs; be mindful of fragility.
- Use withr/local_tempdir() and fs helpers to isolate filesystem effects; clean up after tests.
- Skip conditions for environment-specific tests (skip_on_cran(), skip_if_not_installed()).
- Coverage with covr; treat tests as executable documentation.

Test fixtures and snapshot decisions
- Capture expected results with dput() during development, save to a fixture file, and reload with dget() in the test; dput()/dget() round-trip a full R object (attributes, classes, factor levels) as readable, diffable source, so fixture changes show up as clear code review diffs.
  - dput(test_result) once, copy/save the output to tests/testthat/testfiles/<name>.R
  - expected <- dget("tests/testthat/testfiles/<name>.R"); expect_identical(result, expected)
  - Prefer this over hand-built expected objects for nested lists, data.table objects, or anything with attributes that are easy to miss by hand.
- Snapshot-test decision guide — use expect_snapshot() when all three hold, skip it otherwise:
  1) The output is stable and deterministic (no timestamps, random IDs, or system-specific paths).
  2) Changes to the output should be surfaced for explicit human review (error/warning messages, print methods, formatted reports).
  3) Manually writing the expected value would cost more upkeep than reviewing snapshot diffs.
  - A snapshot failure only shows that something changed, not what or why — keep snapshots narrow (one message or object per snapshot) so the diff stays readable.
- Test value over coverage: a test earns its keep by documenting intended behavior, catching a realistic failure mode, or unblocking safe refactoring — not by moving a coverage percentage. Prioritize exported functions, then internal functions with complex logic, then known error-prone edge cases; trivial getters/setters, pure delegation, and generated code can stay untested.

Architecture sketch (C4-lite, optional)
- Context/Container-level diagrams help communicate boundaries: R code (R/), docs (man/), tests (tests/), data (data/).
- Generate simple diagrams with DiagrammeR for reproducible docs.
- See assets/c4-context-diagram.R for a tiny example.

Workflow C — Single-function development cycle
1) Problem and interface design
- Clarify the core problem and the 80/20 use case: what inputs are needed, what output is expected.
- Design the interface first — parameters, types, sensible defaults — before writing the body.
2) Implementation: make it work, then clear, then fast
- Make it work: implement the core logic against the interface from step 1.
- Make it clear: refactor for readability; prefer vectorized/functional style over explicit loops.
- Make it fast: optimize for the 80/20 case only after correctness and clarity are settled (e.g. vectorization, data.table for internals).
3) Interface-focused tests
- Write tests against the public interface and observable behavior, not internal helpers (see Testing strategy above); this is what keeps tests stable across refactors.
4) Validation
- Measure performance for the 80/20 case with microbenchmark or profile with profvis; confirm the function's benefits (functionality, speed) outweigh its interface cost.
- Sanity-check that a caller can reason about the function's behavior from its interface alone, without needing the internals.
5) Docs and review
- Document with roxygen2 (purpose, params, return value, @examples); code-review the result for design, complexity, and documentation quality.
- Note any non-obvious design trade-offs (e.g. why a particular internal implementation was chosen).

Checklists
- State (env)
  - the <- new.env(parent = emptyenv()) defined early (R/aaa.R)
  - No library() in R/; only namespace-qualified calls
  - Getter/setter functions encapsulate mutation
- Persistence
  - Uses tools::R_user_dir() (rappdirs fallback)
  - Files are small, documented, and user-cleanable
  - Secrets via keyring/gitcreds; interactive consent required
- Hooks
  - .onLoad() does non-interactive setup only
  - .onAttach() for messages; avoid heavy work
- Tests
  - Interface-focused; stable across refactors
  - File-system effects isolated and cleaned
  - Startup messages snapshot-tested (optional)
  - Complex expected objects captured with dput()/dget(), not hand-built
  - Snapshot use passes the decision guide (stable, reviewable, cheaper than manual expectations)
- Lifecycle
  - Stage (Experimental/Stable/Deprecated/Superseded) is intentional, not accidental
  - Badges added only where a component's stage diverges from its parent's
  - Deprecated functions/arguments warn via deprecate_warn() or deprecate_soft() and point to an alternative
- Docs
  - roxygen docs with examples
  - Optional C4 diagram to explain boundaries

Common edge cases
- Older R (< 4.0): use rappdirs; document paths differ.
- OS differences (Windows/macOS/Linux) for XDG paths and line endings in snapshots.
- Concurrency: avoid simultaneous writes; keep caches simple or use file-level locks if needed.
- CRAN checks: don’t write outside allowed dirs; clean up after examples/tests.
- Avoid require() in examples except for suggested packages gating example code.

References and scripts
- Code samples:
  - assets/example-state.R
  - assets/example-persistence.R
  - assets/c4-context-diagram.R
- Cleanup script:
  - scripts/clean-user-data.R
