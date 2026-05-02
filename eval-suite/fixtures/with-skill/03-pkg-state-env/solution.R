.state <- new.env(parent = emptyenv())

set_state <- function(key, value) {
  assign(key, value, envir = .state)
  invisible(value)
}

get_state <- function(key, default = NULL) {
  if (exists(key, envir = .state, inherits = FALSE)) {
    get(key, envir = .state, inherits = FALSE)
  } else {
    default
  }
}

clear_state <- function() {
  rm(list = ls(envir = .state, all.names = TRUE), envir = .state)
  invisible(NULL)
}
