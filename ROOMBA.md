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
| 3 | `dead-code` | 2026-08-27 | 2026-09-10 |
| 4 | `error-edges` | never | due now |
| 5 | `test-flakiness` | never | due now |
| 6 | `security-footguns` | never | due now |
| 7 | `perf-quickwins` | never | due now |

**Next job to run: `error-edges` (#4)** — never run, and the lowest-numbered of
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

### 2026-08-27 — `dead-code`

Four removals, each backed by a reference search across the whole tree
(`git grep` for the identifier; counted against its definition sites):

1. `eval-suite/recall/check_recall.py` — `score()` built
   `valid = {e["name"] for e in menu}` and then discarded it via
   `_ = valid  # (kept for future strict-menu validation)`. The `_ =` binding
   is exactly what kept ruff's F841 quiet. No other reference to `valid` in
   the file; removed both lines.
2. `skills/coupling-cohesion/scripts/lcom.py` — `_r_oo_report(path, src,
   oo_spans)` never reads `path`. Private helper (leading underscore) with one
   call site, `analyze_r()` line 305; dropped the parameter at both ends.
3. `scripts/test_install.sh` — `with_fake_home()` was defined at line 14 and
   never called. `grep -c '\bwith_fake_home\b'` over the repo returns 1, the
   definition itself. Every test in the file sets up its own `mktemp -d` HOME
   inline; the helper has been unused since it was introduced.
4. `eval-suite/import_vitals.R` — `title_to_pretty()` likewise defined and
   never called; the importer writes `title: <slug>` straight into task.yaml.

Verification: `ruff check .` clean, `python -m compileall` clean,
`bash -n scripts/test_install.sh` clean, `scripts/test_install.sh` passes end
to end (all 38 assertions), `check_recall.py --dry-run` prints the same menus
as before (20 flat / 11 routed entries), and `lcom.py` produces identical
output on an R fixture exercising both the R6 class path and the file path.

Nothing behavioural: no branch, no output, and no public entry point changed.
