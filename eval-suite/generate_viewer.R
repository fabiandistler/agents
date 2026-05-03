#!/usr/bin/env Rscript
# Build a self-contained HTML viewer for an eval run by embedding all
# (config, task) data into viewer.html.template at the /*__EMBEDDED_DATA__*/
# marker. Output: runs/<ts>/viewer.html.

suppressPackageStartupMessages({
  library(jsonlite)
  library(yaml)
})
invisible(suppressWarnings(Sys.setlocale("LC_ALL", "C.UTF-8")))

read_yaml_utf8 <- function(p) {
  yaml::yaml.load(paste(readLines(p, encoding = "UTF-8", warn = FALSE),
                        collapse = "\n"))
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("usage: Rscript generate_viewer.R runs/<timestamp>")
}
run_dir <- normalizePath(args[[1]], mustWork = TRUE)

script_arg <- grep("--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
root <- if (length(script_arg) >= 1L) {
  normalizePath(dirname(sub("--file=", "", script_arg[1])), mustWork = FALSE)
} else {
  normalizePath(".", mustWork = FALSE)
}

template_path <- file.path(root, "viewer.html.template")
if (!file.exists(template_path)) stop("template not found: ", template_path)
template <- paste(readLines(template_path, warn = FALSE), collapse = "\n")

`%||%` <- function(a, b) if (is.null(a) || identical(a, "")) b else a

read_text <- function(p) {
  if (!file.exists(p)) return(NULL)
  paste(readLines(p, warn = FALSE), collapse = "\n")
}
read_json_safe <- function(p) {
  if (!file.exists(p)) return(NULL)
  tryCatch(jsonlite::fromJSON(p, simplifyVector = FALSE),
           error = function(e) NULL)
}

score_path <- file.path(run_dir, "score.csv")
score <- if (file.exists(score_path)) {
  read.csv(score_path, stringsAsFactors = FALSE)
} else {
  data.frame()
}

score_for <- function(config, task) {
  if (!nrow(score)) return(list())
  r <- score[score$config == config & score$task == task, , drop = FALSE]
  if (nrow(r) != 1L) return(list())
  as.list(r[1, ])
}

configs <- list.dirs(run_dir, recursive = FALSE, full.names = FALSE)
configs <- sort(configs[configs != ""])

task_ids <- character(0)
for (cfg in configs) {
  task_ids <- union(task_ids, list.dirs(file.path(run_dir, cfg),
                                        recursive = FALSE, full.names = FALSE))
}
task_ids <- sort(task_ids[task_ids != ""])

tasks <- lapply(task_ids, function(tid) {
  yaml_path <- file.path(root, "tasks", tid, "task.yaml")
  ty <- if (file.exists(yaml_path)) read_yaml_utf8(yaml_path) else list()
  res <- list()
  for (cfg in configs) {
    sol  <- read_text(file.path(run_dir, cfg, tid, "solution.R"))
    meta <- read_json_safe(file.path(run_dir, cfg, tid, "meta.json"))
    judge <- read_json_safe(file.path(run_dir, cfg, tid, "judge.json"))
    res[[cfg]] <- list(
      solution = sol %||% "",
      meta     = meta,
      score    = score_for(cfg, tid),
      judge    = judge
    )
  }
  list(
    id = tid,
    title = ty$title %||% tid,
    prompt = ty$prompt %||% "",
    results = res
  )
})

payload <- list(
  run = basename(run_dir),
  configs = as.list(configs),
  tasks = tasks
)

json <- jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", na = "null")
marker <- "/*__EMBEDDED_DATA__*/null"
parts <- strsplit(template, marker, fixed = TRUE)[[1]]
if (length(parts) != 2L) {
  stop("could not find marker '", marker, "' in template")
}
out_html <- paste0(parts[1], json, parts[2])
out_path <- file.path(run_dir, "viewer.html")
writeLines(out_html, out_path)
message(sprintf("[viewer] -> %s", out_path))
