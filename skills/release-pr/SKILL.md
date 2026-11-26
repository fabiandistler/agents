---
name: release-pr
category: workflow
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires git plus the forge's CLI — `gh` or the GitHub MCP tools (GitHub), `az` with the azure-devops extension (Azure Repos), or `glab` (GitLab); other hosts fall back to git only. R packages need Rscript with usethis and devtools; Python packages need uv. `scripts/release_state.py` is stdlib-only (tomllib on Python 3.11+, regex fallback below).
argument-hint: "[major | minor | patch | X.Y.Z | tag]"
description: Turn the current branch into a release pull request for an R or Python package — confirmed version bump, finalized NEWS.md or CHANGELOG.md, checks run, PR body written. After merge, tag and publish the release.
metadata:
  version: "1.2"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Release PR

One run covers one package and one version. In the default prepare mode, turn
the current branch into its release PR when it is ready to ship. After merge,
use `tag` on the default branch to tag the merge commit and create the GitHub or GitLab release.
Azure Repos and unknown hosts use an annotated tag with the release notes.

Feature implementation and standalone CI fixes are outside this workflow.
Package registry uploads belong to CI with trusted publishing or to the
user. Leave `devtools::submit_cran()`, `uv publish`, and `twine upload` to them.

## The version model

Every pull request that changes behavior sets the version it delivers and
writes its entries under exactly that heading. Nothing runs ahead: no `.9000`
development suffix on the default branch, no empty next-version heading opened "for the next
PR". So on the default branch:

- `DESCRIPTION` / `pyproject.toml` version == the top heading of `NEWS.md` /
  `CHANGELOG.md`, and that heading has entries.
- A tag `<tag_prefix>X.Y.Z` points at a commit whose declared version is `X.Y.Z`.
- Every merge of a release PR is followed by exactly one `tag` run.

Never move or delete a tag, force-push, or release a tagged version again.

## Procedure: prepare (default)

Use the numbered steps below as your working checklist.

### 0 State

Preconditions: inside the package's git repository, on a branch that is not
the default branch, working tree clean apart from the PR's own changes. For R,
commit those too before step 2: `usethis::use_version()` aborts under `Rscript`
while tracked files have uncommitted changes. On the default branch, stop and
ask for a branch name. Then:

```bash
git fetch origin
python3 scripts/release_state.py --repo <package-root>  # from the skill directory
```

Run `scripts/release_state.py --help` for the script's options.

The script prints JSON to stdout. It detects the language (`DESCRIPTION` → R, `pyproject.toml` →
Python), reports the declared version, the top changelog heading and whether it
has entries, the last version tag, a bump suggestion from the commits since
that tag (and, for R, exports removed from `NAMESPACE`), places outside the
changelog that mention the current version, the `forge` hosting the remote
(`github`, `azure`, `gitlab`, `unknown`, `none`), and a `state`:

| State | Meaning in this mode |
|---|---|
| `released` | current version already tagged: bump (the normal case) |
| `development` | bump the version and replace any development heading (`(development version)` or `[Unreleased]`) with the concrete version |
| `open-heading` | adopt the empty heading and reset the version only if the evidence calls for a larger bump |
| `consistent` | this branch already bumped and wrote entries: verify only |
| `mismatch` | version and heading disagree, or no changelog: fix first |

Only `mismatch` exits non-zero (3), with the reason in `problems`: it stops the
run. `open-heading` exits 0 and lists the empty heading in `problems`.
Read `references/r.md` for R versioning, NEWS and checks, or
`references/python.md` for uv, CHANGELOG and checks. For a forge other than
`github`, read `references/forges.md` for PR, CI and release commands.

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

Below 1.0.0 a breaking change bumps minor. An explicit `X.Y.Z` takes
precedence. If the requested bump or version falls below what the evidence
supports, stop, explain why, and ask which version to use.

Show the evidence in three lines, the proposed version, and the last tag.
Wait for an explicit yes before writing the version.

### 2 Set the version

Use the version tool from the language reference. For R, use
`usethis::use_version()` for a bump. For Python, use `uv version`. Follow
the language reference for an explicit R version or a dynamic Python version.
The tools keep package metadata and the lockfile in step where applicable.
Set the version before writing the changelog entries so the default branch
lands with a populated release heading matching the declared version.

### 3 Write or finalize the changelog section

