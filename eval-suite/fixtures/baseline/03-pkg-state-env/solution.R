# baseline fixture: uses library() and <<- (violates package conventions)
library(methods)

.state <- new.env()  # parent defaults to globalenv() — wrong

set_state <- function(key, value) {
  .state[[key]] <<- value
  invisible(value)
}

get_state <- function(key, default = NULL) {
  if (is.null(.state[[key]])) default else .state[[key]]
}

clear_state <- function() {
  rm(list = ls(.state), envir = .state)
}
