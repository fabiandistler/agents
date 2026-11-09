# dead-exports - 2026-11-09

Baseline before: `scripts/check_all.sh` on `main` at 741575c, 25 of 25 checks PASS, 0 failed,
0 missing. Run on WSL, so ruff's `EXE001`-`EXE003` are not covered locally; CI decides those.
No tracked file changed apart from this report and the run record, so the check status is
identical by construction.

**Tooling coverage:** `scripts/maintenance-scan.sh dead-exports` exited 3 (`Nothing to scan.`):
the repo has no `DESCRIPTION`, `pyproject.toml` or `requirements.txt`. That means no tooling
coverage, not "nothing found". The checks below use the analogue named in `MAINTENANCE.md`:
skills present in `skills/` but not reachable via `skills.json`, a router, or `.claude-plugin/`.

## Result: 0 findings

| Check | Evidence | Outcome |
|---|---|---|
| Skills with a `SKILL.md` vs `skills.json` paths | set comparison, both directions | 30 = 30, no orphan, no stale entry |
| Top-level skills vs `plugins/*/skills/<name>` symlinks | resolved every symlink under `plugins/` | 21 linked directly, no broken link |
| The other 9 (`architecture-pattern-advisor`, `c4-modeling`, `coupling-cohesion`, `ddd`, `fitness-functions`, `logical-component-design`, `microservices-design` -> router `architecture`; `llm-application-engineering`, `ml-project-lifecycle` -> router `ai-ml`) | `skills/<router>/members/<name>/SKILL.md` resolves for all 9; `git grep "members/<name>/SKILL.md" -- 'skills/*/SKILL.md'` lists the router for each | each is reached through its router; both routers are linked into their plugins |
| `plugins/*` vs `.claude-plugin/marketplace.json` | every plugin directory looked up by name | 8 of 8 listed |

Nothing is removed. The route into those 9 members runs through the routers, which is
intended.

## Checked and ruled out

`skills/skill-creator` is the one directory under `skills/` without a `SKILL.md`. It is not a
finding: `git ls-files skills/skill-creator` is empty and `git status --ignored` reports it as
ignored. It holds only `__pycache__` files left in this local checkout after the skill was
removed in ffe7cdc (2026-09-01), so it does not exist in the repository.

`.claude/skills/` holds 26 directories with no counterpart in `skills/`. They are the vendored
Matt Pocock skills pinned in `.claude/vendor/mattpocock-skills/lock.json`, and outside this
job's analogue.
