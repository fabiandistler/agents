---
name: architecture
category: architecture
activation: router
environments: coding
description: Any software architecture or design question — ADRs, DDD, C4 diagrams, coupling/cohesion analysis, microservices, component design, fitness functions, SQL schema design. Routes to the right sub-skill.
---

# Architecture & design

This is a **router**. The architecture category ships several deep sub-skills;
this entry keeps one broad trigger on the surface and hands off to the specific
one. Do not answer an architecture or design question from this file alone.

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
| adr-workflow | Establish and maintain Architecture Decision Records (ADRs) in software repositories. | `members/adr-workflow/SKILL.md` |
| architecture-pattern-advisor | Use when choosing the architecture of a repository — topology (monolith, modular monolith, microservices, serverless) or code organization (layered, by-domain, hexagonal, clean/onion). | `members/architecture-pattern-advisor/SKILL.md` |
| c4-modeling | Draft a C4 model of a software system with the user and render it as Mermaid diagrams. | `members/c4-modeling/SKILL.md` |
| codebase-design | Shared vocabulary and workflow for designing deep modules. | `members/codebase-design/SKILL.md` |
| coupling-cohesion | Assess an existing codebase's coupling and cohesion — module cohesion and LCOM, codebase-wide coupling metrics and zones, or whether a single dependency is balanced (Khononov). | `members/coupling-cohesion/SKILL.md` |
| ddd | Domain-Driven Design end to end — strategic subdomain classification and context mapping, tactical pattern choice, and implementation conventions for aggregates, value objects, and events. | `members/ddd/SKILL.md` |
| fitness-functions | Design and implement architecture fitness functions. | `members/fitness-functions/SKILL.md` |
| logical-component-design | Forward, generative decomposition of a NEW system or feature into named logical components — Richards & Ford's iterative identify-and-refine cycle. | `members/logical-component-design/SKILL.md` |
| microservices-design | Apply distilled microservices design conventions from Newman's *Building Microservices* when designing or reviewing how services interact. | `members/microservices-design/SKILL.md` |
| sql-schema-design | Apply module-encapsulation thinking to SQL schema design and query patterns. | `members/sql-schema-design/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
