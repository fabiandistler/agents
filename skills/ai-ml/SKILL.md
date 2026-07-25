---
name: ai-ml
category: ai-ml
activation: router
environments: coding
description: Building AI/ML systems — engineering an LLM or foundation-model application (prompts, tool calling, evals) or running a machine-learning project from framing to deployment. Routes to the right sub-skill.
---

# AI & ML

This is a **router**. The ai-ml category ships several deep sub-skills; this
entry keeps one broad trigger on the surface and hands off to the specific one.
Do not answer an AI or ML engineering question from this file alone.

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
| llm-application-engineering | Guide the engineering of a foundation-model application across three linked decisions. | `members/llm-application-engineering/SKILL.md` |
| ml-project-lifecycle | Guide a machine learning project from problem framing through model selection to production deployment. | `members/ml-project-lifecycle/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
