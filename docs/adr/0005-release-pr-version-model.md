# ADR-0005: Version model and stop point of the `release-pr` skill

## Status
Accepted (2026-09-19)

## Context

The owner's packages release in two incompatible ways. `fmisc` bumps in a
dedicated PR ("Increment version number to 0.2.0") and tags that commit, so
`main` carries the last released version between releases. `lintrhelper`
has every PR bump the version *as its last change*, which leaves `main` with
a version whose `NEWS.md` heading is empty: the entries for it arrive with the
next PR. Under that convention no tag can be consistent — the commit that
completes 0.3.2 already declares 0.3.3 — and in practice nothing has been
tagged there since `v0.2.0` although 0.3.0–0.3.2 carry entries.

The tidyverse model (`usethis::use_dev_version()`, a `.9000` suffix and a
`(development version)` heading between releases, replaced at release time)
and Keep a Changelog's `[Unreleased]` section are the documented defaults in
both ecosystems. Neither of the owner's repositories uses them.

Existing release skills (Apache Arrow's `r-cran-release`, hubverse, RocketPy,
Bear, bpftop, and others surveyed on 2026-09-19) converge on one shape: the
agent prepares branch, bump, changelog and PR; a human merges; tag and
GitHub release are a separate, confirmed step; publishing is CI's. Only one
surveyed skill merges and tags on its own.

## Decision

`release-pr` assumes the **per-PR bump, corrected**: every PR that changes
behavior sets the version it delivers *first*, then writes its entries under
that heading. On `main`, declared version, top changelog heading and the tag
always agree; no development suffix, no empty heading ahead.

It has two modes. The default prepares the release on the current branch
(bump derived from changelog, commits and removed exports, confirmed by the
user; version set by `usethis::use_version()` or `uv version`; checks run and
recorded; PR body written) and stops at the PR. `tag` runs on `main` after
the merge, tags `vX.Y.Z` and publishes the GitHub release from the changelog
section, each outward action confirmed. It never publishes to CRAN or PyPI.

The tidyverse / `[Unreleased]` model is served by the same steps, because
`use_version()` replaces a development heading and a `[Unreleased]` heading is
renamed. It is not a separate branch of the skill.

CRAN and PyPI material lives on the reference pages and is read only when
the package publishes there.

## Decision drivers

- A tag whose commit declares a different version is wrong for every
  consumer (`pak::pak("owner/pkg@v0.3.2")` installs 0.3.3). The convention
  producing it is the thing to change, not something to accommodate.
- Bump-first is a one-line change to the per-PR convention, and it keeps
  what the owner wanted from it: `main` always names the version in flight,
  with no `.9000` dance.
- Deterministic facts (versions, headings, tags, commit counts, removed
  exports) come from `scripts/release_state.py`; the model only judges and
  writes.
- Publishing is irreversible and credentialed; CI with trusted publishing
  does it with attestations and an audit trail, an agent session does not.

## Considered options

- **Per-PR bump, corrected (chosen).**
- **Dev-suffix + release PR (tidyverse model).** Rejected as the default:
  requires converting both repositories; gains nothing over bump-first for a
  single-maintainer package. Still supported implicitly.
- **Per-PR bump as practised in `lintrhelper`.** Rejected: inconsistent
  tags by construction.
- **Detect both models and branch.** Rejected: bump-first already covers the
  dev-suffix case, so a second branch would only exist to serve the
  inconsistent one.
- **Stop at the PR, no `tag` mode.** Rejected: the post-merge step is the
  one the owner has been skipping; leaving it manual reproduces the problem.
- **Run through publish.** Rejected: see drivers.

## Consequences

- `lintrhelper`'s `AGENTS.md` "Version bumps" section must change to
  bump-first (run `use_version()` before writing entries; no empty heading
  for the next PR). `main` there is in state `open-heading` until the next
  release PR adopts the 0.3.3 heading or re-sets the version.
- `fmisc` needs no change: `main` is in state `released`.
- Every merge of a release PR is followed by one `tag` run; nothing in CI
  does it. If that proves to be forgotten, the next step is a tag-on-merge
  workflow, not a change to this skill.
- The Keep a Changelog `[Unreleased]` section is not kept between releases
  in Python repos using this skill.

## Notes

Deliberately not in the skill, recorded so it is not helpfully re-added:

- Conventional-commit-only bumping (release-please style). The owner's
  history is only partly conventional, and squash merges hide `fix:` inside
  a `docs:` title; commits are one signal of three.
- A post-release `use_dev_version()` step.
- Automatic CRAN submission or `uv publish`.
- A generic "cut a release" for other languages.
