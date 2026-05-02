A file `target.R` exists in the current working directory. It defines a
function `safe_divide(x, y)` that divides two numeric vectors element-wise and
should:
  - return `NA_real_` where `y == 0`
  - propagate `NA` from either input
  - work on equal-length vectors and on a length-1 `y` recycled across `x`

Write a `testthat` test suite for this function and save it to `solution.R` in
the current working directory.

Requirements:
  - Use `testthat` (3rd edition style is fine).
  - Write at least 4 separate `test_that()` blocks covering: normal division,
    division by zero, NA propagation, and vector recycling.
  - Use Arrange–Act–Assert structure.
  - Source `target.R` from the test file so the function is available.
  - Do not modify or re-define `safe_divide`.

Only write `solution.R`. Do not run code.
