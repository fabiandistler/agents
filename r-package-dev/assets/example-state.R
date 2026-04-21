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
        "Loaded ",
        pkgname,
        " v",
        as.character(utils::packageVersion(pkgname)),
        "\nSee ?",
        pkgname,
        " for help."
    )
}
