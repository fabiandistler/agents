---
name: architecture
category: architecture
activation: router
environments: coding
description: Use for any question about how software should be structured or whether its structure is sound; routes to a sub-skill. Covers organizing a new or existing codebase or project (monolith vs microservices, layered/hexagonal/clean, modules, folders), service boundaries and how services talk, domain modeling (DDD), system diagrams (C4), recording decisions (ADRs), coupling/cohesion review, SQL schema design, architecture checks in CI.
---

# Architecture & design

This is a **router**. The architecture category ships several deep sub-skills;
this entry keeps one broad trigger on the surface and hands off to the specific
one. Do not answer an architecture or design question from this file alone.

## How to use

1. Match the request to a row in the table below.
2. **Read that sub-skill's `SKILL.md` before acting.** Open the file at the
   path in the last column (relative to this router's directory) with your
   file-reading tool. The sub-skills are *not* registered skills of their own:
   invoking one by name (for example `architecture:ddd`) fails with "unknown
   skill" and wastes a turn. Read the file instead; it carries the real
   workflow, references, and scripts — this router only points the way.
3. If two rows seem to apply, read both; if none fit, use your general knowledge
   and say the catalogue had no dedicated sub-skill.

The sub-skills are nested under this router's `members/` directory, so they load
only when routed to (progressive disclosure) rather than each competing for the
model's trigger surface.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| adr-workflow | Establish and maintain Architecture Decision Records (ADRs) in software repositories. | `members/adr-workflow/SKILL.md` |
| architecture-pattern-advisor | Choose a repository's architecture — topology (monolith, modular monolith, microservices, serverless) or code organization (layered, by-domain, hexagonal, clean/onion), not generic project setup. | `members/architecture-pattern-advisor/SKILL.md` |
| c4-modeling | Diagram how a software system fits together at Context, Container, Component, Landscape, Dynamic, and Deployment level (not Code / level 4). | `members/c4-modeling/SKILL.md` |
| coupling-cohesion | Assess an existing codebase's coupling and cohesion — module cohesion and LCOM, codebase-wide coupling metrics and zones, or whether a single dependency is balanced (Khononov). | `members/coupling-cohesion/SKILL.md` |
| ddd | Domain-Driven Design end to end — strategic subdomain classification and context mapping, tactical pattern choice, and implementation conventions for aggregates, value objects, and events. | `members/ddd/SKILL.md` |
| fitness-functions | Automate a CI check that governs an architecture characteristic — modularity, layering, coupling, security, resilience — and fails the build when it erodes. | `members/fitness-functions/SKILL.md` |
| logical-component-design | Decompose a NEW system or feature into named logical components; to measure an existing decomposition use coupling-cohesion instead. | `members/logical-component-design/SKILL.md` |
| microservices-design | Design or review how services interact — boundaries, coupling, communication style, contract versioning, sagas, resiliency patterns. | `members/microservices-design/SKILL.md` |
| sql-schema-design | Give database consumers a stable interface so physical storage can change without breaking their queries — views as the contract, named CTE pipelines, deployment gates against schema drift. | `members/sql-schema-design/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
