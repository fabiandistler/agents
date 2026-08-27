# ROOMBA — maintenance catalogue

A rotating set of small, bounded maintenance jobs for this repository. One
agent run executes **exactly one** job, then updates the log at the bottom of
this file and names the next job that is due.

## Rules

- **One job per run.** Never batch two jobs into one run.
- **Output type is fixed per job.** A `Report` job never opens a pull
  request; a `PR` job never stops at prose.
- **PR jobs branch as `roomba/<job>-<YYYY-MM-DD>`**, one branch per run.
- **Keep PRs small: under 300 lines of diff.** If the finding set is larger,
  ship the highest-value slice and note the remainder in the run log.
- **Never change behaviour.** The only jobs allowed to touch runtime
  behaviour at all are `doc-drift`, `dead-code`, and `test-flakiness`, and
  even there the change must be provably behaviour-preserving (a removal
  backed by a reference search, a test made deterministic, a doc corrected).
  `security-footguns` is report-only by design — it never patches.
- **Every claim needs evidence.** A version number, a command that was run,
  a reference search that came back empty. No "looks unused".
- **Every run updates the log**: the job's *last run* date and the *next due*
  job.
- Reports live in `roomba/reports/<YYYY-MM-DD>-<job>.md`.

## Catalogue

| # | Job | What it looks for | Output | Cooldown |
|---|-----|-------------------|--------|----------|
| 1 | `deps-audit` | Outdated or vulnerable dependencies; recommendation per finding with its breaking-change risk | Report | 7d |
| 2 | `doc-drift` | README, vignettes, and docstrings that no longer match actual behaviour | PR | 14d |
| 3 | `dead-code` | Unused functions, exports, and imports — each removal backed by a reference search | PR | 14d |
| 4 | `error-edges` | API and IO boundaries with no error handling, or with errors silently swallowed | Report | 14d |
| 5 | `test-flakiness` | Tests depending on wall-clock time, randomness, or the network | PR | 30d |
| 6 | `security-footguns` | Hardcoded paths, suspected secrets, injection edges, unsafe defaults | **Report only** | 14d |
| 7 | `perf-quickwins` | Obvious N+1 patterns and copy orgies (in R: needless `data.frame` copies where `data.table` reference semantics apply) | Report | 30d |

## Schedule

A job is *due* when `today >= last run + cooldown`. A job that has never run
is always due. When several jobs are due, take the one that has gone longest
without a run; ties break by catalogue order.

| # | Job | Last run | Next due |
|---|-----|----------|----------|
| 1 | `deps-audit` | 2026-08-25 | 2026-09-01 |
| 2 | `doc-drift` | never | due now |
| 3 | `dead-code` | never | due now |
| 4 | `error-edges` | never | due now |
| 5 | `test-flakiness` | 2026-08-27 | 2026-09-26 |
| 6 | `security-footguns` | never | due now |
| 7 | `perf-quickwins` | never | due now |

**Next job to run: `doc-drift` (#2)** — never run, and the lowest-numbered of
the jobs still tied at "never".

## Run log

### 2026-08-25 — `deps-audit`

Report: [`roomba/reports/2026-08-25-deps-audit.md`](roomba/reports/2026-08-25-deps-audit.md)

Seven findings, one of them breaking today: `mcp-wiki-server` declares
`mcp[cli]>=1.2` with no upper bound, and mcp 2.0.0 removed
`mcp.server.fastmcp`, so a fresh install of the wiki server fails at import.
Reproduced and verified against both 2.1.0 and 1.29.1. No code changed — this
is a report job.

Branch note: this run was pushed to `claude/roomba-deps-audit-6f8r6o` rather
than `roomba/deps-audit-2026-08-25`, because the branch was pinned by the
session that bootstrapped this catalogue. Later runs follow the naming rule
above.

### 2026-08-27 — `test-flakiness`

Both of the repo's test suites reach into the *shared* system temp directory
and assume it behaves like private scratch space. Two fixes, one per suite.

**`test_eval_set_validation.py::test_rejects_a_missing_file` failed on the
contents of `/tmp`.** It called
`load_eval_set(Path(tempfile.gettempdir()) / "definitely-missing-eval-set.json")`
and asserted the read raises — i.e. it bet that no other process on the machine
had ever written that exact name. Reproduced on `6181c31` by creating the file
and running the suite:

    AssertionError: EvalSetFormatError not raised
    Ran 5 tests in 0.002s
    FAILED (failures=1)

The path now lives inside the test's own `TemporaryDirectory`, so "missing" is
a fact the test controls. Re-run under the same condition (the `/tmp` file
still present): 5 tests, OK.

Same class, same cause: `_write()` called `tempfile.mkdtemp()` per invocation
and never cleaned up, so every run left four directories in that same shared
namespace. Moved to one `TemporaryDirectory` per test via `addCleanup`, with a
counter in the filename so repeated `_write()` calls in one test stay distinct
(`test_rejects_the_two_level_object_shape` asserts on the exact path, so the
name has to stay predictable).

**`scripts/test_install.sh` leaked 29 directories per run.** It builds a
throwaway `$HOME` with `mktemp -d` for nearly every assertion — 30 call sites —
and deleted none of them. Measured on `6181c31`: `/tmp` went from 57 entries to
86 across a single run. `TMPDIR` now points at one root the script owns, so all
30 land inside it, and an `EXIT` trap removes that root — but only on success,
so a red CI run stays inspectable and says where the tree is.

Verification: 37 skill-creator unit tests pass; `scripts/test_install.sh`
passes end to end with `/tmp` unchanged at 57 entries before and after;
`ruff check .` and `bash -n scripts/test_install.sh` clean. No assertion was
weakened, added, or removed — `test_rejects_a_missing_file` still exercises
exactly the `OSError` path in `utils.load_eval_set`.

Checked and found clean: nothing in either suite depends on wall-clock time,
randomness, or the network. `test_aggregate_benchmark.py` reads only committed
fixtures; the `timeout=1` arguments in `EntryPointValidationTest` are never
reached, since validation raises before any subprocess starts; every
`$INSTALL` invocation in `test_install.sh` sets its own `HOME`.
