source("target.R")

test_that("normal element-wise division works", {
  result <- safe_divide(c(10, 9, 8), c(2, 3, 4))
  expect_equal(result, c(5, 3, 2))
})

test_that("division by zero yields NA_real_", {
  result <- safe_divide(c(1, 2, 3), c(1, 0, 2))
  expect_equal(result, c(1, NA_real_, 1.5))
})

test_that("NA in either input propagates", {
  result <- safe_divide(c(NA, 4, 6), c(2, NA, 3))
  expect_true(is.na(result[1]))
  expect_true(is.na(result[2]))
  expect_equal(result[3], 2)
})

test_that("length-1 y is recycled across x", {
  result <- safe_divide(c(2, 4, 6), 2)
  expect_equal(result, c(1, 2, 3))
})
