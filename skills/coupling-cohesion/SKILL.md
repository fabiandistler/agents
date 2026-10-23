---
name: coupling-cohesion
category: architecture
environments: coding
description: Assesses existing code for module cohesion and LCOM, codebase-wide coupling metrics and zones, or the balance of one dependency (Khononov). Use when measuring cohesion, coupling, or dependency balance.
compatibility: The bundled scripts are stdlib-only Python 3.8+. LCOM analyzes Python (precise, via AST), R, and Bash (heuristic); the coupling and balance checks are language-agnostic. Dependency-graph extraction uses whatever tool fits the ecosystem (examples in the Mode B file for Python, JS/TS, Java, .NET, Go).
---

# Coupling & Cohesion

"High cohesion, low coupling" is the meta-principle most design rules reduce to.
This skill **measures existing code** along both axes and picks the right lens
for the question in front of you:

| Mode | The question | Open |
|---|---|---|
| **A. Cohesion** | Do this module/class/file's parts belong together — split, merge, or leave? | [references/mode-a-cohesion.md](references/mode-a-cohesion.md) |
| **B. Codebase coupling** | How coupled / brittle / over-abstracted is the codebase, by the numbers? | [references/mode-b-coupling-metrics.md](references/mode-b-coupling-metrics.md) |
| **C. Balanced coupling** | Is this *one specific* dependency the right kind of coupling for its boundary? | [references/mode-c-balanced-coupling.md](references/mode-c-balanced-coupling.md) |

Pick the mode from the question, then open only that mode's file: it holds
the workflow, the output template, and the common mistakes. Open a second
mode file only when the answer needs it — for example, a Mode B hotspot
whose one suspicious dependency you then weigh with Mode C. Script paths in
the mode files are relative to this skill's directory.

Modes B and C are complementary halves of a coupling audit: the metrics (B) find
the hotspots, the balance model (C) explains and fixes a specific relationship.
Mode A is the cohesion half of the same law. The per-scale expressions and the
classic failure shapes live in
[references/cohesion-taxonomy.md](references/cohesion-taxonomy.md#the-same-law-at-every-scale).
For *greenfield* decomposition of a system that doesn't exist yet, use
`members/logical-component-design/SKILL.md` (read via the `architecture` router) instead — this skill measures what's already there.

## When to use

- "Is this `utils.py` a grab-bag — split it or leave it?"
- "Which of our packages sit in the Zone of Pain?"
- "Is it OK that the billing service reads the shared customer entity?"

**Not for:** a single function's cyclomatic complexity, choosing an architecture
from scratch (use `members/architecture-pattern-advisor/SKILL.md`, read via the `architecture` router), or greenfield component
decomposition (read `members/logical-component-design/SKILL.md` via the `architecture` router).

## Output contract (all modes)

Every answer uses the same shape — verdict first, evidence second, concrete
next step third — with a per-mode template in each mode file. Report each
material finding at the requested scope with its seam and fix; group minor
findings by shared pattern. Leave with reason is a first-class, valuable
verdict — saying "leave it" with the reason is success, not a non-answer.
Keep it proportional: a clean module needs a sentence, not a report.

`scripts/test_*.py` are the bundled scripts' own tests; they are not part of
any mode's workflow.

## Related skills

Sibling sub-skills, each read via the `architecture` router:
- **logical-component-design** — the generative front end: *creates* a
  decomposition for a new system; this skill *measures* one that already exists.
- **architecture-pattern-advisor** — when the topology itself is wrong, not just
  one module or dependency.
- **ddd** (`members/ddd/SKILL.md`) — subdomain classification feeds the volatility judgment in Mode C;
  aggregates are, among other things, a cohesion boundary.
