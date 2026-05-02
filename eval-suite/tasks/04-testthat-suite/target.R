safe_divide <- function(x, y) {
  stopifnot(is.numeric(x), is.numeric(y))
  out <- x / y
  out[!is.na(y) & y == 0] <- NA_real_
  out
}
