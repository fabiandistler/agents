# R packages

Verified 2026-09-19 against usethis 3.2.2, devtools 2.5.2, r-lib/actions v2,
rhub 2.0.1. Function names below are stable across those versions; re-check
`?usethis::use_version` when a newer major appears.

## Set the version

```bash
Rscript -e 'usethis::use_version("minor")'   # or "major", "patch"
```

Under `Rscript` (non-interactive) `use_version()` edits `Version:` in
`DESCRIPTION` (and `src/version.c` if present), then calls its NEWS helper:
a top heading `# pkg (development version)` is **replaced** by `# pkg X.Y.Z`;
a concrete top heading gets a new `# pkg X.Y.Z` heading **inserted above**
it. It does not prompt and does not commit outside an interactive session,
so the commit is yours. Called with no argument it prompts, which fails under
`Rscript` — always spell the component out.

For an explicit number the tool is `desc`, and the heading is added by hand
in the same shape:

```bash
Rscript -e 'desc::desc_set_version("1.2.0")'
```

Version rules (r-pkgs.org, lifecycle chapter): released versions have three
components `major.minor.patch`; a fourth component `9000` marks development
and never reaches a tag. Below 1.0.0 a breaking change bumps minor.

## NEWS.md house style (tidyverse)

- One level-1 heading per release, newest first: `# pkg 1.2.0`. No dates.
- `*` bullets, one change per bullet, wrapped at 80 characters, ending in a
  full stop. The function comes first, in backticks with parentheses:
  `` * `lint_project()` gains a `changed_only` argument (#29). ``
- Issue or PR number in parentheses before the full stop; an outside
  contributor as `(@user, #29)`.
- Present tense, describes what the user can now do, not what the diff did.
- With more than a handful of bullets, group under `## Breaking changes`,
  `## New features`, `## Minor improvements and fixes`, in that order.
  Breaking changes always first, each with the symptom and the replacement.
- Order bullets within a group alphabetically by the first function named.

## Checks

The repository's own gate first (`make check`, `pre-commit run -a`). Then:

| Check | Command |
|---|---|
| Docs regenerated | `Rscript -e 'devtools::document()'` |
| README rebuilt (if `README.Rmd`) | `Rscript -e 'devtools::build_readme()'` |
| Full check | `Rscript -e 'devtools::check(remote = TRUE, manual = TRUE)'` |
| Lint | `Rscript -e 'lintr::lint_package()'` |
| URLs (docs, README, DESCRIPTION) | `Rscript -e 'urlchecker::url_check()'` |
| Spelling (if `inst/WORDLIST` exists) | `Rscript -e 'spelling::spell_check_package()'` |

`devtools::check()` runs `--as-cran` by default; `remote = TRUE` adds the
checks that need network (URLs, CRAN incoming), `manual = TRUE` builds the
PDF manual and needs LaTeX — drop `manual` when there is none. The
`r-lib/actions/check-r-package` action fails CI on any **warning**, so a
local warning is a CI failure waiting to happen. `--as-cran` is what CI runs
even for a GitHub-only package.

A quick loop while fixing: `devtools::check(vignettes = FALSE)`; the full
form runs once before the push.

## Other version-bearing files

`codemeta.json` (`version`), `CITATION.cff` (`version`, `date-released`),
`inst/CITATION`, a README install line pinned to a tag
(`pak::pak("owner/pkg@v1.1.0")`). `release_state.py` lists the mentions.

## Tag and GitHub release

Either form. The `gh` form is what the `tag` procedure in `SKILL.md` uses;
the usethis form does the same from inside R:

```bash
Rscript -e 'usethis::use_github_release(publish = TRUE)'
```

`use_github_release()` tags `v{Version}` at `HEAD` (or at the SHA recorded
in a `CRAN-SUBMISSION` file if one exists), and takes the release body from
the matching `NEWS.md` section. Both forms produce the same release.

**r-universe** rebuilds from the default branch on its own within about an
hour of a push; a GitHub release is not required. Only a `packages.json`
entry with `"branch": "*release"` makes the release the trigger.

## CRAN (only when the package is on CRAN, or the user says CRAN)

The maintained checklist is the one `usethis::use_release_issue()` opens as
a GitHub issue — CRAN-oriented, with the first-release block prepended for a
package not yet on CRAN. `devtools::release()` is deprecated in favour of it
(devtools 2.5.0). Items beyond this skill's default set:

- `usethis::use_cran_comments()` creates `cran-comments.md` (in
  `.Rbuildignore`). Two sections: `## R CMD check results` with
  `0 errors | 0 warnings | N notes` and one bullet per NOTE explaining why
  it is acceptable, and `## revdepcheck results` (or "There are currently no
  downstream dependencies for this package"). Terse; the audience is CRAN
  staff.
- `devtools::check_win_devel()` — required by CRAN policy (r-devel); results
  arrive by email in 15–30 minutes. `check_mac_release()` / `check_mac_devel()`
  for macOS.
- `rhub::rhub_check()` — rhub 2.x runs on GitHub Actions in the package's own
  repo after `rhub::rhub_setup()`; the old `check_for_cran()` /
  `devtools::check_rhub()` are defunct.
- `revdepcheck::revdep_check(num_workers = 4)` — not on CRAN, install with
  `pak::pak("r-lib/revdepcheck")`; skip for a patch release. Paste
  `revdep/cran.md` into `cran-comments.md`.
- `devtools::check_doc_fields()` — every export has `@returns` and
  `@examples` (first submission).
- First submission: `Authors@R` includes `cph`, `Title:` / `Description:`
  proofread, licenses of bundled files checked.

Submission itself is `devtools::submit_cran()`, run by the user: it uploads
the tarball with `cran-comments.md` and writes `CRAN-SUBMISSION`. After CRAN
accepts, `use_github_release()` tags the submitted SHA. The tidyverse then
runs `use_dev_version()`; under this skill's version model that step is
skipped — the next PR bumps.
