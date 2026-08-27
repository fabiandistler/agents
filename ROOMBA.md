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
| 6 | `security-footguns` | 2026-08-27 | 2026-09-10 |
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
