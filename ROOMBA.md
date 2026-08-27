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
| 4 | `error-edges` | 2026-08-27 | 2026-09-10 |
| 5 | `test-flakiness` | never | due now |
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

### 2026-08-27 — `error-edges`

Report: [`roomba/reports/2026-08-27-error-edges.md`](roomba/reports/2026-08-27-error-edges.md)

Nine findings across `scripts/`, `install.sh`, `mcp-wiki-server/`,
`eval-suite/` and the skill scripts, each reproduced against a scratch copy of
`6181c31`. Two shapes dominate.

*Messages that never reach anyone.* `build_manifest.py`, `build_routers.py` and
`check_descriptions.py` all raise `ValueError` with sentences written for a
contributor, and none of their `main()` functions catch it — so the repo's
most-hit CI failure ("Manifest in sync") prints a six-frame traceback instead.
`install.sh`'s agent converter is worse: `except Exception: sys.exit(1)`
discards the reason, the caller prints `WARN failed to convert <path>
(skipping)` with no detail, and the install still exits 0 with one of the two
promised subagents missing.

*Failures that change results silently.* `eval-suite/run.sh` sends `setup.R`'s
stderr to `/dev/null`, then runs the task anyway — a broken setup and a genuine
model failure are indistinguishable in `results.csv`, which is the one thing
the harness exists to compare. `churn.py` counts an unreadable file as one
"gone from the tree". One dangling `*.md` symlink makes every call on a wiki
topic raise `FileNotFoundError`, table of contents included.

Report-only by catalogue rule; nothing changed. Five of the nine are a handful
of lines each and need no behavioural decision. Also recorded four boundaries
that are already handled well (`check_plugins.py`'s JSON reads,
`utils.load_eval_set`, `churn.run_git`, the wiki server's `page=` traversal
guard) so a later run does not re-litigate them.
