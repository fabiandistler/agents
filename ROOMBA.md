# ROOMBA — maintenance catalogue

<!--
Source: prompt idea Fabian Distler, 2026-09-01, processed with skill `idee-zu-artefakt`.
Execution: plugin `roomba`, skill `roomba-run`.
Review date: 2026-12-01 — see teardown condition below.
Translated from the German template to match this repository's English convention;
job IDs, cooldowns and the scoring rule are unchanged.
-->

## Status

| Field | Value |
|---|---|
| Last run | 2026-09-28 (`deps-audit`) |
| Last job | `deps-audit` — 6 findings, 0 version bumps; no pin is outdated |
| Next due job | see *Jobs* table — `score = (today - last run) / cooldown`, highest wins |
| Baseline status | green, 2026-09-28 (14/14, captured from `ci.yml`, not the block below) |
| Open roomba PRs | see `gh pr list --state open --search "head:roomba/"` |

## Rules

1. **Exactly one job per run.**
2. **Job selection by relative overdueness:** `score = (today - last_run) / cooldown`.
   Highest score wins, `-` counts as infinity, ties break by catalogue order.
   Reason: selecting by absolute date would let a 7-day job eat every slot.
3. **A job with an open roomba PR is skipped** and counts as in progress.
4. **Every run ends in exactly one PR** on `roomba/<job>-<YYYY-MM-DD>`, report-only jobs
   included. No commit on the default branch.
5. **Diff budget < 300 lines.** The remainder goes under *Backlog*.
6. **Behaviour is never changed.** Edits are limited to documentation, dead exports and
   test infrastructure — and only when the check status is identical before and after.

## What does NOT belong in this catalogue

Anything a tool answers conclusively belongs in the CI gate, not in an agent run. A job
that keeps finding nothing while CI is green only burns rotation slots.

| Previously considered a job | Runs in CI instead |
|---|---|
| security-footguns | `roomba-gate` → gitleaks |
| dead-code (local vars/imports) | `ci.yml` → `ruff check .` |

What remains in the catalogue is the residual question only: `dead-exports` (an export
across the package boundary).

## Baseline

This repository is neither an R package nor a Python package, so `R CMD check` and
`pytest` do not apply. The baseline is the check sequence from `.github/workflows/ci.yml`,
which must be captured **before** each run and reproduced identically afterwards:

```bash
python scripts/build_manifest.py --check
python scripts/build_routers.py --check
python scripts/check_descriptions.py
python scripts/check_docs.py
python scripts/check_plugins.py
for d in skills/*/; do [ -f "$d/SKILL.md" ] && python3 scripts/quick_validate.py "$d"; done
uvx ruff@latest check .
python -m compileall -q scripts skills
uvx --from shellcheck-py shellcheck -S warning \
  install.sh scripts/test_install.sh scripts/roomba-scan.sh
bash scripts/test_install.sh
```

Use `uvx ruff@latest`, not whatever `ruff` is on `PATH` — `ci.yml` installs the newest
ruff too, and a stale local copy would falsify the baseline comparison. Note which
version the baseline resolved to (`uvx ruff@latest --version`) and reproduce the run
with that exact `ruff@X.Y.Z`, so a release landing mid-run cannot read as a finding.

On a WSL host ruff reports none of the `flake8-executable` rules (`EXE001`-`EXE003`),
whatever the file's real mode — measured on this repo's ext4 checkout, where the bits
are correct and the same ruff version flags 13 files in CI. A local baseline is blind
to them, so `ci.yml` decides them alone: never report "ruff is clean" from WSL.

Red or missing baseline → report-only jobs, no code changes.

## Preconditions per run

- Working tree clean, on the default branch, `git fetch` done.
- Baseline captured (see above) **before** the run, status recorded.
- Red or missing baseline → report-only jobs.

## Jobs

| # | Job | Pre-stage | Output | Cooldown | Last run |
|---|---|---|---|---|---|
| 1 | `deps-audit` | yes | report | 7d | 2026-09-28 |
| 2 | `doc-drift` | no | PR | 14d | 2026-09-05 |
| 3 | `dead-exports` | yes | PR | 14d | 2026-09-06 |
| 4 | `error-edges` | no | report | 14d | 2026-09-06 |
| 5 | `test-flakiness` | yes | PR | 30d | 2026-09-06 |
| 6 | `perf-quickwins` | no | report | 30d | 2026-09-06 |

