---
name: refactoring
category: refactoring
activation: router
environments: coding
description: Improving existing code safely — refactoring a code smell with the right Fowler technique, the stepdown rule for function structure, test-driven development, and staging risky changes. Routes to the right sub-skill.
---

# Refactoring & code quality

This is a **router**. The refactoring category ships several deep sub-skills;
this entry keeps one broad trigger on the surface and hands off to the specific
one. Do not answer a refactoring or code-quality question from this file alone.

## How to use

1. Match the request to a row in the table below.
2. **Read that sub-skill's `SKILL.md` (the path in the last column) before
   acting.** It carries the real workflow, references, and scripts — this router
   only points the way.
3. If two rows seem to apply, read both; if none fit, use your general knowledge
   and say the catalogue had no dedicated sub-skill.

The sub-skills are nested under this router's `members/` directory, so they load
only when routed to (progressive disclosure) rather than each competing for the
model's trigger surface.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| refactoring-techniques | Refactor a spotted code smell end to end — decide whether, when, and how safely to act, then apply the right Martin Fowler technique with its atomic mechanics. | `members/refactoring-techniques/SKILL.md` |
| stepdown-rule | Write, refactor, or review functions using the stepdown rule. | `members/stepdown-rule/SKILL.md` |
| tdd | Test-driven development. | `members/tdd/SKILL.md` |
| uncertainty-management | Manage risky, hard-to-predict changes by decomposing them into small validated steps, checkpointing before each one, and rolling back on trouble. | `members/uncertainty-management/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
