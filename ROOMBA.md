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
| 5 | `test-flakiness` | never | due now |
| 6 | `security-footguns` | never | due now |
| 7 | `perf-quickwins` | 2026-08-27 | 2026-09-26 |

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

### 2026-08-27 — `perf-quickwins`

Report: [`roomba/reports/2026-08-27-perf-quickwins.md`](roomba/reports/2026-08-27-perf-quickwins.md)

Six findings, every number measured on `6181c31` — best-of-7 for wall clock,
exact IO counts from patching `pathlib.Path.read_text` and shimming `grep` on
`PATH`. Two are worth acting on; the report says so plainly rather than dressing
up the other four.

**F1 — `install.sh` forks 219 greps for one `--target=all` run.** Five
frontmatter helpers each launch `grep -m1` against the same `SKILL.md`, nothing
caches, and the main loop re-asks per (target, skill) pair. Attributed: 384 ms
of the 875 ms run is those forks (44%), against 3.3 ms for the same 219 answers
read in-process. Grows as skills × targets. One `awk` pass into an associative
array fixes it without changing a single helper signature, and
`test_install.sh` already covers the behaviour.

**F2 — the wiki table of contents reads every page in full to take one line.**
Measured over a realistic 61-page corpus: 523,633 bytes read to produce 1,038
bytes of first lines, **504× amplification**, per call, uncached — and this is
the no-argument call an agent makes to see what a topic holds. Fix is to iterate
the file object and break; it composes with the `error-edges` job's F4, which
wants a guarded read on that exact loop.

**F3 — CI launches Python 25 times to validate 25 files** (1055 ms, 42 ms each,
against 11 ms bare startup), and runs `quick_validate.py` a *second* time for a
failing skill purely to recover the message the first run discarded to
`/dev/null`. The two-line capture-once fix is strictly better.

F4-F6 are read amplification in the check scripts (`check_plugins.py` 3× per
`SKILL.md`, `check_docs.py` 2×, `build_routers.py` re-parsing `skills.json` per
category) and a linear scan in `check_recall.py`. All are real, none is worth a
PR: those scripts run in ~30 ms, mostly interpreter startup. Reported as scaling
and duplication notes — four separate implementations of "parse this frontmatter
field" now exist while `build_manifest.py` exports a real parser two of the
scripts already import. Should ride along with unrelated work on those files.

Report-only by catalogue rule. Also recorded five hot paths that are already
right (`churn.py`'s single `git log` pass and single-buffer `measure()`,
`lcom.py`'s one-parse-per-file, the manifest being read once everywhere except
F6) so a later run does not re-open them.
