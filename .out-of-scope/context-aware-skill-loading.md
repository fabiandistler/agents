# Context-Aware Skill Loading

This project does not gate skill availability on the project you happen to be in,
and does not move skills behind a lookup tool. Two specific mechanisms are
rejected:

- **Part A — project-fingerprint activation.** `project_markers` in `skills.json`,
  installer profiles (`--profile`, `--project`), and a SessionStart hook that
  symlinks only the skills whose markers match the current working directory.
- **Part B — a `find_skill` MCP tool.** A `find_skill(task)` / `list_skills()`
  pair on `mcp-wiki-server/` that searches `skills.json` and returns a matching
  `SKILL.md` on demand, so skills carry no standing description at all.

## Why this is out of scope

Both mechanisms exist to solve one problem: the standing context cost of every
installed skill's description. That problem was solved by cheaper means, and the
cheaper means shipped.

The description budget capped what any single entry may spend — 250 characters
for a normal skill, 450 for a router, enforced in CI by
`scripts/check_descriptions.py`. Routers then collapsed whole categories behind a
single trigger surface. The catalogue is 23 entries, but they do not cost 23
descriptions:

```
architecture   router + 9 sub-skills   -> 1 standing description
ai-ml          router + 2 sub-skills   -> 1 standing description
communication  5 skills                -> 5
workflow       natural-planning        -> 1
refactoring    refactoring             -> 1
personal       hypertrophy-training    -> 1
workflow       2 command skills        -> user-invoked, not in the auto budget
```

Roughly ten standing descriptions, each under a hard cap. That is not a context
problem worth a new hook, a new installer mode, a new manifest field, and a new
MCP tool.

The motivating examples that made the cost look larger are gone. The request
named `zettelkasten-value-hierarchy` and `worry-management` as dead weight in
coding sessions; both are gone (`ffe7cdc` and `f68327d`). `personal` is one skill today,
not a category-sized tax.

What is left is the trade the request itself flagged as its sharpest risk:
**both mechanisms buy context by spending discovery reliability.** A fingerprint
hook that misreads a directory silently hides a skill the user expected, with no
error and no obvious way to notice. `find_skill` only helps when the model
decides to call it, which is strictly worse than a registered description that
the model sees unprompted — and auto-trigger recall is the property
`eval-suite/recall/check_live.py` exists to protect. Paying reliability for
context the catalogue no longer over-spends is the wrong direction.

Deliberately not a reason: "not now". If the catalogue grows to the point where
routers and the description budget stop containing it, this is worth reopening —
Part B first, since it reuses infrastructure that already ships and cannot hide
anything the user did not ask it to hide.

## Prior requests

- #51 — "Experiment: context-aware skill loading — project-fingerprint hook and `find_skill` MCP tool"
