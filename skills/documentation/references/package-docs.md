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
