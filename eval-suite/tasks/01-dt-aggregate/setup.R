suppressPackageStartupMessages(library(data.table))
set.seed(1)
dt <- data.table(
  region   = sample(c("north", "south", "east", "west"), 40, replace = TRUE),
  product  = sample(c("alpha", "beta", "gamma"), 40, replace = TRUE),
  quantity = sample(1:10, 40, replace = TRUE),
  price    = round(runif(40, 5, 50), 2)
)
fwrite(dt, "input.csv")
