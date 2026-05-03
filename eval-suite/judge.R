#!/usr/bin/env Rscript
# LLM-as-judge: for each (config, task) in a run dir, ask claude to evaluate
# the solution against the task's expectations (from task.yaml). Writes
# runs/<ts>/<config>/<task>/judge.json.
#
# Usage:
#   Rscript judge.R runs/<ts>            # call claude for every (config, task)
#   Rscript judge.R runs/<ts> --skip     # write skipped-stub judge.json files
#
# Inputs read per (config, task):
#   - tasks/<task>/task.yaml       (prompt, expectations)
#   - runs/<ts>/<config>/<task>/solution.R
#   - runs/<ts>/score.csv          (objective test/lint anchors, optional)
#
# Output JSON schema:
#   { judge_model, judge_prompt_sha256, skipped, reason?, expectations: [
#       {text, passed, evidence}, ... ], summary: {passed, failed, total, pass_rate} }

suppressPackageStartupMessages({
  library(yaml)
  library(jsonlite)
  library(digest)
})
invisible(suppressWarnings(Sys.setlocale("LC_ALL", "C.UTF-8")))

read_yaml_utf8 <- function(p) {
  yaml::yaml.load(paste(readLines(p, encoding = "UTF-8", warn = FALSE),
                        collapse = "\n"))
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1L) {
  stop("usage: Rscript judge.R runs/<timestamp> [--skip]")
}
run_dir <- normalizePath(args[[1]], mustWork = TRUE)
skip_mode <- "--skip" %in% args[-1L]

JUDGE_MODEL <- Sys.getenv("JUDGE_MODEL", unset = "claude-sonnet-4-5")

