---
name: r-package-dev
description: Design and develop R packages. Use this when building or refactoring R packages that need session-scoped state, user configuration, caches, startup hooks, or architecture documentation (C4). Covers when to use environments (reference semantics), how to avoid search path pollution (Imports, requireNamespace), how to persist safely (XDG-compliant locations, secrets via keyring), and how to test behavior (not internals) with testthat and snapshots for messages.
compatibility: Requires R 4.0+ for tools::R_user_dir() (use rappdirs fallback on older R). No network required. Diagram generation uses DiagrammeR if installed.
metadata:
  version: "1.0"
  source-notes: "R Packages ([[20251004T094934308143000|2e]]), loading vs attaching, persistent data, interface testing, C4 modeling, deep module development system"
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

References and examples
- Quick reference: references/REFERENCE.md
- Code samples:
  - assets/examples-state.R
  - assets/examples-persistence.R
  - assets/c4-context-diagram.R
- Cleanup script:
  - scripts/clean-user-data.R

Related vault notes
- [[R Packages Persistent Data]]
- [[R Package Loading vs Attaching System]]
- [[Interface-fokussiertes Testing in R-Paketen]]
- [[C4-Modellierung für R-Pakete]]
- [[Deep Module Development System]]
- [[R Package Testing with testthat]]
- [[R Packages (2e) - Umfassende Zusammenfassung]]

references/REFERENCE.md
---
# Reference guide — R package state and persistence

Key concepts
- Internal state (session-scoped)
  - Use a package-private environment with reference semantics.
  - Define once (e.g., R/aaa.R): the <- new.env(parent = emptyenv()).
  - Mutate via exported functions; keep internals hidden. Resets each session (“Groundhog Day”).
- Persistent user data (cross-session)
  - Use tools::R_user_dir("<pkg>", which = "data" | "config" | "cache") on R 4.0+; rappdirs fallback for older R.
  - XDG-compliant, small files, actively managed; provide cleaning utilities.
  - Sensitive data via keyring/gitcreds; require interactive user consent.
- Loading vs attaching
  - In package code: never call library(); prefer Imports + package::function().
  - Optional features: requireNamespace("pkg", quietly = TRUE) and gate with if (...) patterns.
  - Avoid require() except in examples for suggested deps.
  - Imports: load without attach; Depends: load and attach (only when strictly necessary).
- Lifecycle hooks
  - .onLoad(): non-interactive init (register S3/S4, set options).
  - .onAttach(): user-facing messages; keep lightweight.
- Testing (testthat)
  - Interface-focused tests: verify inputs/outputs, errors, warnings, side effects.
  - Use snapshots for startup messages and complex outputs (be careful with fragility).
  - Isolate FS side effects with temp dirs; clean up.
  - Coverage via covr; treat tests as executable docs.
- Deep module mindset
  - Simple stable interface; rich hidden internals; test behavior not details.

Code idioms
- Optional dep pattern
if (requireNamespace("optpkg", quietly = TRUE)) {
  res <- optpkg::fn(x)
} else {
  stop("Feature requires 'optpkg'. Please install it.")
}
- R_user_dir usage
p_cfg <- tools::R_user_dir("mypkg", which = "config")
fs::dir_create(p_cfg)
readr::write_lines("key=value", file.path(p_cfg, "config.ini"))

assets/examples-state.R
---
# Package-private environment (in R/aaa.R)
the <- new.env(parent = emptyenv())
the$favorite_letters <- letters[1:3]

#' Report favorite letters
#' @export
mfl2 <- function() {
  the$favorite_letters
}

#' Change favorite letters
#' @export
set_mfl2 <- function(l = letters[24:26]) {
  old <- the$favorite_letters
  the$favorite_letters <- l
  invisible(old)
}

# Initialization and messages (in zzz.R)
.onLoad <- function(libname, pkgname) {
  # Non-interactive setup only
  # e.g., register S3 methods, set options, prime caches (no user messages)
}

.onAttach <- function(libname, pkgname) {
  packageStartupMessage(
    "Loaded ", pkgname, " v", as.character(utils::packageVersion(pkgname)),
    "\nSee ?",
    pkgname,
    " for help."
  )
}

assets/examples-persistence.R
---
# helpers.R — persistent user data (R 4.0+)
user_dir_data <- function() tools::R_user_dir("mypkg", which = "data")
user_dir_config <- function() tools::R_user_dir("mypkg", which = "config")
user_dir_cache <- function() tools::R_user_dir("mypkg", which = "cache")

save_config <- function(key, value) {
  dir <- user_dir_config()
  if (!dir.exists(dir)) dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  path <- file.path(dir, "config.json")
  cfg <- if (file.exists(path)) jsonlite::read_json(path, simplifyVector = TRUE) else list()
  cfg[[key]] <- value
  jsonlite::write_json(cfg, path, auto_unbox = TRUE, pretty = TRUE)
  invisible(path)
}

read_config <- function(key, default = NULL) {
  path <- file.path(user_dir_config(), "config.json")
  if (!file.exists(path)) return(default)
  cfg <- jsonlite::read_json(path, simplifyVector = TRUE)
  if (!is.null(cfg[[key]])) cfg[[key]] else default
}

clear_cache <- function(confirm = interactive()) {
  dir <- user_dir_cache()
  if (!dir.exists(dir)) return(invisible(TRUE))
  if (!confirm || utils::askYesNo("Clear cache?")) {
    unlink(dir, recursive = TRUE, force = TRUE)
    dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  }
  invisible(TRUE)
}

# R < 4.0 fallback (runtime check)
user_dir_safe <- function(which = c("data", "config", "cache")) {
  which <- match.arg(which)
  if (getRversion() >= "4.0.0") {
    tools::R_user_dir("mypkg", which = which)
  } else {
    # rappdirs provides XDG-like paths
    switch(which,
      data = rappdirs::user_data_dir("mypkg"),
      config = rappdirs::user_config_dir("mypkg"),
      cache = rappdirs::user_cache_dir("mypkg")
    )
  }
}

# Secrets (do not store plain-text)
save_token <- function(service, token) {
  keyring::key_set_with_value(paste0("mypkg:", service), password = token)
}
read_token <- function(service) {
  keyring::key_get(paste0("mypkg:", service))
}

assets/c4-context-diagram.R
---
if (!requireNamespace("DiagrammeR", quietly = TRUE)) {
  stop("Install DiagrammeR to render C4-like diagrams.")
}
DiagrammeR::grViz("
  digraph {
    graph [rankdir = TB, splines = ortho]
    node [shape = box, style = filled]
    Dev   [label = 'R Developer', fillcolor = lightblue]
    Pkg   [label = 'R Package (R/, tests/, man/, data/)', fillcolor = lightgreen]
    CRAN  [label = 'CRAN/GitHub', fillcolor = lightgray]
    User  [label = 'End User', fillcolor = lemonchiffon]
    Dev -> Pkg [label = 'builds/tests/docs']
    Pkg -> CRAN [label = 'releases']
    User -> Pkg [label = 'library(), ::']
  }
")

scripts/clean-user-data.R
---
#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
pkg <- if (length(args)) args[[1]] else "mypkg"
dirs <- c("data", "config", "cache")
for (w in dirs) {
  path <- tools::R_user_dir(pkg, which = w)
  if (dir.exists(path)) {
    message("Clearing: ", path)
    unlink(path, recursive = TRUE, force = TRUE)
    dir.create(path, recursive = TRUE, showWarnings = FALSE)
  } else {
    message("Missing: ", path)
  }
}
message("Done.")
