summarize_sales <- function(dt) {
  stopifnot(data.table::is.data.table(dt))
  d <- data.table::copy(dt)
  d[, revenue := quantity * price]

  by_region_product <- d[, .(rev = sum(revenue), n = .N),
                         by = .(region, product)]
  top <- by_region_product[
    by_region_product[, .I[which.max(rev)], by = region]$V1,
    .(region, top_product = product)
  ]
  totals <- d[, .(revenue = sum(revenue), n_orders = .N), by = region]
  out <- totals[top, on = "region"]
  data.table::setorder(out, -revenue)
  out[, .(region, revenue, top_product, n_orders)]
}
