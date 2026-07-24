---
name: r-development
category: r-development
activation: router
environments: coding
description: R package development — custom rlang condition/error constructors, and package internals such as private state, loading/attaching, lifecycle hooks, deprecation, and interface-focused testing. Routes to the right sub-skill.
---

# R development

This is a **router**. The r-development category ships several deep sub-skills;
this entry keeps one broad trigger on the surface and hands off to the specific
one. Do not answer an R package question from this file alone.

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
| r-error-constructors | Design custom condition/error constructors for R packages the tidyverse/rlang way. | `members/r-error-constructors/SKILL.md` |
| r-package-dev | R package internals — package-private state and persistence, loading/attaching, lifecycle hooks and API deprecation, and interface-focused testing with fixtures. | `members/r-package-dev/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
