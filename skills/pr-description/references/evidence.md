# Running the evidence for "Vorher / Nachher" and "Geprüft"

How to produce the output that sections 2 and 7 paste. Every block in the
description comes from a command run in this session; nothing is written from
memory or expectation.

## Contents

- [Set up both branches](#set-up-both-branches)
- [R: reprex on both branches](#r-reprex-on-both-branches)
- [Python: a minimal script on both branches](#python-a-minimal-script-on-both-branches)
- [Performance: a benchmark on both branches](#performance-a-benchmark-on-both-branches)
- [When the example cannot be run](#when-the-example-cannot-be-run)
- [Geprüft: the checks](#geprüft-the-checks)
- [Example output](#example-output)

## Set up both branches

Never switch the user's working tree. Check the base out into a separate
worktree inside `<run>`, the same temporary directory the description goes
into:

```bash
base_sha=$(git merge-base <base> HEAD)
git worktree add --detach <run>/base "$base_sha"
```

The merge-base is the code the PR's diff is computed against, so "Vorher"
shows exactly what the PR changes. The PR branch is the user's current
checkout; uncommitted changes are not part of the PR, so when `git status`
shows any, say so in chat and run "Nachher" from a second worktree at `HEAD`.
Remove the worktrees when done: `git worktree remove <run>/base`.

Write the example once and run the identical file on both sides. Keep it
minimal: the smallest input that shows the change, no setup the reviewer does
not need.

## R: reprex on both branches

Install each side into its own library, then render the same reprex with that
library first on the library path. `reprex` renders in a fresh child session
that inherits `.libPaths()`, so the example itself stays a plain
`library(<pkg>)` the reviewer can run.

```bash
mkdir -p <run>/lib-base <run>/lib-pr <run>/vorher <run>/nachher
R CMD INSTALL --library=<run>/lib-base <run>/base
R CMD INSTALL --library=<run>/lib-pr .
cp <run>/example.R <run>/vorher/example.R
cp <run>/example.R <run>/nachher/example.R
Rscript -e '.libPaths(c("<run>/lib-base", .libPaths())); reprex::reprex(input = "<run>/vorher/example.R", venue = "gh", advertise = FALSE, html_preview = FALSE)'
Rscript -e '.libPaths(c("<run>/lib-pr", .libPaths())); reprex::reprex(input = "<run>/nachher/example.R", venue = "gh", advertise = FALSE, html_preview = FALSE)'
```

Each call writes `example_reprex.md` next to its input; paste that file
verbatim. Add `session_info = TRUE` only when the change depends on the R or
package versions. An error in the "Vorher" reprex is the evidence, not a
failure: paste it.

## Python: a minimal script on both branches

Run the same script from each tree with the project's own runner, so imports
resolve against that tree:

```bash
uv run --directory <run>/base python <run>/example.py
uv run --directory . python <run>/example.py
```

Without uv, use the project's environment and put the tree's source first on
the path, e.g. `PYTHONPATH=<run>/base/src python3 <run>/example.py`. Paste the
script once per side with its output below it, the output prefixed with `# `
like a reprex, or as a separate `text` block.

## Performance: a benchmark on both branches

Run the same benchmark on both sides, on the same machine, one after the
other. R: `bench::mark()` in the reprex. Python: `python -m timeit` or
`pytest-benchmark`. A CLI: `hyperfine` with one command per tree. Paste the
numbers as printed, plus one line naming the machine (CPU, OS) and that both
ran in the same session. Never round a speed-up into the prose that the table
does not show.

## When the example cannot be run

Write one line, then the example the reviewer can run, with no output under
it:

```markdown
## Vorher / Nachher

Nicht ausgeführt, weil die Funktion eine Verbindung zur Produktionsdatenbank braucht.

    library(<pkg>)
    <call>
```

Name the concrete reason: the runtime or a package is not installed here, the
code needs credentials, a network service, a database, hardware or data that
is not available. Do not install a missing runtime silently to get output; ask
in chat when installing it is quick and the user may want it. Never fill the
block with the output the fix should produce.

## Geprüft: the checks

Find the repo's checks in its CI workflow (`.github/workflows/`,
`azure-pipelines.yml`), `AGENTS.md`, `CONTRIBUTING.md` or `Makefile`. Run the
ones that run locally on the PR branch head. Typical sets:

- R: `devtools::test()`, `devtools::check()` (or `R CMD check`),
  `lintr::lint_package()`.
- Python: `pytest`, `ruff check .`, the type checker the repo uses.

Report each as `` `<command>` — <result line> ``, the result line taken from
the tool's own summary (`Status: 2 WARNINGs, 1 NOTE`, `142 passed`). A check
that fails or warns stays in the list as it printed; mention it in chat too.
Do not fix code to make a check pass: that changes the PR, which is the
author's call.

Under `### Nicht geprüft` list what did not run, each with its reason or the
place it is covered: an OS or R/Python version matrix that only CI runs, a
tool that is not installed here, integration tests that need credentials,
CRAN incoming checks for a package not on CRAN.

## Example output

From a smoke run on a throwaway R package whose `clamp()` set values above
`hi` to `lo`:

````markdown
## Vorher / Nachher

### Vorher (`main`)

``` r
library(clampr)
clamp(c(-5, 3, 12), lo = 0, hi = 10)
#> [1] 0 3 0
```

### Nachher (`fix-clamp-upper`)

``` r
library(clampr)
clamp(c(-5, 3, 12), lo = 0, hi = 10)
#> [1]  0  3 10
```

## Geprüft

- `R CMD check --no-manual clampr_0.1.0.tar.gz` — Status: 2 WARNINGs, 1 NOTE

### Nicht geprüft

- `devtools::test()`: das Paket hat keine Tests
- Windows und macOS: keine CI-Matrix in diesem Repo
````
