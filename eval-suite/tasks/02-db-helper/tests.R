suppressPackageStartupMessages({
  library(testthat)
  library(DBI)
  library(RSQLite)
})

source("solution.R", local = TRUE)

make_con <- function() {
  con <- dbConnect(SQLite(), ":memory:")
  dbExecute(con, "CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TEXT,
    amount REAL
  )")
  rows <- data.frame(
    customer_id = c(1, 1, 1, 2, 2, 3),
    order_date  = c("2025-01-01", "2025-03-15", "2025-06-01",
                    "2025-02-10", "2025-04-20", "2025-05-05"),
    amount      = c(10, 20, 30, 40, 50, 60)
  )
  dbWriteTable(con, "orders", rows, append = TRUE)
  con
}

test_that("function exists with the right signature", {
  expect_true(exists("get_orders", inherits = TRUE))
  expect_true(is.function(get_orders))
  expect_named(formals(get_orders), c("con", "customer_id", "since_date"))
})

test_that("returns expected rows", {
  con <- make_con(); on.exit(dbDisconnect(con))
  out <- get_orders(con, customer_id = 1, since_date = "2025-02-01")
  expect_true(is.data.frame(out))
  expect_equal(nrow(out), 2)
  expect_setequal(out$amount, c(20, 30))
})

test_that("results are sorted by order_date ascending", {
  con <- make_con(); on.exit(dbDisconnect(con))
  out <- get_orders(con, customer_id = 1, since_date = "2025-01-01")
  expect_equal(out$order_date, sort(out$order_date))
})

test_that("filtering by customer is correct", {
  con <- make_con(); on.exit(dbDisconnect(con))
  out <- get_orders(con, customer_id = 2, since_date = "1900-01-01")
  expect_equal(nrow(out), 2)
  expect_true(all(out$customer_id == 2))
})

test_that("uses parameterised queries (no string interpolation)", {
  src <- paste(readLines("solution.R"), collapse = "\n")
  bad <- grepl("paste0?\\([^)]*customer_id", src) ||
         grepl("sprintf\\([^)]*customer_id", src) ||
         grepl("glue\\(.*\\{customer_id\\}", src)
  expect_false(bad, info = "found string interpolation of customer_id into SQL")

  uses_params <- grepl("params\\s*=", src) ||
                 grepl("dbBind\\(", src) ||
                 grepl("\\?", src) ||
                 grepl(":customer_id|\\$customer_id", src)
  expect_true(uses_params, info = "no evidence of parameter binding (?, :name, params=, dbBind)")
})

test_that("SQL injection in customer_id does not return all rows", {
  con <- make_con(); on.exit(dbDisconnect(con))
  expect_error(
    out <- get_orders(con, customer_id = "1 OR 1=1", since_date = "1900-01-01"),
    NA  # may error or return 0 rows; both fine. Must NOT return all 6.
  )
  if (exists("out") && is.data.frame(out)) {
    expect_lt(nrow(out), 6)
  }
})
