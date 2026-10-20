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
| Last run | 2026-10-17 |
| Last job | `test-flakiness` (report-only, 0 findings, PR pending merge) |
| Next due job | `perf-quickwins` (no run yet -> catalog order) |
| Baseline status | 2026-10-17: 9 of 14 checks run, all green (7 `scripts/` checks, ruff 0.17.1, pytest 96 passed); shellcheck, prek, install test not run |
| Open maintenance PRs | open PRs whose head branch starts with `maintenance/` (command below the table) |

List open PRs, keeping those whose head branch starts with `maintenance/`. Use
the GitHub MCP tools if the session has them; otherwise `gh api` (REST; `gh pr
list` is GraphQL-backed and fails in cloud sessions):

```bash
gh api "repos/{owner}/{repo}/pulls?state=open&per_page=100" --jq '.[] | select(.head.ref | startswith("maintenance/")) | [.number, .head.ref, .title] | @tsv'
```

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
| dead-code (local vars/imports) | `ci.yml` -> `scripts/check_all.sh` -> prek's `ruff-check` hook (`F401`/`F841` are in the default set) |

Only the open question stays in the catalog: `dead-exports` (exports across the package boundary).

## Preconditions per run

- Clean working tree, on the default branch, `git fetch` has run.
- Baseline recorded **before** the run - see *Baseline* below. This repo is neither an R
  package nor a Python package, so `R CMD check` and `pytest` do not apply as written.
- Red or missing baseline -> report jobs only.

## Baseline

The baseline is `scripts/check_all.sh`, the same entry point CI calls, captured before the
run and reproduced identically afterwards (`scripts/check_all.sh --list` names the checks).
Tool versions are pinned in `scripts/check_all.requirements.txt` and
`.pre-commit-config.yaml`; ruff runs as a prek hook at the version pinned there. A check
reported `MISSING` counts as not run, never as green.

One standing caveat:

- On a WSL host ruff reports none of the `flake8-executable` rules (`EXE001`-`EXE003`)
  whatever the file's real mode - measured on this repo's ext4 checkout, where the bits
  are correct and the same ruff version flags 13 files in CI. A local baseline is blind to
  them, so CI decides them alone: never report "ruff is clean" from WSL.

## Jobs

| # | Job | Scanner | Output | Cooldown | Last run |
|---|---|---|---|---|---|
| 1 | `deps-audit` | yes | Report | 7d | 2026-10-08 |
| 2 | `doc-drift` | no | PR | 14d | 2026-10-08 |
| 3 | `dead-exports` | yes | PR | 14d | 2026-10-10 |
| 4 | `error-edges` | no | Report | 14d | 2026-10-13 |
| 5 | `test-flakiness` | yes | PR | 30d | 2026-10-17 |
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
| `deps-audit` | the pinned `rev:` values in `.pre-commit-config.yaml` and the pins in `scripts/check_all.requirements.txt` (prek, pytest, pyyaml). Action tags are Dependabot's (`.github/dependabot.yml`), so a run should confirm that config still covers them rather than re-checking each tag by hand |
| `dead-exports` | skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/` |
| `test-flakiness` | the `pytest` fixture files under `skills/*/scripts/test_*.py` |

## Backlog

Carried over from the 2026-09-28 `deps-audit` run (closed PR #412) when this catalog
replaced `ROOMBA.md`. Everything else from that catalog's backlog was discarded on purpose
and is recoverable from git history.

Empty: the one carry-over (unpinned `prek` in `ci.yml`) is resolved by
`scripts/check_all.requirements.txt`.

## Run history

| Date | Job | Output | PR |
|---|---|---|---|
| 2026-09-28 | *(bootstrap)* | catalog + scanner + gitleaks gate; `ROOMBA.md` and its history removed | maintenance/init-2026-09-28 |
| 2026-10-08 | `deps-audit` | report: `maintenance/reports/2026-10-08-deps-audit.md` | maintenance/deps-audit-2026-10-08 |
| 2026-10-08 | `doc-drift` | PR: README Contributing list and layout table | maintenance/doc-drift-2026-10-08 |
| 2026-10-10 | `dead-exports` | report: `maintenance/reports/2026-10-10-dead-exports.md` (0 findings) | maintenance/dead-exports-2026-10-10 |
| 2026-10-13 | `error-edges` | report: `maintenance/reports/2026-10-13-error-edges.md` (6 findings) | maintenance/error-edges-2026-10-13 |
| 2026-10-17 | `test-flakiness` | report: `maintenance/reports/2026-10-17-test-flakiness.md` (0 findings) | maintenance/test-flakiness-2026-10-17 |

## Sunset condition

Review date 2026-12-01. Fewer than four runs or not a single merged maintenance PR ->
replace with a manual checklist and uninstall the plugin.
