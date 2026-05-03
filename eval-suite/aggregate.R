#!/usr/bin/env Rscript
# Aggregate a scored+judged run into final results.
#
# Reads:
#   runs/<ts>/score.csv
#   runs/<ts>/<config>/<task>/judge.json
#
# Writes:
#   runs/<ts>/results.csv  (score columns + judge_pass/judge_total/judge_pass_rate)
#   runs/<ts>/results.md   (per-task, overall, delta tables)

suppressPackageStartupMessages({
  library(jsonlite)
})

`%||%` <- function(a, b) if (is.null(a) || identical(a, "")) b else a

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("usage: Rscript aggregate.R runs/<timestamp>")
}
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

score_path <- file.path(run_dir, "score.csv")
if (!file.exists(score_path)) {
  stop("score.csv not found in: ", run_dir, " (run score.R first)")
}
results <- read.csv(score_path, stringsAsFactors = FALSE)

# Pull judge.json values for each (config, task) row.
results$judge_pass     <- NA_integer_
results$judge_total    <- NA_integer_
results$judge_pass_rate <- NA_real_
results$judge_skipped  <- NA
results$judge_model    <- NA_character_

for (i in seq_len(nrow(results))) {
  jp <- file.path(run_dir, results$config[i], results$task[i], "judge.json")
  if (!file.exists(jp)) next
  j <- tryCatch(jsonlite::fromJSON(jp, simplifyVector = FALSE),
                error = function(e) NULL)
  if (is.null(j)) next
  results$judge_skipped[i] <- isTRUE(j$skipped)
  results$judge_model[i]   <- j$judge_model %||% NA_character_
  if (isTRUE(j$skipped)) next
  s <- j$summary
  if (!is.null(s)) {
    results$judge_pass[i]      <- as.integer(s$passed %||% NA)
    results$judge_total[i]     <- as.integer(s$total  %||% NA)
    if (!is.na(results$judge_total[i]) && results$judge_total[i] > 0) {
      results$judge_pass_rate[i] <- results$judge_pass[i] / results$judge_total[i]
    }
  }
}

write.csv(results, file.path(run_dir, "results.csv"), row.names = FALSE)

# ----- markdown summary -----
configs <- sort(unique(results$config))
tasks   <- sort(unique(results$task))

md <- c(sprintf("# Eval results — %s\n", basename(run_dir)))

# per-task per-config: tests + lint + judge
md <- c(md, "## Per-task results\n")
hdr <- c("task", configs)
md <- c(md, paste0("| ", paste(hdr, collapse = " | "), " |"))
md <- c(md, paste0("|", paste(rep("---", length(hdr)), collapse = "|"), "|"))
for (t in tasks) {
  cells <- vapply(configs, function(cfg) {
    r <- results[results$task == t & results$config == cfg, ]
    if (nrow(r) == 0L) return("—")
    if (!isTRUE(r$has_solution)) return("**no file**")
    if (!is.na(r$test_run_error)) return("**test crash**")
    judge_cell <- if (isTRUE(r$judge_skipped) || is.na(r$judge_total)) {
      "judge: —"
    } else {
      sprintf("judge: %d/%d", r$judge_pass, r$judge_total)
    }
    sprintf("%d/%d tests · %d lint · %s",
            r$tests_pass, r$tests_total, r$n_lint, judge_cell)
  }, character(1))
  md <- c(md, paste0("| ", t, " | ", paste(cells, collapse = " | "), " |"))
}

# overall
md <- c(md, "\n## Overall\n")
md <- c(md, "| config | tasks | tests passed | tests total | lint | judge passed | judge total |")
md <- c(md, "|---|---|---|---|---|---|---|")
for (cfg in configs) {
  r <- results[results$config == cfg, ]
  graded <- r[!is.na(r$judge_skipped) & r$judge_skipped == FALSE, ]
  any_judged <- nrow(graded) > 0
  jp <- if (any_judged) sum(graded$judge_pass,  na.rm = TRUE) else NA_integer_
  jt <- if (any_judged) sum(graded$judge_total, na.rm = TRUE) else NA_integer_
  md <- c(md, sprintf("| %s | %d | %d | %d | %d | %s | %s |",
    cfg, nrow(r),
    sum(r$tests_pass,  na.rm = TRUE),
    sum(r$tests_total, na.rm = TRUE),
    sum(r$n_lint,      na.rm = TRUE),
    if (any_judged) as.character(jp) else "—",
    if (any_judged) as.character(jt) else "—"
  ))
}

# delta if exactly 2 configs (b - a, where a is the alphabetically first config)
if (length(configs) == 2L) {
  a <- configs[1]; b <- configs[2]
  cols <- c("task", "tests_pass", "tests_total", "n_lint", "judge_pass", "judge_total")
  ra <- results[results$config == a, cols]
  rb <- results[results$config == b, cols]
  m  <- merge(ra, rb, by = "task", suffixes = paste0(".", c(a, b)))
  m$delta_passed <- m[[paste0("tests_pass.", b)]] - m[[paste0("tests_pass.", a)]]
  m$delta_lint   <- m[[paste0("n_lint.",      b)]] - m[[paste0("n_lint.",      a)]]
  m$delta_judge  <- m[[paste0("judge_pass.",  b)]] - m[[paste0("judge_pass.",  a)]]
  md <- c(md, sprintf("\n## Delta (%s − %s)\n", b, a))
  md <- c(md, "| task | Δ passed tests | Δ lint warnings | Δ judge passed |")
  md <- c(md, "|---|---|---|---|")
  for (i in seq_len(nrow(m))) {
    dj <- m$delta_judge[i]
    md <- c(md, sprintf("| %s | %+d | %+d | %s |",
      m$task[i], m$delta_passed[i], m$delta_lint[i],
      if (is.na(dj)) "—" else sprintf("%+d", dj)))
  }
}

writeLines(md, file.path(run_dir, "results.md"))
writeLines(md)
