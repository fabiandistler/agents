# dead-exports - 2026-10-10

Baseline before: partial - only the seven `scripts/` checks ran (green); ruff, pytest, shellcheck, prek and install test were not run because no file they cover changed. No tracked file
changed apart from this report and `MAINTENANCE.md`, so check status is identical by
construction.

**Tooling coverage:** `scripts/maintenance-scan.sh dead-exports` returned only its evidence
checklist. The repo has no `DESCRIPTION`, `NAMESPACE` or `pyproject.toml`, and
`git grep __all__ -- '*.py'` finds nothing, so no scanner ran. The check below uses the
analogue named in `MAINTENANCE.md`: skills present in `skills/` but not reachable via
`skills.json`, a router, or `.claude-plugin/`.

## Result: 0 findings

| Check | Evidence | Outcome |
|---|---|---|
| `skills/*` dirs vs `skills.json` entries | set comparison, both directions | 27 = 27, no orphan, no stale entry |
| Top-level skills vs `plugins/*/skills/<name>` symlinks | loop over `skills/*/` | 17 linked directly |
| The other 10 (`adr-workflow`, `architecture-pattern-advisor`, `c4-modeling`, `coupling-cohesion`, `ddd`, `fitness-functions`, `logical-component-design`, `microservices-design` -> router `architecture`; `llm-application-engineering`, `ml-project-lifecycle` -> router `ai-ml`) | `git grep "members/<name>/SKILL.md" -- 'skills/*/SKILL.md'` | each is referenced by its router; routers are linked into `plugins/architecture` and `plugins/ai-ml` |
| `.claude-plugin/marketplace.json` | lists the plugins that carry the routers and skills | consistent |

Nothing is removed. The route into those 10 members runs through the routers, which is
intended.
