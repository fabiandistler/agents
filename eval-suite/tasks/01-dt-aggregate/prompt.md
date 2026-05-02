Write a function `summarize_sales(dt)` and save it to `solution.R` in the
current working directory.

Input: a `data.table` with columns `region` (character), `product` (character),
`quantity` (integer), `price` (numeric). A file `input.csv` exists in the cwd
with example data — you can use it to sanity-check your function but the
function must work on any data.table with that schema.

Output: a `data.table` with one row per region containing:
  - `region`     (character)
  - `revenue`    (numeric, sum of quantity * price)
  - `top_product` (character, the product with the highest revenue in that region)
  - `n_orders`   (integer, number of input rows for that region)

Sort the result by `revenue` descending.

Requirements:
  - Use data.table idioms (no dplyr, no base aggregate).
  - The function must not modify the input by reference.
  - Do not print or message anything.

Only write `solution.R`. Do not run code.
