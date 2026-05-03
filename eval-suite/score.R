#!/usr/bin/env Rscript
# Score an eval run: for each (config, task), run lintr on solution.R and
# execute the task's tests.R against it. Writes results.csv and a markdown
# summary to runs/<ts>/results.{csv,md}, and prints the markdown to stdout.

suppressPackageStartupMessages({
  library(testthat)
  library(lintr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("usage: Rscript score.R runs/<timestamp>")
}
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

# Repo root: this script lives at <root>/score.R
script_arg <- grep("--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
root <- if (length(script_arg) >= 1L) {
  normalizePath(dirname(sub("--file=", "", script_arg[1])), mustWork = FALSE)
} else {
  normalizePath(".", mustWork = FALSE)
}

score_one <- function(config, task, sol_path, tests_path, work_setup_files) {
  out <- list(
    config = config, task = task,
    has_solution = file.exists(sol_path),
    parses = NA, n_lint = NA_integer_, n_lines = NA_integer_,
    tests_total = NA_integer_, tests_pass = NA_integer_,
    tests_fail = NA_integer_, tests_error = NA_integer_,
    test_run_error = NA_character_
  )
  if (!out$has_solution) return(out)

  out$n_lines <- length(readLines(sol_path, warn = FALSE))
  out$parses  <- tryCatch({ parse(file = sol_path); TRUE },
                          error = function(e) FALSE)

  out$n_lint <- tryCatch(
    length(lintr::lint(sol_path)),
    error = function(e) NA_integer_
  )

  # Run tests in an isolated tempdir so we can drop solution.R + setup files
  # alongside tests.R as if it was the workdir.
  tdir <- tempfile("score-"); dir.create(tdir)
  on.exit(unlink(tdir, recursive = TRUE), add = TRUE)
  file.copy(sol_path, file.path(tdir, "solution.R"))
  for (f in work_setup_files) {
    if (file.exists(f)) file.copy(f, file.path(tdir, basename(f)))
  }
  file.copy(tests_path, file.path(tdir, "tests.R"))

  # Generate the inputs setup.R produces (input.csv etc.) inside tdir
  setup_R <- file.path(dirname(tests_path), "setup.R")
  if (file.exists(setup_R)) {
    withr::with_dir(tdir, tryCatch(
      source(setup_R, local = TRUE),
      error = function(e) message("setup.R failed in scoring: ", conditionMessage(e))
    ))
  }

  res <- tryCatch(
    withr::with_dir(tdir, {
      reporter <- testthat::SilentReporter$new()
      testthat::test_file(file.path(tdir, "tests.R"),
                          reporter = reporter, stop_on_failure = FALSE)
    }),
    error = function(e) e
  )

  if (inherits(res, "error")) {
    out$test_run_error <- conditionMessage(res)
  } else {
    df <- as.data.frame(res)
    out$tests_total <- nrow(df)
    out$tests_fail  <- as.integer(sum(df$failed))
    out$tests_error <- as.integer(sum(df$error))
    out$tests_pass  <- as.integer(out$tests_total - out$tests_fail - out$tests_error)
  }
  out
}

configs <- list.dirs(run_dir, recursive = FALSE, full.names = FALSE)
configs <- configs[configs != ""]

rows <- list()
for (config in configs) {
  cdir <- file.path(run_dir, config)
  tasks <- list.dirs(cdir, recursive = FALSE, full.names = FALSE)
  for (task in tasks) {
    sol  <- file.path(cdir, task, "solution.R")
    tdir <- file.path(root, "tasks", task)
    tests <- file.path(tdir, "tests.R")
    if (!file.exists(tests)) {
      warning(sprintf("no tests.R for task '%s' — skipping", task))
      next
    }
    setup_files <- list.files(tdir, full.names = TRUE,
                              pattern = "^(target\\.R)$")
    rows[[length(rows) + 1L]] <-
      score_one(config, task, sol, tests, setup_files)
  }
}

if (length(rows) == 0L) stop("no results found in: ", run_dir)
results <- do.call(rbind, lapply(rows, as.data.frame))
results$pass_rate <- ifelse(
  is.na(results$tests_total) | results$tests_total == 0,
  NA_real_,
  results$tests_pass / results$tests_total
)
write.csv(results, file.path(run_dir, "results.csv"), row.names = FALSE)

# ----- markdown summary -----
md <- c(sprintf("# Eval results — %s\n", basename(run_dir)))

# per-task comparison
tasks <- sort(unique(results$task))
md <- c(md, "## Per-task pass rate\n")
hdr <- c("task", configs)
md <- c(md, paste0("| ", paste(hdr, collapse = " | "), " |"))
md <- c(md, paste0("|", paste(rep("---", length(hdr)), collapse = "|"), "|"))
for (t in tasks) {
  cells <- vapply(configs, function(cfg) {
    r <- results[results$task == t & results$config == cfg, ]
    if (nrow(r) == 0L) return("—")
    if (!isTRUE(r$has_solution)) return("**no file**")
    if (!is.na(r$test_run_error)) return("**test crash**")
    sprintf("%d/%d (%d lint)", r$tests_pass, r$tests_total, r$n_lint)
  }, character(1))
  md <- c(md, paste0("| ", t, " | ", paste(cells, collapse = " | "), " |"))
}

# overall
md <- c(md, "\n## Overall\n")
md <- c(md, "| config | tasks | total tests | passed | failed | errored | lint warnings |")
md <- c(md, "|---|---|---|---|---|---|---|")
for (cfg in configs) {
  r <- results[results$config == cfg, ]
  md <- c(md, sprintf("| %s | %d | %d | %d | %d | %d | %d |",
    cfg, nrow(r),
    sum(r$tests_total, na.rm = TRUE),
    sum(r$tests_pass,  na.rm = TRUE),
    sum(r$tests_fail,  na.rm = TRUE),
    sum(r$tests_error, na.rm = TRUE),
    sum(r$n_lint,      na.rm = TRUE)
  ))
}

# delta if exactly 2 configs
if (length(configs) == 2L) {
  a <- configs[1]; b <- configs[2]
  ra <- results[results$config == a, c("task", "tests_pass", "tests_total", "n_lint")]
  rb <- results[results$config == b, c("task", "tests_pass", "tests_total", "n_lint")]
  m  <- merge(ra, rb, by = "task", suffixes = paste0(".", c(a, b)))
  m$delta_passed <- m[[paste0("tests_pass.", b)]] - m[[paste0("tests_pass.", a)]]
  m$delta_lint   <- m[[paste0("n_lint.", b)]]    - m[[paste0("n_lint.", a)]]
  md <- c(md, sprintf("\n## Delta (%s − %s)\n", b, a))
  md <- c(md, "| task | Δ passed tests | Δ lint warnings |")
  md <- c(md, "|---|---|---|")
  for (i in seq_len(nrow(m))) {
    md <- c(md, sprintf("| %s | %+d | %+d |",
      m$task[i], m$delta_passed[i], m$delta_lint[i]))
  }
}

writeLines(md, file.path(run_dir, "results.md"))
writeLines(md)
