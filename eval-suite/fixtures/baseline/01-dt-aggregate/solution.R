# baseline fixture: mutates input by reference (should fail one test)
summarize_sales <- function(dt) {
  dt[, revenue := quantity * price]
  by_rp <- dt[, .(rev = sum(revenue), n = .N), by = .(region, product)]
  top <- by_rp[by_rp[, .I[which.max(rev)], by = region]$V1,
               .(region, top_product = product)]
  totals <- dt[, .(revenue = sum(revenue), n_orders = .N), by = region]
  out <- totals[top, on = "region"]
  data.table::setorder(out, -revenue)
  out[, .(region, revenue, top_product, n_orders)]
}
