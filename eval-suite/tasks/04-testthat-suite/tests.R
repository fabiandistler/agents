suppressPackageStartupMessages(library(testthat))

src <- paste(readLines("solution.R"), collapse = "\n")

test_that("solution sources without error", {
  expect_no_error(parse(file = "solution.R"))
})

test_that("uses testthat", {
  expect_true(grepl("test_that\\s*\\(", src))
  expect_true(grepl("expect_", src))
})

test_that("has at least 4 test_that blocks", {
  n <- length(gregexpr("test_that\\s*\\(", src)[[1]])
  expect_gte(n, 4L)
})

test_that("sources target.R", {
  expect_true(grepl("source\\s*\\(\\s*[\"']target\\.R[\"']", src))
})

test_that("does not redefine safe_divide", {
  expect_false(grepl("safe_divide\\s*<-\\s*function", src),
               info = "must not redefine safe_divide")
})

test_that("the produced tests actually run and pass against target.R", {
  reporter <- testthat::SilentReporter$new()
  res <- tryCatch(
    testthat::test_file("solution.R", reporter = reporter),
    error = function(e) e
  )
  expect_false(inherits(res, "error"),
               info = if (inherits(res, "error")) conditionMessage(res) else "")
  if (!inherits(res, "error")) {
    df <- as.data.frame(res)
    n_fail <- sum(df$failed)
    n_err  <- sum(df$error)
    expect_equal(n_fail, 0L, info = sprintf("%d test failures in solution.R", n_fail))
    expect_equal(n_err, 0L,  info = sprintf("%d errors in solution.R", n_err))
  }
})

test_that("covers the by-zero case", {
  expect_true(grepl("0", src) && grepl("NA", src),
              info = "should test division by zero -> NA")
})
