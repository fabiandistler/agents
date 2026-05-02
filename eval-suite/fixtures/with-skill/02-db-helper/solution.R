get_orders <- function(con, customer_id, since_date) {
  sql <- "SELECT id, customer_id, order_date, amount
            FROM orders
           WHERE customer_id = ?
             AND order_date >= ?
           ORDER BY order_date ASC"
  DBI::dbGetQuery(con, sql, params = list(customer_id, since_date))
}
