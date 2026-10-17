# test-flakiness - 2026-10-17

Baseline before: the seven `scripts/` checks green, `uvx ruff@0.17.1 check .` clean,
`pytest scripts skills` 96 passed. shellcheck, prek and the install test were not run
because no file they cover changed. No tracked file changed apart from this report and
`MAINTENANCE.md`, so check status is identical by construction.

**Tooling coverage:** `scripts/maintenance-scan.sh test-flakiness` returned only "no tests/
or test/ directory found", so no scanner ran. The check below greps the pytest files named
in `MAINTENANCE.md` (`scripts/test_*.py`, `skills/*/scripts/test_*.py`, 11 files).

## Result: 0 findings

Pattern searched: `time.time`, `datetime.now/utcnow`, `random`, `sleep`, `urlopen`,
`requests.`, `uuid`, `tempfile`, `mktemp`, `GIT_*_DATE`, `--since`, `os.environ`.

| Candidate | Evidence | Outcome |
|---|---|---|
| clock / randomness / sleep | no match in any test file | none present |
| network | only literal URL strings (`test_loop.py:34-35,197,206`, `test_release_state.py:28`) passed as data to parsers; no HTTP client call | not a network dependency |
| `skills/refactoring/scripts/test_churn.py` real-time git commits with `--since` | fixed `--since 2020-01-01` for value assertions; the relative forms (`12 months ago`, `yesterday`, ...) at line 89 assert only the exit code | not time-sensitive |
| `NamedTemporaryFile(delete=False)` in `test_balance_check.py:22`, `test_coupling_metrics.py:22` | leaks temp files, but each run gets a unique name | not nondeterministic; cleanup is not this job's remit |

Nothing is changed. The cooldown (30d) starts when this PR is merged.
