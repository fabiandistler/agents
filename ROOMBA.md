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
| 4 | `error-edges` | 2026-08-27 | 2026-09-10 |
| 5 | `test-flakiness` | 2026-08-27 | 2026-09-26 |
| 6 | `security-footguns` | 2026-08-27 | 2026-09-10 |
| 7 | `perf-quickwins` | 2026-08-27 | 2026-09-26 |

**Next job to run: `deps-audit` (#1)** — every job has now run; `deps-audit`
is the only one past its cooldown (7d from 2026-08-25).

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

*Merge note (2026-09-01):* the `skill-creator` skill was removed from the repo
after this run, so the `test_eval_set_validation.py` half of the fix no longer
has a file to apply to and was dropped when this branch was merged up to
`main`. The `scripts/test_install.sh` fix is unaffected and stands.

### 2026-08-27 — `security-footguns`

Report: [`roomba/reports/2026-08-27-security-footguns.md`](roomba/reports/2026-08-27-security-footguns.md)

Seven findings. Nothing here handles credentials, so the interesting surface is
elsewhere: this repo's outputs get *fed to agents and opened in browsers*, and
two places put content the operator did not write somewhere it is trusted. Both
were reproduced.

**F1 — the wiki cache is `/tmp/mcp-wiki-cache` and `cache.exists()` is the only
check.** The path does not depend on `WIKI_GIT_URL`, nothing verifies the
directory is a clone of it (or a git repo at all), and a failed refresh
deliberately serves whatever is there. A plain directory planted at that path is
served as the wiki with the configured URL never contacted — reproduced against
a nonexistent remote, output `- joins.md — # planted`. On a multi-user host that
is one `mkdir` in `/tmp` to write an agent's reference material. Without an
adversary the same shape silently serves a stale wiki forever after the URL
changes.

**F2 — `generate_viewer.R` splices model output into a `<script>` block.**
`payload$…$solution` is the verbatim `solution.R` the CLI under test produced;
JSON escaping covers `"` and `\` but not `<` or `/`, so a solution containing
`</script>` closes the element early. Reproduced against the real
`viewer.html.template`: the first `</script>` the browser sees is the one inside
the payload, `DATA` is never assigned, and the injected element runs when the
maintainer opens `viewer.html`. The template's DOM code is careful — all
`textContent`, no `innerHTML` — but that care is defeated at HTML-parse time.
Fix is three `gsub` calls to `\uXXXX`-escape `< > &`.

Also: F3 the hardcoded `/home/user/agents` paths in `.mcp.json.example` (handed
over by the 2026-08-25 `deps-audit` run — the same-day `doc-drift` run left it
alone deliberately, since the fix is the config, not the prose); F4 `meta.json`
built by string interpolation; F5 no `permissions:` block in CI; F6 `pyyaml>=6`
unpinned in a workflow that pins ruff on principle; F7 the recall check passing
its prompt on argv where `coder_cli_invoke` two directories away uses stdin.

Report-only by design — this job never patches. Recorded six boundaries that
are already sound (the `page=` traversal guard, the `--` guard on `git clone`,
`install.sh`'s TOML name validation and marker discipline, no secrets in the
tree, `coder_cli_invoke`'s backend allowlist) so a later run does not
re-litigate them.

*Method note:* R is not installed here, so F2's serialization step was
reproduced with an equivalent JSON serializer rather than `jsonlite` itself.
The claim rests on the RFC 8259 escape set, which `jsonlite` implements and
offers no option to widen; worth re-confirming with `Rscript` where available.

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
