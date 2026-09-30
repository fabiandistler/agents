# MAINTENANCE - maintenance catalog

<!--
Source: prompt idea by Fabian Distler, 2026-09-01, developed with skill `idee-zu-artefakt`.
Run by: plugin `repo-maintenance`, skill `maintenance-run`.
Review date: 2026-12-01 - see sunset condition below.
Bootstrapped fresh on 2026-09-28, replacing `ROOMBA.md` (the same catalog under the
plugin's former naming, from `repo-maintenance` v0.1.0 / skill `roomba-run`). Seven runs
of history, six reports and a ten-item backlog were deliberately discarded with it; they
remain in git history (`git show 58fc561^:ROOMBA.md`, `git log -- roomba/`) and in closed
PR #412. Two findings were carried forward into *Backlog* below.
-->

## Status

| Field | Value |
|---|---|
| Last run | 2026-09-28 *(bootstrap - no job was run)* |
| Last job | - |
| Next due job | `deps-audit` (no job has run against this catalog -> catalog order) |
| Baseline status | green, 2026-09-28, 14/14 (see *Baseline*) |
| Open maintenance PRs | see `gh pr list --state open --search "head:maintenance/"` |

## Rules

1. **Exactly one job per run.**
2. **Job choice by relative overdueness:** `score = (today - last_run) / cooldown`.
   Highest score wins, `-` counts as infinite, ties go to catalog order.
   Reason: picking by absolute date, a 7-day job would take every slot.
3. **A job with an open maintenance PR is skipped** and counts as in progress.
4. **Every run ends in exactly one PR** on `maintenance/<job>-<YYYY-MM-DD>`, report-only jobs
   too. No commit to the default branch.
5. **Diff budget < 300 lines.** The rest goes under *Backlog*.
6. **Behavior is never changed.** Changes only to docs, dead exports, and test
   infrastructure - and only with identical check status before and after the run.

## What does NOT belong in this catalog

Anything a tool answers conclusively belongs in the CI gate, not in an agent run. A job that
regularly finds nothing when CI is green only burns rotation slots.

| Once planned as a job | Runs in CI instead |
|---|---|
| security-footguns | `maintenance-gate` -> gitleaks; ruff `S113` via `ruff.toml` |
| dead-code (local vars/imports) | `ci.yml` -> `ruff check .` (`F401`/`F841` are in the default set) |

Only the open question stays in the catalog: `dead-exports` (exports across the package boundary).

## Preconditions per run

- Clean working tree, on the default branch, `git fetch` has run.
- Baseline recorded **before** the run - see *Baseline* below. This repo is neither an R
  package nor a Python package, so `R CMD check` and `pytest` do not apply as written.
- Red or missing baseline -> report jobs only.

## Baseline

The baseline is the check sequence from `.github/workflows/ci.yml`, captured before the
run and reproduced identically afterwards:

```bash
python scripts/build_manifest.py --check
python scripts/build_routers.py --check
python scripts/check_descriptions.py
python scripts/check_docs.py
python scripts/check_plugins.py
python scripts/check_instructions.py
python scripts/check_evals.py
for d in skills/*/; do [ -f "$d/SKILL.md" ] && python3 scripts/quick_validate.py "$d"; done
uvx ruff@latest check .
python -m compileall -q scripts skills
uvx --with pyyaml pytest scripts skills
uvx --from shellcheck-py shellcheck -S warning \
  install.sh scripts/test_install.sh scripts/maintenance-scan.sh
uvx prek run --all-files
bash scripts/test_install.sh
```

Fourteen checks. Two standing caveats:

- Use `uvx ruff@latest`, not whatever `ruff` is on `PATH`: `ci.yml` installs the newest
  ruff too, so a stale local copy falsifies the comparison. Record the version the
  baseline resolved to and reproduce the run with that exact `ruff@X.Y.Z`, so a release
  landing mid-run cannot read as a finding.
- On a WSL host ruff reports none of the `flake8-executable` rules (`EXE001`-`EXE003`)
  whatever the file's real mode - measured on this repo's ext4 checkout, where the bits
  are correct and the same ruff version flags 13 files in CI. A local baseline is blind to
  them, so `ci.yml` decides them alone: never report "ruff is clean" from WSL.

## Jobs

| # | Job | Scanner | Output | Cooldown | Last run |
|---|---|---|---|---|---|
| 1 | `deps-audit` | yes | Report | 7d | - |
| 2 | `doc-drift` | no | PR | 14d | - |
| 3 | `dead-exports` | yes | PR | 14d | - |
| 4 | `error-edges` | no | Report | 14d | - |
| 5 | `test-flakiness` | yes | PR | 30d | - |
| 6 | `perf-quickwins` | no | Report | 30d | - |

Open question per job (details in the skill under `references/jobs.md`):

1. **deps-audit** - Will these updates break me? The scanner delivers the list, the run
   delivers breaking-change risk from changelogs it has read, and a recommendation.
2. **doc-drift** - Do the docs still describe what the code does? Proven by running the
   examples. Only docs are touched.
3. **dead-exports** - Is this export really dead across the package boundary? Evidence per
   removal: git grep, NAMESPACE/`__all__`, vignettes, reverse deps, `git log -S`.
4. **error-edges** - Where does the code swallow an error silently? Report, no PR.
5. **test-flakiness** - Is the time, randomness, or network dependency intentional? Only the
   source of nondeterminism is replaced, never the assertion.
6. **perf-quickwins** - Measurably slow, or just ugly? No measurement, no finding.

## Notes on the pre-stages in this repository

`scripts/maintenance-scan.sh` keys off `DESCRIPTION` (R) and `pyproject.toml` /
`requirements.txt` (Python) **at the repository root**, and this repo has none of them, at
the root or below it. All three pre-stages therefore return empty here. A run must treat an
empty pre-stage as "no tooling coverage", not as "nothing found", and say so in the report
instead of inventing findings by hand.

The catalog-relevant analogues in this repository are:

| Job | What it means here |
|---|---|
| `deps-audit` | the pinned `rev:` values, which exist in two places - `.pre-commit-config.yaml` and the fragments under `skills/prek-hooks/references/fragments/` that the skill ships to other repos - plus the unpinned `pip install` lines in `.github/workflows/ci.yml` (`ruff` deliberately, per `ee36b79`; `prek` and `pytest` incidentally) and the `pyyaml>=6` floor. Action tags are Dependabot's (`.github/dependabot.yml`), so a run should confirm that config still covers them rather than re-checking each tag by hand |
| `dead-exports` | skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/` |
| `test-flakiness` | the `pytest` fixture files under `skills/*/scripts/test_*.py` |

## Backlog

Carried over from the 2026-09-28 `deps-audit` run (closed PR #412) when this catalog
replaced `ROOMBA.md`. Everything else from that catalog's backlog was discarded on purpose
and is recoverable from git history.

- **No `--check` keeps the prek pins in sync across their two copies.**
  `pre-commit-hooks`, `ruff-pre-commit` and `ty-pre-commit` are each pinned twice: in the
  generated `.pre-commit-config.yaml` and in `skills/prek-hooks/references/fragments/`,
  which is what the `prek-hooks` skill hands to other repos. The documented update path
  (`prek update --cooldown-days 7`, per the config header and `setup-hooks.sh:107`)
  rewrites the generated file only. They agree today. Every other generated surface here
  has a gate behind it (`build_manifest.py --check`, `build_routers.py --check`,
  `check_docs.py`, `check_plugins.py`, `check_instructions.py`); this one does not. Stakes:
  `ty` 0.0.84 exists to close an arbitrary-code-execution advisory (GHSA-vxvm-j4xq-q7m4),
  so the next advisory moves this repo's pin and leaves the shipped fragment handing new
  repos the unpatched rev. A new script plus a CI step is a behavior change, so it was out
  of scope for a report-only job.
- **`prek` is unpinned in `ci.yml`** and feeds the blocking *Hooks in sync* step, while
  prek v0.5.0 (2026-08-27) removed `auto-update`, `init-template-dir` and
  `PREK_MAX_CONCURRENCY`. The 2026-09-28 run confirmed no tracked file uses a removed name,
  so nothing is broken; unlike ruff's unpinning (`ee36b79`) no decision is recorded for
  `prek`. Pin it the first time the gate fails for no reproducible reason.

## Run history

| Date | Job | Output | PR |
|---|---|---|---|
| 2026-09-28 | *(bootstrap)* | catalog + scanner + gitleaks gate; `ROOMBA.md` and its history removed | maintenance/init-2026-09-28 |

## Sunset condition

Review date 2026-12-01. Fewer than four runs or not a single merged maintenance PR ->
replace with a manual checklist and uninstall the plugin.
