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
| Last run | 2026-09-06 (`error-edges`) |
| Last job | `error-edges` — 3 findings, report-only by design |
| Next due job | see *Jobs* table — `score = (today - last run) / cooldown`, highest wins |
| Baseline status | green, 2026-09-06 (all 10 commands in *Baseline* below) |
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
| dead-code (local vars/imports) | `ci.yml` → `ruff check .` (pinned 0.15.8) |

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
uvx ruff@0.15.8 check .
python -m compileall -q scripts skills mcp-wiki-server
uvx --from shellcheck-py shellcheck -S warning \
  install.sh scripts/test_install.sh scripts/roomba-scan.sh eval-suite/run.sh
bash scripts/test_install.sh
```

Use the pinned `ruff@0.15.8`, not whatever `ruff` is on `PATH`. A newer ruff reports
pre-existing findings in first-party files and would falsify the baseline comparison —
`ci.yml` pins for the same reason.

Red or missing baseline → report-only jobs, no code changes.

## Preconditions per run

- Working tree clean, on the default branch, `git fetch` done.
- Baseline captured (see above) **before** the run, status recorded.
- Red or missing baseline → report-only jobs.

## Jobs

| # | Job | Pre-stage | Output | Cooldown | Last run |
|---|---|---|---|---|---|
| 1 | `deps-audit` | yes | report | 7d | 2026-09-05 |
| 2 | `doc-drift` | no | PR | 14d | 2026-09-05 |
| 3 | `dead-exports` | yes | PR | 14d | - |
| 4 | `error-edges` | no | report | 14d | 2026-09-06 |
| 5 | `test-flakiness` | yes | PR | 30d | - |
| 6 | `perf-quickwins` | no | report | 30d | - |

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
them; its tests likewise live at `skills/skill-creator/tests`, not at the root. All three
pre-stages therefore return empty here today. Corrected by the 2026-09-05 `deps-audit` run:
`mcp-wiki-server/pyproject.toml` does exist one level down and declares an `mcp[cli]` bound — the
gap is the scanner's root-only search, not an absence of package metadata. Until the scanner is adapted (see *Backlog*), the run must treat
an empty pre-stage as "no tooling coverage", not as "nothing found" — and say so in the
report rather than inventing findings by hand.

The catalogue-relevant analogues in this repository are:

| Job | What it means here |
|---|---|
| `deps-audit` | pinned versions in `.github/workflows/ci.yml` (`ruff==0.15.8`, `pyyaml>=6`), `mcp-wiki-server/pyproject.toml` (`mcp[cli]>=1.2,<2`), and pinned `rev:` values in any pre-commit config. Action tags are Dependabot's (`.github/dependabot.yml`), so a run should confirm that config still covers them rather than re-checking each tag by hand |
| `dead-exports` | skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/` |
| `test-flakiness` | the eval harness under `eval-suite/` and `skills/skill-creator/tests` |

## Backlog

- **Adapt `scripts/roomba-scan.sh` to this repository.** Add a skills-repo branch to
  `deps-audit` (pinned CI versions and action tags), to `dead-exports` (catalogued but
  unrouted skills), and to `test-flakiness` (discover test directories below
  `skills/*/tests` and `eval-suite/`, not just repo-root `tests/`). Deferred out of the
  bootstrap PR: it is a change to the scanner, not catalogue setup.
  Sharpened by the 2026-09-05 `deps-audit` run: the `deps-audit` pre-stage must also search
  below the root — `mcp-wiki-server/pyproject.toml` was missed, and the dependency it declares
  turned out to be the run's second-most-severe finding.
- **`eval-suite/*.R` dependencies are outside the catalogue's scope.** `digest`, `jsonlite`,
  `lintr`, `testthat`, `withr`, `yaml` — no `renv.lock`, no floors, and absent from the
  "what `deps-audit` means here" table above. Recorded as a gap by the 2026-09-05 run rather
  than audited. Decide whether they belong in `deps-audit` before the next run of that job.
- **Four of the five triage labels in `docs/agents/triage-labels.md` do not exist** in
  `fabiandistler/agents` (`gh label list`: only `wontfix` is there). Recorded by the
  2026-09-05 `doc-drift` run rather than fixed: creating them changes the tracker, and
  the alternative — rewording the doc — is a different decision. Pick a direction.
- **`check_live.py` silent-CLI-failure fix**, from the 2026-09-06 `error-edges` run: the
  harness reports a nonzero `claude` exit as a routing miss. A fix changes behaviour, so it
  is out of scope for a roomba PR — it belongs to issue #95, whose cause 3 is the same
  failure mode. Fix it before any eval-coverage work relies on those numbers.
- **Eval coverage gap** carried over from the 2026-07 skill audit — candidate input for
  `test-flakiness` once that job's pre-stage sees this repo's test locations.
- **`.serena/` is untracked** and trips precondition 1 ("working tree clean") on every
  run. Adding it to `.gitignore` is a change to a tracked file unrelated to bootstrap, so
  it was deliberately left out of this PR.

## Run history

| Date | Job | Output | PR |
|---|---|---|---|
| 2026-09-05 | *(bootstrap)* | catalogue + scanner + CI gate | roomba/init-2026-09-05 |
| 2026-09-05 | `deps-audit` | report, 7 findings, 0 changes | roomba/deps-audit-2026-09-05 |
| 2026-09-05 | `doc-drift` | 7 findings, 6 doc fixes (12+/7-) | roomba/doc-drift-2026-09-05 |
| 2026-09-06 | `error-edges` | report, 3 findings, 0 changes | roomba/error-edges-2026-09-06 |

## Teardown condition

Review date 2026-12-01. Fewer than four runs, or not a single merged roomba PR → fall back
to a manual checklist and uninstall the plugin.