Under the new heading, one bullet per user-visible change, in the language's
house style (tidyverse NEWS style or Keep a Changelog; on the language page).
Sources: the branch's diff and commits, the linked issues. Only what a user
of the package notices; internal refactors stay out unless they change
behavior. Reference the issue or PR number. Mark breaking changes inline
with a `**Breaking:**` marker inside their type section, each with the
symptom a user sees and what to do instead.

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

Run the repository's own gate first (e.g. `make check`, `pre-commit run -a`,
or a justfile target), then the language checks. Run CI checks locally
before pushing. Fix failures in the PR's scope and stop and report others.
Keep tests and lint thresholds in force throughout the checks.

Record every command and its one-line outcome verbatim for the PR body.
List the checks you could not run, such as the CI-only OS matrix.

### 6 Commit, push, PR body

Commit the version bump and the changelog together, separate from the
feature commits, as `Increment version number to X.Y.Z` (usethis's own
message; used for Python too so both languages read the same in `git log`).

Get explicit confirmation, push the branch, and find its open PR. Prepare
the body to update it or open a new PR titled `<package> X.Y.Z`. Get separate
explicit confirmation before opening or editing the PR.
For the GitHub PR, use the GitHub MCP tools if the session has them; otherwise
`gh` (`gh pr view`, `gh pr edit`, `gh pr create`). For other forges, use
`references/forges.md`. Write the body to `<run>/pr-body.md` first, where
`<run>` is the directory a fresh `mktemp -d /tmp/release-pr-XXXXXX` printed,
and pass that path to the CLI. The body, in this order:

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
Run the `tag` step on the default branch: tags `<tag_prefix>X.Y.Z` at the merge commit and
publishes the release from the section above.

Closes #<n>   (Azure Repos: link work items instead, see forges.md)
```

Then stop. Merging is the user's decision.

## Procedure: tag

Run on the default branch after the release PR merges. Read
`references/r.md` for the CRAN and r-universe cases, or
`references/python.md` for Python prereleases and PyPI. For a forge other
than GitHub, read `references/forges.md` for CI and release commands.
If tag steps 5–6 use a single annotated tag with notes, confirm its push
before running the forge command.

The commands use placeholders: `<default-branch>` from step 0, `<tag>` for
`<tag_prefix>X.Y.Z`, and `<run>` for the directory a fresh
`mktemp -d /tmp/release-pr-XXXXXX` printed. Substitute the literal values.
Each step may run in a new shell, so shell variables do not carry over.

- [ ] 0 `git remote set-head origin --auto && git symbolic-ref --short refs/remotes/origin/HEAD`
      prints `origin/<default-branch>`; `git switch <default-branch> && git pull --ff-only`;
      working tree clean
- [ ] 1 `release_state.py` reports `consistent`; note `version` and `tag_prefix`
- [ ] 2 CI on `HEAD` is green (`gh run list --commit $(git rev-parse HEAD)`,
      other forges in `references/forges.md`); a red, pending, or missing
      run is not tagged without the user's say-so
- [ ] 3 `release_state.py --section X.Y.Z > <run>/notes.md`; the file is not empty
- [ ] 4 Show the tag name (`<tag>`), commit, and notes. Get explicit
      confirmation before creating and pushing the tag.
- [ ] 5 `git tag -a <tag> -m "<package> X.Y.Z" && git push origin <tag>`
- [ ] 6 Get separate explicit confirmation before publishing the release. On GitHub,
      create it from the pushed tag with
      `gh release create <tag> --verify-tag --title "<package> X.Y.Z" --notes-file <run>/notes.md`.
      Use `--prerelease` for a Python `a`/`b`/`rc` version. The GitHub MCP
      tools only read releases. Use `gh` to create one. If you need REST, run
      `gh api -X POST 'repos/{owner}/{repo}/releases' -f tag_name=<tag> -f name="<package> X.Y.Z" -F body=@<run>/notes.md`
      with `-F prerelease=true` for those prereleases. REST creates a missing
      tag from the default branch, so run it only after step 5 pushed the tag.
      If the release has binary assets, create a draft first and publish
      after all assets are uploaded. For GitLab use `glab release create`.
      Azure Repos and unknown hosts use the single annotated tag with notes
      described in `references/forges.md` in place of steps 5–6.
- [ ] 7 Report the release URL and what happens next per the language page
      (r-universe rebuild, a tag-triggered PyPI workflow, or nothing)

If `release_state.py` says `released`, the version is already tagged: stop,
nothing to do. If it says anything else, the merge did not leave the default branch
consistent; report the `problems` line and stop — fixing the default branch is a new PR,
not a tag.
