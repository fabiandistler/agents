# Package Reference

The reader is writing code that calls your library, with your page open in a
second window. Optimize for scanning and copying, not for reading.

## Skeleton

```markdown
# <package> Reference

## Installation
## Quick example
## Functions
### <function>(<signature>)
  Purpose · parameters · return value · runnable example
## Reference index
```

## Section notes

**Function entries.** One entry per exported function: a single line of
purpose, each parameter with its type and default, what is returned, and a
runnable example with realistic values. Document with roxygen2 tags
(`@param`, `@returns`, `@examples`, `@export`) in R, or docstrings in
Python — pick one convention (Google or NumPy) and keep it everywhere.

**Reference index.** A complete list of every exported function pointing at
its entry. In R this is the pkgdown `_pkgdown.yml` reference index; in
Python it is the Sphinx autodoc or mkdocstrings API page. Generate the index
from the source; never hand-maintain a second list of function names.

**Examples.** Every example is executed in CI (R CMD check runs
`@examples`; doctest or an equivalent runner runs docstring examples), so a
broken example fails the build instead of misleading the reader.

## Runnable in the browser (R, optional)

When a vignette or Quarto article should let the reader edit and re-run an
example without installing R, use the official `quarto-live` extension
(`quarto add r-wasm/quarto-live`). It runs webR in the reader's browser, so
static hosting (GitHub Pages, Netlify) is enough.

````markdown
---
format: live-html
engine: knitr
webr:
  packages: [yourpkg]
  repos: [https://<owner>.r-universe.dev]
---

{{< include ./_extensions/r-wasm/live/_knitr.qmd >}}

```{webr}
yourpkg::main_function(example_data)
```
````

- **Your package must exist as a WebAssembly binary.** webR installs only
  pre-compiled Wasm binaries, never from source. R-universe builds them for
  every package it hosts; the default webR repo covers only part of CRAN.
  Check that every dependency loads in the webR REPL (webr.sh) before
  promising a live page.
- **A `{webr}` chunk is not a test.** It runs client-side, so R CMD check
  never executes it. Keep the canonical example in `@examples`; the live
  chunk is a copy for exploration.
- **Pin the extension** (commit `_extensions/`) and state the webR version
  the page was checked with — the webR API is still declared unstable.
- **Mobile browsers cap WebAssembly memory** whatever the device has; keep
  live examples to small data.

Source: forge pass 2026-10-03 on the webR docs (docs.r-wasm.org, webR 0.6.0)
and the quarto-live README; review in Todoist (Tickler, 2027-06-21).

## Failure modes

- **Hand-maintained function lists** that miss new exports or keep removed
  ones. Generate the index or test that it matches the namespace.
- **Parameters documented without types, defaults, or return values.**
  The reader cannot call what they cannot construct.
- **Unexecuted examples.** Copy-pasted output that no longer runs is the
  fastest way to lose a user's trust.
- **Mixed docstring styles** in one package, so no single generator renders
  the reference cleanly.
- **Tutorial prose inside the reference.** Usage narratives belong in a
  tutorial or how-to guide; link to them instead of inlining them here.
