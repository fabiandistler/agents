# deps-audit - 2026-10-08

Baseline before and after: green, 14/14 (`MAINTENANCE.md` *Baseline*), ruff 0.16.10.
No code changed, so the status is identical by construction.

**Tooling coverage:** `scripts/maintenance-scan.sh deps-audit` returned only its changelog
prompt and "Dependabot is configured". The repo has no `DESCRIPTION`, `pyproject.toml`,
`requirements.txt` or `uv.lock`, so no vulnerability scanner ran. The findings below come from
the pinned `rev:` values read by hand, as `MAINTENANCE.md` describes.

## Findings

Cooldown rule: `prek update --cooldown-days 7` ignores releases younger than 7 days.

| # | Pin (both copies unless noted) | Latest | Released | Decision |
|---|---|---|---|---|
| 1 | `ruff-pre-commit` v0.16.9 | v0.16.10 | 2026-10-01 (7d) | upgrade now |
| 2 | `ty-pre-commit` v0.0.84 | v0.0.85 | 2026-10-06 (2d) | leave open until 2026-10-13 |
| 3 | `air-pre-commit` 0.11.0 (fragment `r.yaml` only) | 0.12.0 | 2026-10-01 (7d) | upgrade now, low risk |
| 4 | `pre-commit-hooks` v6.0.0, `shellcheck-py` v0.11.0.1-1, `shfmt` v3.14.1-1, `jarl` 0.6.0, `precommit` v0.4.3.9032 | same | - | current |

1. **ruff v0.16.10.** The release notes list preview rules (`UP052`, preview-only), a
   diagnostics memory reduction, a server fix and docs (ruff `CHANGELOG.md`, section 0.16.10).
   No stable rule change, so no new findings in a repo that is clean today. Check: `uvx ruff@0.16.10 check .`
   passes on this tree. Migration effort: bump two lines.
2. **ty v0.0.85.** Crash and recursion fixes, a CLI `@`-path change and an opt-in rule (ty
   `CHANGELOG.md`, 0.0.85). Released 2 days ago, inside the repo's 7-day cooldown, so not
   recommended yet. Not a security release. The advisory GHSA-vxvm-j4xq-q7m4 is already closed
   by 0.0.84.
3. **air 0.12.0.** Adds `--no-configuration` and formats `data.table::rowwiseDT()` as tables
   (air `CHANGELOG.md`, 0.12.0). The second item can reformat R files in repos that
   use it, so it is a formatting-only change for consumers. Reachability: the pin is shipped to other
   repos by the `prek-hooks` skill, not run here (no R code in this repo).
4. **Bump mechanics.** Findings 1-3 touch two files each for the shared hooks
   (`.pre-commit-config.yaml` plus `skills/prek-hooks/references/fragments/*.yaml`). The two
   copies have no sync check (see *Backlog* in `MAINTENANCE.md`), so a bump must edit both. Not done here:
   this job delivers a report only.

## CI inputs (`.github/workflows/ci.yml`)

| Input | Pin | Latest on PyPI/GitHub | Note |
|---|---|---|---|
| `ruff` | unpinned (deliberate, `ee36b79`) | 0.16.10 | unchanged |
| `prek` | unpinned | 0.5.5 (2026-10-05) | Changelog 0.5.1-0.5.5 read: the only breaking changes are in 0.5.0 (`auto-update`, `init-template-dir`, `PREK_MAX_CONCURRENCY` removed). `git grep` finds none of them in tracked files and the *Hooks in sync* step passed in this run. Backlog item stays as is |
| `pytest` | unpinned | 9.1.1 | baseline pytest run passed |
| `pyyaml` | `>=6` | 6.0.3 | floor still satisfiable |
| `actions/checkout`, `actions/setup-python` | `@v7` | v7.0.1 | floating tag, covered by `.github/dependabot.yml` (`github-actions`, weekly, grouped) |

Dependabot config still covers the action tags. It deliberately does not cover the pip lines or
the `rev:` pins.

## One-off check: `issue_comment` triggers

`.github/workflows/claude.yml` triggers on `issue_comment` and has no `author_association`
check. The job `if:` only tests that the comment contains `@claude`. It holds
`id-token: write` and the `CLAUDE_CODE_OAUTH_TOKEN` secret. Whether an arbitrary commenter
can run it depends on `anthropics/claude-code-action@v1` rejecting actors without write
access. This run did not verify that behavior. The repo owner should confirm it from the action's
documentation, or add an `author_association` condition to the `if:`.
