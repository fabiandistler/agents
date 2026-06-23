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
