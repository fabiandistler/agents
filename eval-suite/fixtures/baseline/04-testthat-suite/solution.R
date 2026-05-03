# baseline fixture: only 2 test_that blocks (should fail "at least 4" check)
# and forgets to source target.R
test_that("normal division", {
  expect_equal(safe_divide(10, 2), 5)
})

test_that("by zero", {
  expect_equal(safe_divide(1, 0), NA_real_)
})
