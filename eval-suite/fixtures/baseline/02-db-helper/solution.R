# baseline fixture: SQL injection via paste0 (should fail security tests)
get_orders <- function(con, customer_id, since_date) {
  sql <- paste0(
    "SELECT id, customer_id, order_date, amount FROM orders ",
    "WHERE customer_id = ", customer_id,
    " AND order_date >= '", since_date, "' ",
    "ORDER BY order_date ASC"
  )
  DBI::dbGetQuery(con, sql)
}
