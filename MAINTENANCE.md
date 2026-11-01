# MAINTENANCE - maintenance catalog

<!--
Source: prompt idea by Fabian Distler, 2026-09-01, developed with skill `idee-zu-artefakt`.
Run by: plugin `repo-maintenance`, skill `maintenance-run` - an external Claude Code
plugin, not part of this repository; its `references/jobs.md` holds the job details.
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
| Last run | 2026-10-31 |
| Last job | `deps-audit` (report-only, 4 updates available, 0 advisories, PR pending merge) |
| Next due job | `doc-drift` (last run 2026-10-08, cooldown 14d) |
| Baseline status | The current check list is `scripts/check_all.sh --list`. The last run (2026-10-17) recorded its baseline in its report under `maintenance/reports/`; do not read an old report as today's status |
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
  package nor a Python package: there is no `R CMD check` step, and the `pytest` check
  runs the tests that live next to the scripts under `scripts/` and `skills/`, not a
  package test suite.
- Red or missing baseline -> report jobs only.

## Baseline

The baseline is `scripts/check_all.sh`, the same entry point CI calls, captured before the
run and reproduced identically afterwards (`scripts/check_all.sh --list` names the checks).
Tool versions are pinned in `scripts/check_all.requirements.txt` and
`.pre-commit-config.yaml`; ruff runs as a prek hook at the version pinned there. A check
reported `MISSING` counts as not run, never as green.

In a cloud session the check tools come from `.claude/hooks/session-start.sh`, which runs
only when the session starts inside this checkout. A routine with several repositories
starts in `/home/user`, so the hook never runs: `pytest` reports `MISSING`, and prek's
`gitleaks` hook fails trying to fetch Go from the blocked `go.dev` (routine run of
2026-10-28). Run the hook once by hand from the checkout root before the baseline, then
source its env file in every shell that runs a check, because each tool call starts a
fresh shell:

```bash
CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$PWD" \
  CLAUDE_ENV_FILE="$HOME/.cache/agents-check-tools.env" .claude/hooks/session-start.sh
. "$HOME/.cache/agents-check-tools.env" && scripts/check_all.sh
```

`git push` is one of those shells: the pre-push hooks run `scripts/check_all.sh` with the
`python3` on `PATH`. From an unsourced shell that is the image's interpreter without
`pytest`, so the hook reports `MISSING pytest` and rejects the push. Push with
`. "$HOME/.cache/agents-check-tools.env" && git push …`; never fall back to
`git push --no-verify`.

Do not `pip install` the tools into the image's Python instead; the hook's venv is the
path that keeps them where `check_all.sh` looks. If the hook logs `MISSING go`, it then
exits non-zero at `prek install-hooks`, its last step, after the venv and the Bats
submodules are in place. That is expected: run the baseline and every commit with
`SKIP=gitleaks` (`. "$HOME/.cache/agents-check-tools.env" && SKIP=gitleaks
scripts/check_all.sh`), which keeps prek from building the hook, and say so in the
report. The gitleaks job of `maintenance-gate` still scans every pull request in CI.

One standing caveat:

- On a WSL host ruff reports none of the `flake8-executable` rules (`EXE001`-`EXE003`)
  whatever the file's real mode - measured on this repo's ext4 checkout, where the bits
  are correct and the same ruff version flags 13 files in CI. A local baseline is blind to
  them, so CI decides them alone: never report "ruff is clean" from WSL.

## Jobs

| # | Job | Scanner | Output | Cooldown | Last run |
|---|---|---|---|---|---|
| 1 | `deps-audit` | yes | Report | 7d | 2026-10-31 |
| 2 | `doc-drift` | no | PR | 14d | 2026-10-08 |
| 3 | `dead-exports` | yes | PR | 14d | 2026-10-10 |
| 4 | `error-edges` | no | Report | 14d | 2026-10-13 |
| 5 | `test-flakiness` | yes | PR | 30d | 2026-10-17 |
| 6 | `perf-quickwins` | no | Report | 30d | 2026-10-24 |

