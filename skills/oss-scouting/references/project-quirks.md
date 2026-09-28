# Project quirks

Per-project deviations from the default procedure. Verify in the repo when in
doubt rather than adopting blindly.

- data.table tests through its own `test()` mechanism in
  `inst/tests/tests.Rraw` (numbered tests, not testthat) and requires a NEWS
  entry.
- polars has a Rust core — only take candidates whose cause sits in the
  Python layer, the docs, or the tests, unless the user explicitly wants Rust.
- plumber and most R packages use testthat + NEWS.md.
- FastAPI uses pytest and its docs are multilingual (translations follow their
  own process).
