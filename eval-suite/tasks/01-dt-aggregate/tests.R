suppressPackageStartupMessages({
  library(testthat)
  library(data.table)
})

source("solution.R", local = TRUE)

make_dt <- function() {
  data.table(
    region   = c("a", "a", "a", "b", "b", "c"),
    product  = c("x", "x", "y", "x", "y", "z"),
    quantity = c(2L, 3L, 1L, 4L, 5L, 1L),
    price    = c(10, 10, 100, 20, 20, 7)
  )
}

test_that("function exists with the right signature", {
  expect_true(exists("summarize_sales", inherits = TRUE))
  expect_true(is.function(summarize_sales))
  expect_named(formals(summarize_sales), "dt")
})

test_that("returns a data.table with the expected columns", {
  out <- summarize_sales(make_dt())
  expect_s3_class(out, "data.table")
  expect_setequal(names(out), c("region", "revenue", "top_product", "n_orders"))
  expect_type(out$region, "character")
  expect_type(out$revenue, "double")
  expect_type(out$top_product, "character")
  expect_true(is.integer(out$n_orders) || is.numeric(out$n_orders))
})

test_that("revenue, top_product, n_orders are correct", {
  out <- summarize_sales(make_dt())
  setkey(out, region)
  expect_equal(out["a", revenue], 2 * 10 + 3 * 10 + 1 * 100)
  expect_equal(out["b", revenue], 4 * 20 + 5 * 20)
  expect_equal(out["c", revenue], 1 * 7)
  expect_equal(out["a", top_product], "y")
  expect_equal(out["b", top_product], "y")
  expect_equal(out["a", as.integer(n_orders)], 3L)
})

test_that("result is sorted by revenue descending", {
  out <- summarize_sales(make_dt())
  expect_equal(out$revenue, sort(out$revenue, decreasing = TRUE))
})

test_that("input is not mutated by reference", {
  dt <- make_dt()
  before <- copy(dt)
  invisible(summarize_sales(dt))
  expect_equal(dt, before)
})
