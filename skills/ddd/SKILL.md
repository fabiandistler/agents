---
name: ddd
category: architecture
environments: coding
description: Domain-Driven Design end to end — strategic subdomain classification and context mapping, tactical pattern choice, and implementation conventions for aggregates, value objects, and events.
metadata:
  version: "2.0"
---

# DDD

Strategic design decides *where* to invest; tactical design decides *how* to build. Match the investment to the value — over-engineering a Supporting subdomain and under-investing a Core one are both failures of the same discipline.

## When to use

Whenever a design conversation touches subdomain classification, buy-vs-build
for a capability, integration with a legacy or third-party system,
bounded-context boundaries, or how much domain modeling a piece of business
logic actually deserves — *and* whenever implementing domain logic, persisting
aggregates, publishing events, or wiring cross-context integration — even if
the user never says "DDD". Use the decision path below for the upfront design
choice, the workflow for the design conversation, and the reference files as
the code-review checklist while writing.

## Core principle

Match the investment to the value. A subdomain's strategic classification
(Core / Generic / Supporting) should drive both *how much* engineering effort
it gets and *which tactical pattern* implements it. Never let architectural
enthusiasm outrun the subdomain's actual importance.

## Decision path

Walk questions 1–4 in order and stop at the first "yes"; question 5 is a follow-up, not a further rung:

1. **Does the subdomain involve monetary transactions, regulatory audit requirements, or a genuine need for full history / deep analytics / point-in-time reconstruction?** → **Event-Sourced Domain Model.** Read `references/event-sourcing.md` when this fires.
2. **Does the subdomain carry complex, changing business logic or domain invariants that must be enforced** (this is where Core subdomains usually land)? → **Domain Model.**
3. **Is the data structure complex** (object trees, hierarchies, 1:n or n:m relations) **but the logic is still essentially CRUD**, with no rich business rules to enforce? → **Active Record.**
4. **Otherwise** (flat/simple data, linear straightforward operation — ETL, batch/report generation, simple CRUD)? → **Transaction Script.**
5. **Does the system need multiple persistence models** (e.g. a write model and separately optimized read models)? → Layer **CQRS + Event Sourcing**, or a **Ports & Adapters** architecture, on top of whichever pattern steps 1–4 selected — this is an orthogonal concern, not a fifth rung on the ladder.

Testing shape follows the pattern (Ch 10): Transaction Script → reversed pyramid (few unit tests, mostly integration/E2E); Active Record → diamond (integration-heavy); Domain Model and Event-Sourced Domain Model → pyramid (mostly unit tests).

Never select a pattern above what the subdomain's classification and actual
complexity justify. Treat "complex logic" (invariants + algorithms), not
"important feature", as the trigger for a richer pattern. If a "Core"
subdomain turns out to need only a Transaction Script, or a "Supporting" one
genuinely needs a Domain Model, revisit the classification in
`references/strategic-design.md` before proceeding — one of the two judgments
is wrong.

## Architecture follows the pattern

The business-logic pattern also determines the architecture style around it —
choose them together, not independently:

| Business-logic pattern | Architecture style | Why |
|---|---|---|
| Transaction Script | Minimal 3-layer (presentation / logic / data) | The logic is procedural; hexagonal ceremony adds nothing |
| Active Record | Layered, with an added application/service layer | The service layer drives the records; persistence-awareness is inherent to the pattern |
| Domain Model | Ports & Adapters (hexagonal) | Aggregates and Value Objects must stay persistence-ignorant; a classic layered architecture makes that hard (e.g. ORM annotations leaking into aggregates) |
| Event-Sourced Domain Model | CQRS (required) | Without a separate read model, querying an event store is limited to fetch-by-ID |

CQRS is not exclusive to event sourcing: add it to *any* pattern when the
subdomain needs multiple persistent read models (mirrors step 5 of the
decision path).

## Design workflow

1. **Classify the subdomain first** (Core / Generic / Supporting) with input from domain experts — run Big Picture EventStorming to surface candidate subdomains first (see "Discovering subdomains and boundaries" in `references/strategic-design.md`), then apply the classification table and the resourcing rule there. State the classification explicitly before recommending anything.
2. **Identify the bounded context(s) involved** and, for each relationship to another context, pick a context-mapping pattern from the table in `references/strategic-design.md` and name the trade-off being accepted.
3. **Walk the tactical decision path** above to choose an implementation pattern, keeping the pattern proportional to the subdomain's classification and complexity.
4. **Model with the building blocks** in `references/implementation-conventions.md`: identify Entities (identity + a lifecycle worth tracking), Value Objects (validated, immutable, no identity), and the Aggregate boundary — keep the aggregate as small as the actual consistency requirement allows.
5. **Apply the implementation conventions** in `references/implementation-conventions.md` as the code-review checklist while writing; read `references/event-sourcing.md` when step 3 of the decision path selects event sourcing.
6. **Flag over/under-investment** explicitly: a Domain Model proposed for a Supporting subdomain, or a Transaction Script proposed for a Core one, is worth calling out before implementation starts (see the Decision path above).
7. **Note migration triggers**, not migrations to do immediately (see `references/strategic-design.md`): name the next pattern on the spectrum as the future move, ideally via a Strangler Fig migration.

## Common mistakes

- **Treating Active Record as a DDD pattern.** It mixes persistence with business logic and contradicts DDD's Repository-based separation — don't reach for it when a subdomain actually needs a Domain Model.
- **Skipping the context-mapping choice.** Integrating two bounded contexts without naming the pattern hides a real trade-off (usually coupling vs. control) that should be made consciously.
- **Jumping straight to Event Sourcing** for complexity's sake, without an actual audit/history/monetary-transaction requirement driving it — that requirement is the trigger, not general "Core-ness."

## Related skills

- **architecture-pattern-advisor** — once bounded contexts are identified, use this skill for the topology decision (monolith vs. modular monolith vs. microservices) and code-organization pattern; bounded contexts are the natural seams, but the topology call is out of scope here.
- **coupling-cohesion** — to judge whether a specific cross-context dependency is acceptable as designed (integration strength × distance × volatility), e.g. before accepting a conformist relationship or a shared kernel; and because Aggregates are, among other things, a cohesion boundary.
- **adr-workflow** — record the subdomain classification and the chosen context-mapping / implementation pattern as an ADR when the decision is significant or likely to be revisited.
- **logical-component-design** — to decompose a bounded context into named logical components; aggregates live inside components and bounded contexts group components.
- **microservices-design** — for the service-level mapping once contexts exist (saga style, messaging reliability, resilience); the shared-database rule is stated once in `references/implementation-conventions.md` and mirrored there.

## Source

Based on Vlad Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021), and
Eric Evans, *Domain-Driven Design* (2003); the Active Record vs. Domain Model
contrast also draws on Martin Fowler, *Patterns of Enterprise Application
Architecture* (2002).
