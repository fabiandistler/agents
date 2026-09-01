#!/usr/bin/env Rscript
# One-shot script: fetch vitals ARE tasks and create task directories.
# Source: https://github.com/tidyverse/vitals/tree/main/data-raw
#
# Usage:
#   Rscript import_vitals.R
#
# Creates tasks/<slug>/ for each of the 31 ARE tasks if not already present.
# Each directory contains a task.yaml with prompt + target (no tests.R).

suppressPackageStartupMessages(library(jsonlite))

ARE_URL <- "https://raw.githubusercontent.com/tidyverse/vitals/main/data-raw/are.json"

script_arg <- grep("--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
root <- if (length(script_arg) >= 1L) {
  normalizePath(dirname(sub("--file=", "", script_arg[1])), mustWork = FALSE)
} else {
  normalizePath(".", mustWork = FALSE)
}
tasks_dir <- file.path(root, "tasks")

message(sprintf("[import_vitals] fetching %s", ARE_URL))
are <- jsonlite::fromJSON(ARE_URL, simplifyDataFrame = TRUE)
message(sprintf("[import_vitals] found %d tasks", nrow(are)))

created <- 0L
skipped <- 0L

for (i in seq_len(nrow(are))) {
  row <- are[i, ]
  slug <- row$title
  task_dir <- file.path(tasks_dir, slug)

  if (dir.exists(task_dir)) {
    skipped <- skipped + 1L
    next
  }
  dir.create(task_dir)

  knowledge <- row$knowledge
  if (is.list(knowledge)) knowledge <- unlist(knowledge)
  knowledge_str <- paste(knowledge, collapse = " ")

  prompt_text <- paste0(
    trimws(row$input),
    "\n\nWrite your solution as valid R code to `solution.R`."
  )

  yaml_lines <- c(
    sprintf("id: %s", slug),
    sprintf("title: '%s'", gsub("'", "''", slug)),
    "prompt: |",
    paste0("  ", strsplit(prompt_text, "\n")[[1]]),
    "target: |",
    paste0("  ", strsplit(trimws(row$target), "\n")[[1]]),
    sprintf("domain: %s", row$domain),
    sprintf("task_type: %s", row$task),
    sprintf("source: %s", if (is.na(row$source) || row$source == "NA") "~" else row$source),
    sprintf("knowledge: %s", knowledge_str)
  )

  writeLines(yaml_lines, file.path(task_dir, "task.yaml"))
  created <- created + 1L
}

message(sprintf(
  "[import_vitals] done: %d created, %d skipped (already existed)",
  created, skipped
))
