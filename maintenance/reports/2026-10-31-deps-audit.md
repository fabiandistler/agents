# deps-audit - 2026-10-31

Result: **4 updates available, 0 advisories, 0 findings that need an issue.** No tool
coverage from the scanner (see below); the list comes from the manual analogues named in
`MAINTENANCE.md`.

## Scope and coverage

`scripts/maintenance-scan.sh deps-audit` finds no `DESCRIPTION`, `renv.lock`,
`pyproject.toml` or `requirements.txt`, so it returned only its changelog hint and
"Dependabot is configured". Empty pre-stage means no tooling coverage, not "nothing found".
Versions were read from PyPI and `git ls-remote --tags` on 2026-10-31; changelogs were read
from the upstream `CHANGELOG`/`changelog.rst` files on raw.githubusercontent.com.

Dependabot (`.github/dependabot.yml`) still covers `github-actions`, weekly, grouped. Action
tags are not re-checked here.

## Updates

| Pin | Current | Latest | Risk | Decision |
|---|---|---|---|---|
| `prek` (check_all.requirements.txt) | 0.5.5 | 0.5.9 | low: 0.5.6-0.5.9 add builtin hooks and performance work, one stashing bug fix; no breaking entry | upgrade now |
| `pytest` (same file) | 9.1.1 | 9.2.0 | low, tested: breaking entries are `-c` path validation and keyword-only `indirect`/`ids`/`scope` in `parametrize`; no use of either here (`git grep` finds no `indirect=`, `ids=`, `scope=` in parametrize calls, no `-c`, no ini file). Full suite on 9.2.0: 284 passed, 13 subtests | upgrade now |
| `pyyaml` | 6.0.3 | 6.0.3 | none | current |
| ruff hook `.pre-commit-config.yaml` | v0.16.10 | v0.17.3 | low, tested: 0.17.0 changes the default Python version, the default rule set (DTZ rules off, F406 on) and the CLI fix display. `ruff.toml` sets `target-version = "py310"` and only `extend-select = ["S"]`. `ruff check .` and `ruff format --check .` give identical output on 0.16.10 and 0.17.3: the same 3 findings and 2 unformatted files, all in the vendored `test/bats/bats-core/docs/`, which prek's hook does not lint | upgrade now |
| `ty-pre-commit` | v0.0.84 | v0.0.95 | risk unverified: not run against the repo; ty is 0.0.x and its diagnostics change between releases | upgrade in a separate PR, run `ty` first |
| `shellcheck-py` | v0.11.0.1-1 | v0.11.0.1-1 | none | current |
| `pre-commit-hooks` | v6.0.0 | v6.0.0 | none | current |
| `shfmt` hook | v3.14.1-1 | v3.14.1-1 | none | current |
| `gitleaks` hook | v8.30.1 | v8.30.1 | none | current |
| `test/bats/*` submodules | core v1.14.0, assert v2.2.4, support v0.3.0 | same | none | current |

The ruff behavior notes are against the 0.17.0 changelog entries "Update the default and
latest Python versions", "Update the default rule set" and "Always show unsafe and
display-only fixes".

## Advisories

None found. There is no scanner coverage for the pinned tools; no advisory database was
queried for `prek`, `pytest` or `pyyaml` beyond reading their changelogs.

## Recommendations

- Bump `prek`, `pytest` and the ruff hook in one dependency PR. Evidence above shows
  check status is unchanged. Not done here: this job delivers only the report.
- Check `ty` v0.0.95 locally before bumping its rev.
- Dependabot covers actions only; widening it to `pip` for `check_all.requirements.txt`
  would take over the two Python pins. That is the owner's call, not filed as an issue.

## Baseline

`scripts/check_all.sh`, 23 PASS, 0 failed, 0 missing, before the run (the hook ran by hand
as MAINTENANCE.md describes; gitleaks needed no skip). No code was changed.
