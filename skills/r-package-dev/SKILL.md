---
name: r-package-dev
description: Design and develop R packages. Use this when building or refactoring R packages.
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

Example
See assets/examples-state.R

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
- Path helpers and read/write helpers: assets/examples-persistence.R
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

Testing strategy (interface-focused)
- Test exported interfaces and observable behavior (returns, errors, warnings, side effects).
- Use testthat (3rd edition), Arrange–Act–Assert structure, deterministic tests with set.seed() if needed.
- Snapshot startup messages and complex outputs; be mindful of fragility.
- Use withr/local_tempdir() and fs helpers to isolate filesystem effects; clean up after tests.
- Skip conditions for environment-specific tests (skip_on_cran(), skip_if_not_installed()).
- Coverage with covr; treat tests as executable documentation.

Architecture sketch (C4-lite, optional)
- Context/Container-level diagrams help communicate boundaries: R code (R/), docs (man/), tests (tests/), data (data/).
- Generate simple diagrams with DiagrammeR for reproducible docs.
- See assets/c4-context-diagram.R for a tiny example.

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
  - assets/examples-state.R
  - assets/examples-persistence.R
  - assets/c4-context-diagram.R
- Cleanup script:
  - scripts/clean-user-data.R
