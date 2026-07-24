---
name: workflow
category: workflow
activation: router
environments: coding
description: Development workflow helpers — distilling messy docs into rules files (CONVENTIONS/AGENTS/CLAUDE.md), throwaway prototypes to validate a design, and authoring or improving Claude skills. Routes to the right sub-skill.
---

# Workflow

This is a **router**. The workflow category ships several deep sub-skills; this
entry keeps one broad trigger on the surface and hands off to the specific one.
Do not answer a workflow question from this file alone.

## How to use

1. Match the request to a row in the table below.
2. **Read that sub-skill's `SKILL.md` (the path in the last column) before
   acting.** It carries the real workflow, references, and scripts — this router
   only points the way.
3. If two rows seem to apply, read both; if none fit, use your general knowledge
   and say the catalogue had no dedicated sub-skill.

The sub-skills are nested under this router's `members/` directory, so they load
only when routed to (progressive disclosure) rather than each competing for the
model's trigger surface. The category's user-invoked command skills (`grilling`,
`handoff`, `natural-planning`, `repo-status`, `to-issues`) are triggered directly
and bypass this router.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| guideline-distillation | Distill messy source documents (style guides, ADRs, RFCs, wikis, linter configs) into lean, machine-actionable rules files (CONVENTIONS.md, AGENTS.md, CLAUDE.md) for coding agents. | `members/guideline-distillation/SKILL.md` |
| prototype | Build a throwaway prototype to flesh out a design — a runnable terminal app for state/business-logic questions, or several radically different UI variations toggleable from one route. | `members/prototype/SKILL.md` |
| skill-creator | Create new skills, modify and improve existing skills, and measure skill performance. | `members/skill-creator/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