script_arg <- grep("--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
root <- if (length(script_arg) >= 1L) {
  normalizePath(dirname(sub("--file=", "", script_arg[1])), mustWork = FALSE)
} else {
  normalizePath(".", mustWork = FALSE)
}

score_path <- file.path(run_dir, "score.csv")
score <- if (file.exists(score_path)) {
  read.csv(score_path, stringsAsFactors = FALSE)
} else {
  data.frame()
}

build_prompt <- function(task_yaml, solution_text, score_row) {
  exp_block <- paste(sprintf("%d. %s",
                             seq_along(task_yaml$expectations),
                             task_yaml$expectations),
                     collapse = "\n")

  if (nrow(score_row) == 1L) {
    parses_str <- if (is.na(score_row$parses)) "unknown" else as.character(score_row$parses)
    score_block <- sprintf(
      "- Tests passed: %s/%s\n- Lint warnings: %s\n- Parses: %s",
      ifelse(is.na(score_row$tests_pass),  "?", score_row$tests_pass),
      ifelse(is.na(score_row$tests_total), "?", score_row$tests_total),
      ifelse(is.na(score_row$n_lint),      "?", score_row$n_lint),
      parses_str
    )
  } else {
    score_block <- "- (no objective score available)"
  }

  sprintf(
'You are evaluating an R solution against a list of expectations.

# Task prompt
%s

# The R code submitted (solution.R)
```r
%s
```

# Test results (objective, do not contradict)
%s

# Expectations to evaluate
%s

For each expectation, return STRICT JSON only (no prose, no markdown fences):
{
  "expectations": [
    {"text": "...", "passed": true, "evidence": "<short quote from code or test results>"}
  ],
  "summary": {"passed": N, "failed": N, "total": N, "pass_rate": 0.X}
}

Passing requires positive evidence in the code, not absence of contradiction.',
    task_yaml$prompt,
    solution_text,
    score_block,
    exp_block
  )
}

# Strip optional ```json ... ``` fences and locate the outermost JSON object.
extract_json <- function(s) {
  s <- sub("^```(?:json)?\\s*", "", s, perl = TRUE)
  s <- sub("\\s*```\\s*$", "", s, perl = TRUE)
  start <- regexpr("\\{", s)
  end   <- regexpr("\\}[^}]*$", s, perl = TRUE)
  if (start < 0 || end < 0) return(s)
  substr(s, start, end + attr(end, "match.length") - 1L)
}

call_claude <- function(prompt, model) {
  tmp_in <- tempfile("judge-prompt-", fileext = ".txt")
  on.exit(unlink(tmp_in), add = TRUE)
  writeLines(prompt, tmp_in)

  raw <- tryCatch(
    system2("claude",
            args = c("-p", "--output-format", "json", "--model", model),
            stdin = tmp_in, stdout = TRUE, stderr = TRUE),
    error = function(e) e
  )
  if (inherits(raw, "error")) {
    return(list(ok = FALSE, error = conditionMessage(raw), raw = NULL))
  }
  status <- attr(raw, "status")
  raw_text <- paste(raw, collapse = "\n")
  if (!is.null(status) && status != 0) {
    return(list(ok = FALSE,
                error = sprintf("claude exited %d: %s", status, raw_text),
                raw = raw_text))
  }

  outer <- tryCatch(jsonlite::fromJSON(raw_text, simplifyVector = FALSE),
                    error = function(e) e)
  if (inherits(outer, "error")) {
    return(list(ok = FALSE,
                error = paste("could not parse claude wrapper JSON:",
                              conditionMessage(outer)),
                raw = raw_text))
  }
  inner_text <- outer$result %||% outer$content %||% ""
  if (!nzchar(inner_text)) {
    return(list(ok = FALSE,
                error = "no result text in claude response",
                raw = raw_text))
  }

  inner_json <- extract_json(inner_text)
  parsed <- tryCatch(jsonlite::fromJSON(inner_json, simplifyVector = FALSE),
                     error = function(e) e)
  if (inherits(parsed, "error")) {
    return(list(ok = FALSE,
                error = paste("could not parse inner judge JSON:",
                              conditionMessage(parsed)),
                raw = inner_text))
  }
  list(ok = TRUE, parsed = parsed)
}

`%||%` <- function(a, b) if (is.null(a) || identical(a, "")) b else a

write_judge <- function(out_path, payload) {
  jsonlite::write_json(payload, out_path,
                       auto_unbox = TRUE, pretty = TRUE, null = "null")
}

configs <- list.dirs(run_dir, recursive = FALSE, full.names = FALSE)
configs <- configs[configs != ""]

for (config in configs) {
  cdir <- file.path(run_dir, config)
  tasks <- list.dirs(cdir, recursive = FALSE, full.names = FALSE)
  for (task in tasks) {
    out_dir <- file.path(cdir, task)
    judge_path <- file.path(out_dir, "judge.json")
    sol_path   <- file.path(out_dir, "solution.R")
    yaml_path  <- file.path(root, "tasks", task, "task.yaml")

    if (!file.exists(yaml_path)) {
      warning(sprintf("no task.yaml for '%s' — skipping judge", task))
      next
    }
    task_yaml <- read_yaml_utf8(yaml_path)
    expectations <- task_yaml$expectations %||% list()

    if (skip_mode || !file.exists(sol_path)) {
      reason <- if (skip_mode) "skip flag" else "no solution.R produced"
      write_judge(judge_path, list(
        judge_model = JUDGE_MODEL,
        skipped = TRUE,
        reason = reason,
        expectations = lapply(expectations, function(e)
          list(text = e, passed = NA, evidence = NA_character_)),
        summary = list(passed = 0, failed = 0,
                       total = length(expectations), pass_rate = NA_real_)
      ))
      next
    }

    solution_text <- paste(readLines(sol_path, warn = FALSE), collapse = "\n")
    score_row <- score[score$config == config & score$task == task, , drop = FALSE]
    prompt <- build_prompt(task_yaml, solution_text, score_row)
    prompt_sha <- digest::digest(prompt, algo = "sha256", serialize = FALSE)

    message(sprintf("[judge] %s / %s", config, task))
    res <- call_claude(prompt, JUDGE_MODEL)

    if (!res$ok) {
      write_judge(judge_path, list(
        judge_model = JUDGE_MODEL,
        judge_prompt_sha256 = prompt_sha,
        skipped = TRUE,
        reason = paste("judge call failed:", res$error),
        expectations = lapply(expectations, function(e)
          list(text = e, passed = NA, evidence = NA_character_)),
        summary = list(passed = 0, failed = 0,
                       total = length(expectations), pass_rate = NA_real_)
      ))
      next
    }

    parsed_exp <- res$parsed$expectations %||% list()
    parsed_sum <- res$parsed$summary %||% list()
    write_judge(judge_path, list(
      judge_model = JUDGE_MODEL,
      judge_prompt_sha256 = prompt_sha,
      skipped = FALSE,
      expectations = parsed_exp,
      summary = parsed_sum
    ))
  }
}

message(sprintf("[judge] done -> %s/<config>/<task>/judge.json", run_dir))
