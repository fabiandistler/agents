# helpers.R — persistent user data (R 4.0+)
user_dir_data <- function() tools::R_user_dir("mypkg", which = "data")
user_dir_config <- function() tools::R_user_dir("mypkg", which = "config")
user_dir_cache <- function() tools::R_user_dir("mypkg", which = "cache")

save_config <- function(key, value) {
    dir <- user_dir_config()
    if (!dir.exists(dir)) {
        dir.create(dir, recursive = TRUE, showWarnings = FALSE)
    }
    path <- file.path(dir, "config.json")
    cfg <- if (file.exists(path)) {
        jsonlite::read_json(path, simplifyVector = TRUE)
    } else {
        list()
    }
    cfg[[key]] <- value
    jsonlite::write_json(cfg, path, auto_unbox = TRUE, pretty = TRUE)
    invisible(path)
}

read_config <- function(key, default = NULL) {
    path <- file.path(user_dir_config(), "config.json")
    if (!file.exists(path)) {
        return(default)
    }
    cfg <- jsonlite::read_json(path, simplifyVector = TRUE)
    if (!is.null(cfg[[key]])) cfg[[key]] else default
}

clear_cache <- function(confirm = interactive()) {
    dir <- user_dir_cache()
    if (!dir.exists(dir)) {
        return(invisible(TRUE))
    }
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
        switch(
            which,
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
