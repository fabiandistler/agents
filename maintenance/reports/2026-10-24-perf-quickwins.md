# perf-quickwins - 2026-10-24

Result: **0 findings.** No pattern in this repository is measurably slow.

## Scope and coverage

There is no scanner for this job and the repository has no R code and no pandas/data.frame
code. The Python (62 files, `scripts/` and `skills/*/scripts/`) was searched with
`git grep` for `pd.concat`, `.apply(`, `iterrows`, `subprocess.run` / `check_output`,
`read_text()` and `glob(` outside tests.

## Candidates examined

| Location | Pattern | Verdict |
|---|---|---|
| `scripts/skill_audit_select.py:97,47` | `git log` subprocess | Two calls per run, not per skill. Constant. |
| `skills/refactoring/scripts/churn.py` `run_git` | `git` subprocess | Calls are sequential setup steps plus one `git log`; none in a per-file loop. |
| `skills/release-pr/scripts/release_state.py:292` `last_tag` | loop over tags | One `git tag --list`, then a regex loop that exits at the first match. O(tags), no subprocess inside. |
| `scripts/check_*.py` | `sorted(glob/rglob)` over `skills/` | Each script runs in at most 0.15 s wall time (measured, `skill_refs` slowest). |

Measurement: every `scripts/check_*.py` was timed from the repository root; the slowest
is `check_skill_refs.py` at 0.15 s. The slow checks in `scripts/check_all.sh` are
`install-smoke` (about 100 s) and `mermaid` (about 15 s). Both are external-process bound
(install, `npx`), not a code pattern this job judges.

## Baseline

`scripts/check_all.sh` before the run: 19 PASS, `pytest` MISSING (not installed; the
install attempt did not provide it), `prek` failed (it could not download its Go toolchain
through the proxy). Missing is not green, so the run is report-only, which this job is anyway.
No code was changed.
