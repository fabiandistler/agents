# Python packages

Verified 2026-09-19 against uv 0.12.17, twine 7.0.0,
pypa/gh-action-pypi-publish v1.14.2, towncrier 26.9.0, git-cliff 2.14.2,
Keep a Changelog 2.0.0. Re-check `uv version --help` when uv changes major.

## Set the version

```bash
uv version --dry-run --bump minor   # preview
uv version --bump minor             # or --bump major | patch, or an explicit: uv version 1.2.0
```

`uv version` rewrites `[project] version` in `pyproject.toml` **and**
re-locks, so `uv.lock` carries the new version (`--frozen` skips the lock,
`--no-sync` locks without syncing). Verified semantics:

| From → flags | Result |
|---|---|
| `1.2.3 --bump patch` | `1.2.4` |
| `1.2.3 --bump minor --bump rc` | `1.3.0rc1` |
| `1.3.0rc1 --bump rc` | `1.3.0rc2` |
| `1.3.0rc1 --bump stable` | `1.3.0` |
| `1.2.3 --bump rc` alone | error: a pre-release bump needs a release component too |

A **dynamic** version (`dynamic = ["version"]`, hatch-vcs, setuptools-scm,
uv-dynamic-versioning) makes `uv version` refuse: the git tag is the version
source there. Skip the bump step, treat the changelog heading as the declared
version, and say so in the PR body — the `tag` step then *is* the version.
`release_state.py` flags this in `problems`.

PEP 440 ordering for reference: `X.Y.devN < X.YaN < X.YbN < X.YrcN < X.Y <
X.Y.postN`. Tags may carry a leading `v`; PEP 440 normalizes it away.

## CHANGELOG.md house style (Keep a Changelog)

Keep a Changelog 2.0.0 (June 2026) changed guidance, not format. Shape:

```markdown
# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), versions follow PEP 440.

## [1.2.0] - 2026-09-19

### Added
- `wiki_search()` tool that queries one topic folder (#12).

### Fixed
- Empty topic folders no longer register a tool (#15).

[1.2.0]: https://github.com/owner/repo/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/owner/repo/releases/tag/v1.1.0
```

- One level-2 heading per version with the ISO date, newest first.
- Categories in this order, only the ones used: Added, Changed, Deprecated,
  Removed, Fixed, Security.
- One bullet per user-visible change, ending with the issue or PR number.
- Comparison links at the bottom; add the new one, keep the old ones.
- Under this skill's version model there is no `[Unreleased]` section
  between releases: entries go straight under the version heading. A
  repository that has one gets it renamed to the version, not duplicated.
- No `CHANGELOG.md` yet: create it with the header above and the one
  section; do not backfill history.

If the repository already generates its changelog, run its tool instead of
editing by hand, then proofread the result:

- towncrier (`[tool.towncrier]` in `pyproject.toml`, fragments directory):
  `uvx --from towncrier==26.9.0 towncrier build --version X.Y.Z --yes`
- git-cliff (`cliff.toml`): `uvx --from git-cliff==2.14.2 git-cliff --bump --unreleased --prepend CHANGELOG.md`
- commitizen (`[tool.commitizen]`): `uvx --from commitizen==4.18.1 cz bump --dry-run` to preview; its tag format defaults to bare `$version`, so match the repo's existing tags.

## Checks

The repository's own gate first (`pre-commit run -a`, a `Makefile` or
`justfile` target). Then:

| Check | Command |
|---|---|
| Lockfile current | `uv lock --check` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types (only if the repo already runs one) | `uv run mypy .` / `uv run pyright` — `ty` is still 0.0.x beta, run it only where the repo does |
| Tests | `uv run pytest` |
| Build | `uv build --no-sources` |
| Metadata | `uvx --from twine==7.0.0 twine check --strict dist/*` |
| Wheel imports | `uv run --isolated --no-project --with dist/*.whl python -c "import <pkg>"` |

`uv build` has no `--check`; the twine and import lines are the equivalent.
`validate-pyproject` (`uvx validate-pyproject==0.26 pyproject.toml`) is
optional and useful once, when the metadata was last touched by hand.

## Other version-bearing files

A hand-maintained `__version__` (prefer
`importlib.metadata.version("pkg")` and delete the constant), `docs/conf.py`
(`release =`), `CITATION.cff`, a README install line pinned to a version.
`release_state.py` lists the mentions.

## Tag and GitHub release

Tag `vX.Y.Z` — the default of release-please (`include-v-in-tag`),
python-semantic-release, and uv's reference workflow (glob
`v[0-9]+.[0-9]+.[0-9]+`); match the repo's existing prefix, which
`release_state.py` reports as `tag_prefix`. A pre-release version (`a`,
`b`, `rc`) gets `gh release create --prerelease`.

## PyPI (only when the project publishes, or the user says PyPI)

Publishing is a tag-triggered workflow, never a command in a session:

- Trigger on the tag push; a `build` job (`uv build`, upload the `dist/`
  artifact, smoke-test the wheel) and a separate `publish` job with
  `environment: pypi` (required reviewers on the environment),
  `permissions: id-token: write`, and either
  `pypa/gh-action-pypi-publish@release/v1` (v1.14.x; PEP 740 attestations on
  by default) or `astral-sh/attest-action` followed by `uv publish`.
- Trusted publishing needs the publisher registered on PyPI for that repo,
  workflow file, and environment name. No `UV_PUBLISH_TOKEN` in the repo.
- `uv publish --check-url https://pypi.org/simple/<pkg>/` makes a re-run
  skip files already uploaded, so a retried workflow is idempotent.
- TestPyPI first: `[[tool.uv.index]] name = "testpypi" url =
  "https://test.pypi.org/simple/" publish-url =
  "https://test.pypi.org/legacy/" explicit = true`, then
  `uv publish --index testpypi`.

What the PR body says here: which workflow the tag will trigger, or that
the package does not publish.
