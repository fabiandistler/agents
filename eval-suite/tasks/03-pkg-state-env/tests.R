suppressPackageStartupMessages(library(testthat))

env <- new.env()
sys.source("solution.R", envir = env)

test_that(".state exists and has empty parent", {
  expect_true(exists(".state", envir = env, inherits = FALSE))
  expect_true(is.environment(env$.state))
  expect_identical(parent.env(env$.state), emptyenv())
})

test_that("set_state / get_state round-trip works", {
  expect_true(is.function(env$set_state))
  expect_true(is.function(env$get_state))
  env$set_state("foo", 42)
  expect_equal(env$get_state("foo"), 42)
  env$set_state("bar", list(x = 1, y = 2))
  expect_equal(env$get_state("bar")$y, 2)
})

test_that("get_state returns default for missing keys", {
  default <- env$get_state("does_not_exist", default = "fallback")
  expect_equal(default, "fallback")
  expect_null(env$get_state("also_missing"))
})

test_that("clear_state empties the environment and returns invisibly", {
  env$set_state("a", 1); env$set_state("b", 2)
  res <- withVisible(env$clear_state())
  expect_false(res$visible)
  expect_length(ls(envir = env$.state), 0)
})

test_that("no library()/require() calls in source", {
  src <- paste(readLines("solution.R"), collapse = "\n")
  expect_false(grepl("\\blibrary\\s*\\(", src),
               info = "library() must not appear in package code")
  expect_false(grepl("\\brequire\\s*\\(", src),
               info = "require() must not appear in package code")
})

test_that("no <<- or globalenv() writes", {
  src <- paste(readLines("solution.R"), collapse = "\n")
  expect_false(grepl("<<-", src), info = "no super-assignment allowed")
  expect_false(grepl("globalenv\\s*\\(\\)", src),
               info = "must not write to globalenv()")
})

test_that("nothing leaked into globalenv", {
  for (nm in c(".state", "set_state", "get_state", "clear_state")) {
    expect_false(exists(nm, envir = globalenv(), inherits = FALSE),
                 info = sprintf("%s leaked to globalenv", nm))
  }
})
