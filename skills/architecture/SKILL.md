---
name: architecture
category: architecture
activation: router
environments: coding
description: "Routes software architecture work to the right sub-skill; use when choosing system topology or code organization, service boundaries, domain models, component structure, C4 diagrams, coupling or cohesion, or architecture rules for CI. Not for single-file placement or routine refactors."
when_to_use: "Use even when the word architecture is absent: how should I structure or organize this project, how should this repo be split into modules, two services share a database, draw an overview of how the system fits together, make CI enforce layering rules, model this domain. Not for single-file placement or routine refactors."
---

# Architecture & design

This is a **router**. The architecture category ships several deep sub-skills;
this entry keeps one broad trigger on the surface and hands off to the specific
one. Do not answer an architecture or design question from this file alone.

## How to use

1. Match the request to a row in the table below.
2. **Read that sub-skill's `SKILL.md` before acting.** The sub-skills are
   files; open `members/<name>/SKILL.md` relative to this file's directory.
   If your agent also lists them as skills, still route through this table.
   The file carries the real workflow, references, and scripts — this router
   only points the way.
3. If two rows seem to apply, apply the tie-break below and read the default
   member; read a second member only if the first points to it. If none fit,
   use your general knowledge and say the catalogue had no dedicated
   sub-skill. Plain table/index design has no member — answer directly and
   say so.

The sub-skills are nested under this router's `members/` directory, so they load
only when routed to (progressive disclosure) rather than each competing for the
model's trigger surface.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| architecture-pattern-advisor | Guides repository architecture choices for topology or code organization; use when selecting or restructuring either, not for generic project setup. | `members/architecture-pattern-advisor/SKILL.md` |
| c4-modeling | Drafts C4 system diagrams in Mermaid at Context, Container, Component, Landscape, Dynamic, or Deployment level; use when documenting a system as C4, not Code. | `members/c4-modeling/SKILL.md` |
| coupling-cohesion | Assesses existing code for module cohesion and LCOM, codebase-wide coupling metrics and zones, or the balance of one dependency (Khononov). | `members/coupling-cohesion/SKILL.md` |
| ddd | Applies Domain-Driven Design to boundaries, context mapping, tactical patterns, aggregates, value objects, events, and event sourcing; use for DDD design or review. | `members/ddd/SKILL.md` |
| fitness-functions | Designs and implements architecture fitness functions — automated CI checks that fail the build when a characteristic such as modularity, layering, coupling, security, or resilience erodes. | `members/fitness-functions/SKILL.md` |
| logical-component-design | Decomposes a NEW system or feature into named logical components; not for measuring an existing decomposition. | `members/logical-component-design/SKILL.md` |
| microservices-design | Guides microservice interaction design and review — boundaries, coupling, communication style, contract versioning, sagas, and resiliency patterns from Newman's *Building Microservices*. | `members/microservices-design/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.

## Tie-breaks

When more than one row matches, route to exactly one default member:

- Split into services or organize code → `architecture-pattern-advisor`
- Where domain boundaries lie → `ddd`
- Components of a new system or feature → `logical-component-design`
- How services talk to each other → `microservices-design`
- Measure existing code for coupling or cohesion → `coupling-cohesion`
- Enforce a rule in CI so the design cannot erode → `fitness-functions`
- Two services share a database → `microservices-design`
- Where to start refactoring an unfamiliar codebase → the top-level `refactoring` skill, outside this router