Residual question per job (details in the skill under `references/jobs.md`):

1. **deps-audit** — will these updates break me? The scanner supplies the list, the run
   supplies breaking-change risk from changelogs actually read, plus a recommendation.
2. **doc-drift** — does the documentation still describe what the code does? Proven by
   executing the examples. Only documentation is touched.
3. **dead-exports** — is this export across the package boundary really dead? Evidence per
   removal: git grep, NAMESPACE/`__all__`, vignettes, reverse deps, `git log -S`.
4. **error-edges** — where does the code swallow an error silently? Report, no PR.
5. **test-flakiness** — is the time/random/network dependency intentional? Only the source
   of non-determinism is replaced, never the assertion.
6. **perf-quickwins** — measurably slow or merely ugly? No measurement, no finding.

## Repository-specific notes on the pre-stages

`scripts/roomba-scan.sh` keys off `DESCRIPTION` (R) and `pyproject.toml` /
`requirements.txt` (Python) **at the repository root**, where this repository has none of
them. All three pre-stages therefore return empty here. The 2026-09-05 `deps-audit` run
attributed that to the scanner's root-only search, citing `mcp-wiki-server/pyproject.toml`
one level down; the 2026-09-28 run retired that reading — `eval-suite/` and
`mcp-wiki-server/` have both been extracted into their own repositories (PRs #147, #148),
and no `pyproject.toml` is tracked anywhere, at the root or below it. The root-only search
remains a general scanner limitation, but it is no longer what makes the pre-stage empty
here. A run must still treat an empty pre-stage as "no tooling coverage" rather than
"nothing found", and say so in the report instead of inventing findings by hand.

The catalogue-relevant analogues in this repository are:

| Job | What it means here |
|---|---|
| `deps-audit` | the pinned `rev:` values, which exist in two places — `.pre-commit-config.yaml` and the fragments under `skills/prek-hooks/references/fragments/` that the skill ships to other repos — plus the unpinned `pip install` lines in `.github/workflows/ci.yml` (`ruff` deliberately, per `ee36b79`; `prek` and `pytest` incidentally) and the `pyyaml>=6` floor. Action tags are Dependabot's (`.github/dependabot.yml`), so a run should confirm that config still covers them rather than re-checking each tag by hand |
| `dead-exports` | skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/` |
| `test-flakiness` | the `pytest` fixture files under `skills/*/scripts/test_*.py` |

## Backlog

- **No `--check` keeps the prek pins in sync across their two copies.** From the
  2026-09-28 `deps-audit` run (finding 3): `pre-commit-hooks`, `ruff-pre-commit` and
  `ty-pre-commit` are each pinned twice — in the generated `.pre-commit-config.yaml` and in
  `skills/prek-hooks/references/fragments/`, which is what the skill hands to other repos.
  The documented update path (`prek update --cooldown-days 7`, per the config header and
  `setup-hooks.sh:107`) rewrites the generated file only. They agree today. Every other
  generated surface here has a gate (`build_manifest.py --check`, `build_routers.py
  --check`, `check_docs.py`, `check_plugins.py`, `check_instructions.py`); this one does
  not. Stakes: `ty` 0.0.84 exists to close an arbitrary-code-execution advisory
  (GHSA-vxvm-j4xq-q7m4), so the next advisory moves this repo's pin and leaves the shipped
  fragment handing new repos the unpatched rev. A new script plus a CI step is a behaviour
  change, so it was out of scope for a report-only job.
- **`prek` is unpinned in `ci.yml:66`** and feeds the blocking *Hooks in sync* step, while
  prek v0.5.0 (2026-08-27) removed `auto-update`, `init-template-dir` and
  `PREK_MAX_CONCURRENCY`. The 2026-09-28 run confirmed no tracked file uses a removed name,
  so nothing is broken; unlike ruff's unpinning (`ee36b79`) no decision is recorded for
  `prek`. Pin it the first time the gate fails for no reproducible reason.
- **ROOMBA.md's *What does NOT belong in this catalogue* table is false for
  `security-footguns`.** It routes the job to `roomba-gate → gitleaks`, but
  `roomba-gate.yml` was deliberately deleted in `58fc561`, so there is no secret scanning
  on `main`. Either restore a gate or drop the claim — restoring a deliberately removed
  workflow is a decision, not maintenance. Recorded by the 2026-09-28 run.
- **ROOMBA.md's *Baseline* block is short of `ci.yml`.** It lists ten commands and omits
  `check_instructions.py`, `check_evals.py`, the `release-pr` pytest file and `prek run
  --all-files`. The 2026-09-28 run captured its baseline from `ci.yml` instead. Sync the
  block or replace it with a pointer to the workflow.
- **`.pre-commit-config.yaml`'s comment prescribes `select`** for pinning the ruff rule
  set, where `ruff.toml` correctly uses `extend-select`. Documentation drift, so it belongs
  to `doc-drift`. Noted by the 2026-09-28 run.
- **Adapt `scripts/roomba-scan.sh` to this repository.** Add a skills-repo branch to
  `deps-audit` (the two-copy `rev:` surface and the unpinned `pip install` lines), to
  `dead-exports` (catalogued but unrouted skills), and to `test-flakiness` (discover
  `skills/*/scripts/test_*.py`, not just a repo-root `tests/`). Deferred out of the
  bootstrap PR: it is a change to the scanner, not catalogue setup. Narrowed by the
  2026-09-28 run — the earlier "must also search below the root" framing is retired, since
  no manifest exists below the root either.
- **Four of the five triage labels in `docs/agents/triage-labels.md` do not exist** in
  `fabiandistler/agents` (`gh label list`: only `wontfix` is there). Recorded by the
  2026-09-05 `doc-drift` run rather than fixed: creating them changes the tracker, and
  the alternative — rewording the doc — is a different decision. Pick a direction.
- **Decide whether `dead-exports` survives the 2026-12-01 review.** The 2026-09-06 run
  found every tracked skill reachable, and CI (`build_routers --check`, `check_docs.py`,
  `check_plugins.py`) already fails on an unrouted tracked skill — a CI-gate question under
  *What does NOT belong in this catalogue*. The only thing the gate cannot see is an
  untracked leftover under `skills/`, which is what the run did find. Narrow the job to
  that, or drop it.
- **`lcom.py` analyses git-ignored directories.** Measured by the 2026-09-06
  `perf-quickwins` run: `lcom.py --json .` takes 4.5 s and emits 607 KB / 1921 module
  reports, of which 1271 come from a `.venv` and 517 from a `.worktrees` checkout; a scoped
  run takes 115 ms and emits 8. Pruning changes which modules appear in the output, so it
  is a behaviour change and out of scope for a roomba PR. It degrades the
  `cohesion-analyst` subagent's input, so it is worth doing deliberately.
- **Eval coverage gap** carried over from the 2026-07 skill audit — candidate input for
  `test-flakiness` once that job's pre-stage sees this repo's test locations.

Retired by the 2026-09-28 `deps-audit` run, because the code they describe was extracted
into its own repositories (PRs #147, #148) and is no longer tracked here: the `eval-suite/*.R`
dependency question, the `check_live.py` silent-CLI-failure fix and the `check_recall.py`
single-sample item (both issue #95), and the `import_vitals.R` ARE-task miscount. The
`.serena/` item is retired too — the directory no longer exists.

## Run history

| Date | Job | Output | PR |
|---|---|---|---|
| 2026-09-05 | *(bootstrap)* | catalogue + scanner + CI gate | roomba/init-2026-09-05 |
| 2026-09-05 | `deps-audit` | report, 7 findings, 0 changes | roomba/deps-audit-2026-09-05 |
| 2026-09-05 | `doc-drift` | 7 findings, 6 doc fixes (12+/7-) | roomba/doc-drift-2026-09-05 |
| 2026-09-06 | `dead-exports` | 3 findings, 1 catalogue fix | roomba/dead-exports-2026-09-06 |
| 2026-09-06 | `error-edges` | report, 3 findings, 0 changes | roomba/error-edges-2026-09-06 |
| 2026-09-06 | `test-flakiness` | 4 findings, 1 fix (pinned ARE ref) | roomba/test-flakiness-2026-09-06 |
| 2026-09-06 | `perf-quickwins` | report, 2 findings, 0 changes | roomba/perf-quickwins-2026-09-06 |
| 2026-09-28 | `deps-audit` | report, 6 findings, catalogue map corrected | roomba/deps-audit-2026-09-28 |

## Teardown condition

Review date 2026-12-01. Fewer than four runs, or not a single merged roomba PR → fall back
to a manual checklist and uninstall the plugin.