Open question per job (details in the external `repo-maintenance` skill's `references/jobs.md`):

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

`scripts/maintenance-scan.sh` and the two helpers it calls
(`scripts/maintenance-r-advisories.py`, `scripts/maintenance-new-deps.py`) are vendored
from [fabiandistler/repo-maintenance](https://github.com/fabiandistler/repo-maintenance)
(`plugins/repo-maintenance/assets/`). `vendor/repo-maintenance/lock.json` pins the
upstream commit and each file's sha256 and git mode. To update, run

```sh
python3 scripts/vendor_repo_maintenance.py --ref <commit>
```

and commit the three files and `vendor/repo-maintenance/LICENSE` together with the lock.
Scanner fixes go upstream, then a re-vendor brings them here: the `vendor-lock` check in
`scripts/check_all.sh` fails on any local edit or mode change. `--check` compares the files
against the lock offline. It does not compare the lock against upstream, so after a merge
conflict in `lock.json`, re-vendor instead of hand-merging.

These hooks skip the vendored files: `ruff-check`, `ruff-format` and `ty` skip the two
Python helpers (`ruff.toml`, `ty.toml`), and `shellcheck` and `shfmt` skip the scanner
(`.pre-commit-config.yaml`). `trailing-whitespace` and `end-of-file-fixer` still run on all
three, as they do upstream.

The scanner keys off `DESCRIPTION` (R) and `pyproject.toml` / `requirements.txt` (Python)
**at the repository root**, and this repo has none of them, at the root or below it. What
each pre-stage covers here:

- `deps-audit` exits 0 and prints `[skipped] no DESCRIPTION, pyproject.toml or
  requirements.txt -> R and Python package audit`; it only checks that Renovate or
  Dependabot is configured.
- `dead-exports` exits 3 (`Nothing to scan.`).
- `test-flakiness` scans `test/`: this repo's Bats suites, without the vendored Bats
  libraries under `test/bats/`. The pytest files under `scripts/` and `skills/*/scripts/`
  are outside its reach.

The `[skipped]` package audit and the `dead-exports` exit 3 mean "no tooling coverage", not
"nothing found". A run says so in the report and works through the analogue below by hand
instead of inventing findings.

The catalog-relevant analogues in this repository are:

| Job | What it means here |
|---|---|
| `deps-audit` | the pinned `rev:` values in `.pre-commit-config.yaml` and the pins in `scripts/check_all.requirements.txt` (prek, pytest, pyyaml), and the release tags the `test/bats/` submodules are checked out at (Dependabot would move them to branch heads, so they stay manual). Action tags are Dependabot's (`.github/dependabot.yml`), so a run should confirm that config still covers them rather than re-checking each tag by hand. Read each changelog from the upstream file on `raw.githubusercontent.com` (`https://raw.githubusercontent.com/<owner>/<repo>/<branch>/CHANGELOG.md`), which a cloud session can fetch (routine run of 2026-10-31: pytest, prek, ruff); its GitHub access may refuse third-party repositories ("GitHub access to this repository is not enabled for this session"), so do not depend on release pages. Only if the raw file cannot be read either, the report marks the update "risk unverified: changelog not readable in this session" instead of estimating a risk from the version number |
| `dead-exports` | skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/` |
| `test-flakiness` | the `pytest` fixture files under `skills/*/scripts/test_*.py` and the Bats suites `test/*.bats` |

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
| 2026-10-24 | `perf-quickwins` | report: `maintenance/reports/2026-10-24-perf-quickwins.md` (0 findings) | maintenance/perf-quickwins-2026-10-24 |
| 2026-10-31 | `deps-audit` | report: `maintenance/reports/2026-10-31-deps-audit.md` (4 updates, 0 advisories) | maintenance/deps-audit-2026-10-31 |

## Sunset condition

Review date 2026-12-01. Fewer than four runs or not a single merged maintenance PR ->
replace with a manual checklist and uninstall the plugin.
