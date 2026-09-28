---
name: architecture
category: architecture
activation: router
environments: coding
description: "Routes software-architecture work to the right sub-skill: choosing topology or code organization (monolith vs microservices, layered/hexagonal/clean), service boundaries and inter-service communication, DDD modeling, component decomposition, C4 diagrams, ADRs, coupling/cohesion analysis, CI architecture rules, and SQL schemas as stable consumer interfaces."
when_to_use: "Use even when the word architecture is absent: how should I structure or organize this project, how should this repo be split into modules, two services share a database, draw an overview of how the system fits together, keep a record of past decisions, make CI enforce layering rules, model this domain. Not for single-file placement or routine refactors."
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
| adr-workflow | Establish, draft, supersede, and maintain Architecture Decision Records (ADRs) in software repositories. | `members/adr-workflow/SKILL.md` |
| architecture-pattern-advisor | Choose a repository's architecture — topology (monolith, modular monolith, microservices, serverless) or code organization (layered, by-domain, hexagonal, clean/onion), not generic project setup. | `members/architecture-pattern-advisor/SKILL.md` |
| c4-modeling | Diagram how a software system fits together at Context, Container, Component, Landscape, Dynamic, and Deployment level (not Code / level 4). | `members/c4-modeling/SKILL.md` |
| coupling-cohesion | Assess an existing codebase's coupling and cohesion — module cohesion and LCOM, codebase-wide coupling metrics and zones, or whether a single dependency is balanced (Khononov). | `members/coupling-cohesion/SKILL.md` |
| ddd | Domain-Driven Design end to end — strategic subdomain classification and context mapping, tactical pattern choice, and implementation conventions for aggregates, value objects, and events. | `members/ddd/SKILL.md` |
| fitness-functions | Automate a CI check that governs an architecture characteristic — modularity, layering, coupling, security, resilience — and fails the build when it erodes. | `members/fitness-functions/SKILL.md` |
| logical-component-design | Decompose a NEW system or feature into named logical components; to measure an existing decomposition use coupling-cohesion instead. | `members/logical-component-design/SKILL.md` |
| microservices-design | Design or review how services interact — boundaries, coupling, communication style, contract versioning, sagas, resiliency patterns. | `members/microservices-design/SKILL.md` |
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
