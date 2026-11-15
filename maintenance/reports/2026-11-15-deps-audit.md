# deps-audit - 2026-11-15

Result: **4 tool updates available (all tested, low risk), 0 advisories, 2 vendor locks
reported `behind`: one re-vendored in this PR, one a false `behind` from the check itself.**
2 findings need an issue (below). No tooling coverage from the scanner; the list comes from
the manual analogues named in `MAINTENANCE.md`.

## Scope and coverage

`scripts/maintenance-scan.sh deps-audit` (both the vendored copy at `4d851e0` and the
re-vendored one at `884a179`) prints `[skipped]` for the R and Python package audit: this
repo has no `DESCRIPTION`, `pyproject.toml` or `requirements.txt`. That means no tooling
coverage, not "nothing found". The re-vendored scanner adds the Dependabot update-run
check; it printed no `[finding]`: the newest completed Dependabot update run
(43563336916, 2026-11-14) ended `success`. Dependabot (`.github/dependabot.yml`) still
covers `github-actions`, weekly, grouped; action tags are not re-checked here.

Versions were read from PyPI and `git ls-remote --tags` on 2026-11-15; changelogs from the
upstream files on raw.githubusercontent.com (`j178/prek` `CHANGELOG.md`,
`astral-sh/ruff` `CHANGELOG.md`, `astral-sh/ty` `CHANGELOG.md`).

## Updates

| Pin | Current | Latest | Risk | Decision |
|---|---|---|---|---|
| `prek` (`scripts/check_all.requirements.txt`) | 0.5.5 | 0.5.10 | low, tested: 0.5.6-0.5.10 add builtin hooks, performance work and Node download fixes; no breaking entry. 0.5.7 "Update CA root crates and uv for the eMudhra intermediate CA compromise" (j178/prek#2919) is a trust-store fix this repo's pin lacks. `prek run --all-files` on 0.5.10: all hooks pass | upgrade now (second report in a row) |
| `pytest` (same file) | 9.1.1 | 9.2.0 | low, tested: breaking entries reviewed in the 2026-10-31 report, unchanged. Full suite on 9.2.0: 2221 passed, 8 skipped, 36 subtests | upgrade now (second report in a row) |
| `pyyaml`, `zizmor` (same file) | 6.0.3, 1.32.0 | same | none | current |
| ruff hook (`.pre-commit-config.yaml`) | v0.17.3 | v0.17.5 | low, tested: 0.17.4-0.17.5 are bug fixes, preview rules and rule changes to `B008`/`SIM102`, neither selected by `ruff.toml` (default set + `S`). `ruff check` and `ruff format --check` give identical output on both versions (the same 3 findings and 2 files, all in the vendored `test/bats/bats-core/docs/`) | upgrade now |
| `ty-pre-commit` | v0.0.95 | v0.0.104 | low, tested: 0.0.97, 0.0.100 and 0.0.102 rename rules (e.g. `unresolved-import` -> `import-not-found`); `git grep` finds no `ty: ignore` comment and `ty.toml` names no rule. `ty check` (with pyyaml, pytest) passes on both versions | upgrade now |
| `shellcheck-py`, `pre-commit-hooks`, `shfmt`, `gitleaks` hooks | v0.11.0.1-1, v6.0.0, v3.14.1-1, v8.30.1 | same | none | current |
| `test/bats/*` submodules | core v1.14.0, assert v2.2.4, support v0.3.0 | same | none | current |

## Vendor locks

| Lock | `--check-upstream` | Action |
|---|---|---|
| `vendor/repo-maintenance/lock.json` | exit 5, `behind`: locked `4d851e0`, upstream `main` `884a179` | Re-vendored in this PR at `884a179` (`python3 scripts/vendor_repo_maintenance.py --ref 884a179...`). Only `scripts/maintenance-scan.sh` changed: upstream f7c5a7e, 455f4fc, b2e76ee, 5913efc. `scripts/check_all.sh` after the re-vendor: 26 PASS, same as the baseline |
| `.claude/vendor/mattpocock-skills/lock.json` | exit 5, `behind`: locked `4ae2317`, tag v1.3.2 `d1478fc` | **Not re-vendored.** The lock is *ahead* of the tag, not behind: `git merge-base --is-ancestor d1478fc 4ae2317` holds (tag commit 2026-10-29, locked commit 2026-10-31). A re-vendor at the tag fails with exit 3 (`in-progress skill missing upstream at d1478fcb140d: software-factory`). See finding 1 |

## Findings

### 1. `check_upstream` reports a lock ahead of the target as `behind`

- Where: `scripts/vendoring.py:97`: `status = "current" if target_commit == locked_commit else "behind"`.
- Evidence: the mattpocock-skills lock was vendored at `4ae2317`, a commit after the newest
  release tag v1.3.2 (`d1478fc`), because `INCLUDED_IN_PROGRESS` needs `software-factory`,
  which does not exist at the tag. `--check-upstream` still prints `behind` and exits 5, and
  `MAINTENANCE.md` tells a run to re-vendor at the printed commit, which would be a downgrade
  and fails with exit 3. Every `deps-audit` run until v1.3.3 hits this.
- Proposal: in `check_upstream`, distinguish `ahead` (target is an ancestor of the locked
  commit) from `behind`, e.g. via the GitHub compare API or a shallow fetch of both commits,
  and give `ahead` its own exit code that `MAINTENANCE.md` maps to "no action". Also
  consider whether the lock's `version: 1.3.2` should say it is past the tag.

### 2. Four check-tool pins are behind (prek, pytest second time)

- Where: `scripts/check_all.requirements.txt` (`prek==0.5.5`, `pytest==9.1.1`),
  `.pre-commit-config.yaml` (ruff `v0.17.3`, ty `v0.0.95`).
- Evidence: table above, each tested against this repo with unchanged results. prek and
  pytest were already "upgrade now" in the 2026-10-31 report and were not bumped; prek
  0.5.7's CA-root update makes its bump more than routine.
- Proposal: one dependency PR bumping all four; or let Dependabot own them by adding a
  `pip` entry for `scripts/` and a `pre-commit` ecosystem entry, so this job stops carrying
  plain update work.

## No issue needed

- `issue_comment` workflows without `author_association` (jobs.md one-off check):
  `.github/workflows/claude.yml`, `issue-triage.yml`, `factory-issue-triage.yml`. Each is
  gated otherwise: `claude.yml` relies on claude-code-action stopping actors without write
  access (comment at its trigger); the triage pair accepts only the issue's reporter on a
  `needs-info` issue (`factory-issue-triage.yml:82-85`) and lets only issues by people with
  write access reach the model (`scripts/issue_triage_policy.py`). Leave as is.

## Advisories

None found. No advisory database covers the pinned tools here; none was queried beyond
the changelogs above.

## Baseline

`scripts/check_all.sh`, 26 PASS, 0 failed, 0 missing, before the run (hook run by hand as
`MAINTENANCE.md` describes; gitleaks built, no `SKIP`). After the re-vendor: 26 PASS.
