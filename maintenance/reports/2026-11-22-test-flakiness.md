# test-flakiness - 2026-11-22

Job: `test-flakiness` (score 1.20, cooldown 30d). Baseline `scripts/check_all.sh`: 0 failed,
0 missing (gitleaks ran; no `SKIP`). Started from `main` at `4a4e942`.

Result: no finding. No test in scope depends on wall-clock time, randomness, real network or
real sleeps, so this run changes no test.

## Scanner (`scripts/maintenance-scan.sh test-flakiness`, exit 0)

Time, randomness, seeds, mocking and sleep/timing: `none`. Six network candidates, all
dismissed after reading them:

| Candidate | Why it is not a network dependency |
|---|---|
| `test/install_opencode.bats:150` | prose in a heredoc agent fixture ("opens pull requests"), matched on the word "opens" |
| `test/factory_repo_setup.bats:162`, `:324`, `:348-349`, `:360` | expected URL strings in assertions; `gh` is a stub that fails on any unexpected call (line 53) and the browser is a `wslview` stub writing to `$BROWSER_LOG` (lines 56-57) |

## Pytest files (outside the scanner's reach, checked by hand)

109 `test_*.py` files under `scripts/` and `skills/*/scripts/`, grepped for `time.time()`,
`datetime.now/today/utcnow`, `date.today`, `random.`, `uuid4`, `time.sleep`, `urlopen`,
`requests.`, `httpx`, `socket` and remote `git`/`gh`/`curl` calls:

- `scripts/test_factory_failure.py`: the code under test takes an injected `today` and `sleep`;
  the tests pass `today="2026-11-13"` (line 119) and record sleeps in a list (lines 218-229).
- `scripts/test_skill_audit_select.py`: fixed dates everywhere, `--date 2027-02-08` for the CLI
  (line 111), commit dates set explicitly.
- `scripts/test_retro_counter.py`: times built from a fixed `FLOOR` with `timedelta`.
- `skills/refactoring/scripts/test_churn.py`: `git clone --no-local` of a local fixture repo
  (line 151); `--since` uses fixed dates except one test that only asserts exit 0 for the
  documented relative forms (line 107), which holds on any date.
- All `secrets.` matches are `${{ secrets.* }}` workflow strings, and `random.py` in
  `test_pr_risk_paths.py:136` is a path fixture.

Production code that reads the clock (`factory_failure.py:275`, `skill_audit_select.py:132`,
`churn.py:386`, `maintenance-new-deps.py:391`) reads it only as a default the tests override,
or for output no test asserts on.
