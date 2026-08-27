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
| 2 | `doc-drift` | 2026-08-27 | 2026-09-10 |
| 3 | `dead-code` | never | due now |
| 4 | `error-edges` | never | due now |
| 5 | `test-flakiness` | never | due now |
| 6 | `security-footguns` | never | due now |
| 7 | `perf-quickwins` | 2026-08-27 | 2026-09-26 |

**Next job to run: `dead-code` (#3)** — never run, and the lowest-numbered of
the four jobs still tied at "never".

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

### 2026-08-27 — `doc-drift`

Five documented claims that no longer matched the code, each checked against
the source it describes:

1. `mcp-wiki-server/README.md` said the git-backed wiki is "cloned shallowly
   once on first run; delete the cache dir to refresh". `resolve_wiki_root()`
   (`server.py:33-46`) has run `git pull --ff-only --quiet` on every start
   since the cache existed, falling back to the stale checkout with a stderr
   note when the pull fails. Rewrote the paragraph.
2. Same README's "Adding your own content" documented tool-name sanitizing but
   not the collision handling `register_topics()` (`server.py:113-136`) added:
   two folders that sanitize to one name no longer silently overwrite each
   other — the first wins and the rest are skipped with a stderr warning.
   Documented it.
3. `scripts/check_docs.py` named `README.md (## Contents)` as the home of the
   skill table, in both its docstring and its failure message. `## Contents` is
   the *directory* table (`| Directory | Description |`); the rows
   `README_ROW` actually matches live under `## Skill catalogue`, same as in
   AGENTS.md. Corrected both strings — the failure message is what a
   contributor follows after CI rejects a skill addition.
4. `eval-suite/README.md` gave the judge's default model as `claude-sonnet-4-5`;
   `judge.R:43` defaults `JUDGE_MODEL` to `claude-sonnet-4-20250514`.
5. `README.md` lists what `--target=codex` does beyond linking skills, but had
   only two of the three extras: it omitted the managed `[[skills.config]]`
   block in `~/.codex/config.toml` that disables nested router members
   (`install.sh:466-487`), which AGENTS.md and the `install.sh` header both
   document. Added the bullet. Also fixed the `install.sh` header's
   "`--uninstall` reverses both", left over from when the codex path installed
   MCP servers as well as subagents; only the subagents remain.

No behaviour changed: the only non-Markdown edits are two strings in
`check_docs.py` and one comment line in `install.sh`. `check_docs.py`,
`check_descriptions.py`, `check_plugins.py`, `build_manifest.py --check`,
`build_routers.py --check`, `ruff check .` and the skill-creator unit tests
all pass.

Checked and *not* changed: `docs/agents/{issue-tracker,triage-labels,domain}.md`
reference `/triage`, `/wayfinder`, `/domain-modeling`, `/grill-with-docs` and
`/improve-codebase-architecture`, none of which this repo ships. They are
config surfaces for skills installed from elsewhere, so whether they should
stay is a scope call for the maintainer, not a drift fix. Noted here as the
remainder.

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
