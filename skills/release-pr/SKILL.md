---
name: release-pr
category: workflow
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires git and the GitHub CLI (`gh`). R packages need Rscript with usethis and devtools; Python packages need uv. `scripts/release_state.py` is stdlib-only Python 3.11+.
argument-hint: "[major | minor | patch | X.Y.Z | tag]"
description: Turn the current branch into a release pull request for an R or Python package — confirmed version bump, finalized NEWS.md or CHANGELOG.md, checks run, PR body written. After merge, tag and publish the GitHub release.
metadata:
  version: "1.0"
---

# Release PR

One run = one package, one version. The default mode makes the current branch's
pull request *the* release of that version: version set, changelog finalized,
checks run, PR body written. The `tag` mode runs on `main` after that PR merged
and turns the merge commit into a tag and a GitHub release. Publishing to CRAN
or PyPI is never this skill's job; the reference pages say where it belongs.

## When to use

Use this when a branch is ready to become a release ("make this the 0.4.0
release", "cut a release from this branch", "release-pr minor") or right after
such a PR merged ("tag the release", "release-pr tag").

Not for writing the feature itself, not for hotfixing CI, and not for
submitting to CRAN or uploading to PyPI.

## The version model

Every pull request that changes behavior sets the version it delivers and
writes its entries under exactly that heading. Nothing runs ahead: no `.9000`
development suffix on `main`, no empty next-version heading opened "for the next
PR". So on `main`:

- `DESCRIPTION` / `pyproject.toml` version == the top heading of `NEWS.md` /
  `CHANGELOG.md`, and that heading has entries.
- A tag `vX.Y.Z` points at a commit whose declared version is `X.Y.Z`.
- Every merge of a release PR is followed by exactly one `tag` run.

A repository still on the development-suffix model (`0.3.1.9000`, a
`(development version)` or `[Unreleased]` heading) is handled by the same
steps: the release step replaces the development heading with the concrete
version. A repository whose last PR opened an empty heading ahead of its
entries is in state `open-heading` (see below): adopt that heading instead of
bumping again, and re-set the version if the evidence calls for a larger bump.

## Non-negotiable rules

1. **Confirm the version before writing it.** Show the evidence (commits,
   changelog sections, removed exports) and the proposed number; wait for a yes.
   If the argument asks for a smaller bump than the evidence supports, stop and
   say why before proceeding.
2. **Never edit a version by hand when a tool exists.** R: `usethis::use_version()`.
   Python: `uv version`. They keep the lockfile and the changelog heading in step.
3. **Checks run before the push, and their results go into the PR body
   verbatim.** A failing check is fixed if it is in the PR's own scope,
   otherwise the run stops and reports. Never skip, disable, or loosen a test
   or a lint threshold to get a release green.
4. **Outward actions get an explicit confirmation each**: pushing the branch,
   opening or editing the PR, pushing the tag, publishing the release.
5. **No publish.** No `devtools::submit_cran()`, no `uv publish`, no
   `twine upload`. Those belong to CI with trusted publishing or to the user.
6. **Never move or delete a tag, never force-push**, never re-run a
   release on a version that already has a tag.

## Procedure: prepare (default)

Copy the checklist and work through it:

- [ ] 0 State: run `scripts/release_state.py`, read the JSON
- [ ] 1 Derive the bump, confirm the version
- [ ] 2 Set the version with the language's tool
- [ ] 3 Write or finalize the changelog section
- [ ] 4 Update other version-bearing files
- [ ] 5 Run the checks, record results
- [ ] 6 Commit, push, write the PR body

### 0 State

Preconditions: inside the package's git repository, on a branch that is not
the default branch, working tree clean apart from the PR's own changes. On the
default branch, stop and ask for a branch name. Then:

```bash
git fetch origin
python3 <skill>/scripts/release_state.py --repo . > /tmp/release-state.json
```

The script detects the language (`DESCRIPTION` → R, `pyproject.toml` →
Python), reports the declared version, the top changelog heading and whether it
has entries, the last version tag, a bump suggestion from the commits since
that tag (and, for R, exports removed from `NAMESPACE`), places outside the
changelog that mention the current version, and a `state`:

| State | Meaning in this mode |
|---|---|
| `released` | current version already tagged: bump (the normal case) |
| `development` | dev suffix or Unreleased heading: bump replaces it |
| `open-heading` | empty heading from a bump that ran ahead: adopt it |
| `consistent` | this branch already bumped and wrote entries: verify only |
| `mismatch` | version and heading disagree, or no changelog: fix first |

`mismatch` and `open-heading` exit non-zero with the reason in `problems`.
Read the language page now: `references/r.md` or `references/python.md`.

### 1 Derive the bump

Three sources, in this order of authority:

1. **The changelog entries this PR will carry** (write them mentally first, or
   read the ones already on the branch): a breaking change → major, a new
   user-facing feature → minor, only fixes, docs, internals → patch.
2. **Commits since the last tag**, as the script counted them: `!` or
   `BREAKING CHANGE:` → major, `feat` → minor, otherwise patch. Merge commits
   are excluded so nothing counts twice. Unconventional subjects count for
   nothing; if most are unconventional, the diff is the evidence, not the log.
3. **Removed exports** (R, from `NAMESPACE`) → breaking.

Below 1.0.0 a breaking change bumps minor, not major (the release-please and
python-semantic-release convention; SemVer itself only says "anything may
change"). An explicit `X.Y.Z` argument wins over all of this, but a number
below what the evidence supports is queried, not silently accepted.

Show the user: the evidence in three lines, the proposed version, the last
tag. Wait for confirmation.

### 2 Set the version

Run the language's tool, never a text edit — the exact commands are on the
language page. Order matters: **bump first, then write the entries** under
the heading the bump created. That is the correction to a bump-last habit,
which leaves an empty heading on `main` and a tag that disagrees with the
declared version.

### 3 Write or finalize the changelog section

Under the new heading, one bullet per user-visible change, in the language's
house style (tidyverse NEWS style or Keep a Changelog; on the language page).
Sources: the branch's diff and commits, the linked issues. Only what a user
of the package notices; internal refactors stay out unless they change
behavior. Reference the issue or PR number. Breaking changes come first, each
with the symptom a user sees and what to do instead.

If entries already exist on the branch, proofread against the diff: every
exported function that changed has a bullet; no bullet describes something
the diff does not contain.

### 4 Other version-bearing files

Walk `version_mentions` from the script output — the places outside the
changelog and lockfiles that still say the old version (README install
snippets pinned to a tag, `CITATION.cff`, `codemeta.json`, `docs/conf.py`, a
hand-maintained `__version__`). Update the ones that are meant to track the
release; leave historical mentions alone. Re-run the script: `state` must now
be `consistent`.

### 5 Run the checks

The repository's own gate first (a `Makefile` target, `pre-commit`, a
`justfile`), then the language's standard set from the language page. Run
what CI runs, locally, so the PR does not turn red on push. Keep every
command and its one-line outcome for the PR body. What was *not* run (the
CI-only OS matrix, CRAN incoming checks) is listed too — reviewers need the
gap named, not implied.

### 6 Commit, push, PR body

Commit the version bump and the changelog together, separate from the
feature commits, as `Increment version number to X.Y.Z` (usethis's own
message; used for Python too so both languages read the same in `git log`).

Push after confirmation. If the branch already has a PR, edit its body;
otherwise open one, titled `<package> X.Y.Z`. The body, in this order:

```markdown
## Release <package> X.Y.Z

**Bump:** minor — 3 `feat` commits since v0.2.0, no breaking change,
NEWS carries a "New features" section.

### Changes
<the changelog section, verbatim>

### Checks run
- `make check` — 0 errors, 0 warnings, 0 notes
- `lintr::lint_package()` — clean

### Not verified here
- Windows and macOS: CI matrix on this PR
- CRAN incoming checks: package is not on CRAN

### After merge
Run the `tag` step on `main`: tags `vX.Y.Z` at the merge commit and
publishes the GitHub release from the section above.

Closes #<n>
```

Then stop. Merging is the user's decision.

## Procedure: tag

Runs on the default branch after the release PR merged.

- [ ] 0 `git switch main && git pull --ff-only`; working tree clean
- [ ] 1 `release_state.py` reports `consistent`; note `version` and `tag_prefix`
- [ ] 2 CI on `HEAD` is green (`gh run list --commit $(git rev-parse HEAD)`);
      a red or pending head is not tagged
- [ ] 3 `release_state.py --section X.Y.Z > /tmp/notes.md`; the file is not empty
- [ ] 4 Show tag name, commit, and the notes; confirm
- [ ] 5 `git tag -a vX.Y.Z -m "<package> X.Y.Z" && git push origin vX.Y.Z`
- [ ] 6 `gh release create vX.Y.Z --verify-tag --title "<package> X.Y.Z" --notes-file /tmp/notes.md`
      (`--prerelease` for a Python `a`/`b`/`rc` version)
- [ ] 7 Report the release URL and what happens next per the language page
      (r-universe rebuild, a tag-triggered PyPI workflow, or nothing)

If `release_state.py` says `released`, the version is already tagged: stop,
nothing to do. If it says anything else, the merge did not leave `main`
consistent; report the `problems` line and stop — fixing `main` is a new PR,
not a tag.

## References

- `references/r.md` — `usethis::use_version()` under Rscript, tidyverse
  NEWS.md style, the check set, `use_github_release()`, r-universe, and the
  CRAN-only material (`use_release_issue()`, `cran-comments.md`,
  `check_win_devel()`, rhub v2, revdepcheck).
- `references/python.md` — `uv version` semantics, Keep a Changelog, towncrier
  and git-cliff when the repo uses them, the check set, tag conventions and
  PEP 440, and the PyPI-only material (trusted publishing, attestations).
- `scripts/release_state.py --help` — the state report used above.

## Provenance

Written 2026-09-19 against usethis 3.2.2, devtools 2.5.2, uv 0.12.17,
release-please 17.11, Keep a Changelog 2.0.0. The two-mode split (prepare,
then tag on request) is what most existing release skills converge on:
the agent prepares, a human merges, the tag is a separate confirmed step and
publishing is CI's. The version model is recorded in `docs/adr/0005`.
