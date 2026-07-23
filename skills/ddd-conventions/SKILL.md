---
name: ddd-conventions
category: architecture
environments: coding
description: Correctness and design conventions for writing or reviewing code in a Domain-Driven Design codebase — aggregates, value objects, domain events, event sourcing, bounded-context integration. The code, not the upfront design (→ ddd-advisor).
metadata:
  version: "1.0"
---

# DDD Conventions

> Distilled from Vlad Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021).
> Non-obvious rules that correct a coding model's likely default behavior. Generic DDD
> vocabulary (what an entity/VO/aggregate *is*, "use a ubiquitous language", "talk to
> domain experts") is assumed and omitted. Chapter refs anchor each rule to the source.

## When to use

Whenever implementing domain logic, persisting aggregates, publishing events,
or wiring cross-context integration — even if the user never says "DDD". For
the upfront design conversation (subdomain classification, pattern choice,
context mapping) use ddd-advisor; this skill governs the code that comes out
of those decisions.

## Choosing the Business-Logic Pattern

- **Don't reach for a full domain model by default. Pick the pattern by complexity, cheapest first.** Ordered heuristic (Ch 10):
  1. Money / audit-log / deep-behavioral-analytics requirement → **event-sourced domain model**.
  2. Else complex business logic (rules, invariants, algorithms) → **domain model**.
  3. Else complex data structures only → **active record**.
  4. Else → **transaction script**.
  - ❌ modeling a simple supporting subdomain with aggregates + repositories ← likely-default over-engineering
- **Treat "complex logic" as the trigger, not "important feature".** Simple logic = mostly input validation / CRUD; complex = invariants + algorithms. A core subdomain's edge need not be technical (Ch 10).
- **Use the chosen pattern to sanity-check the subdomain type.** If a "core" subdomain only needs a transaction script, or a "supporting" one needs a domain model, revisit the classification (Ch 10).

## Aggregates

- **Commit exactly one aggregate instance per database transaction.** Needing to write two aggregates in one transaction means the boundaries are wrong — redraw them, don't span the transaction (Ch 6).
  - ❌ `unitOfWork.save(order); unitOfWork.save(inventory); commit()` ← likely-default
- **Reference other aggregates by ID only, never by object holding.** Embedded object references smuggle a second aggregate into the boundary (Ch 6).
  - ✅ `private CustomerId customerId;`
  - ❌ `private Customer customer;` ← likely-default
- **Keep aggregates as small as the invariants allow.** Include only data that must be *strongly consistent* to enforce this aggregate's rules; anything that can be eventually consistent belongs outside (Ch 6).
- **Test membership by consistency, not by "related-ness".** An entity belongs inside only if operating on eventually-consistent copies of it could corrupt state; otherwise it's a separate aggregate (Ch 6).
- **Expose only the aggregate root as public API.** Mutate inner entities exclusively through a root command; never let callers reach a child entity directly (Ch 6).
  - ❌ `order.getLines().get(0).setQty(5)` ← likely-default
  - ✅ `order.changeLineQty(lineId, 5)`
- **Give every aggregate a version field and check-and-set on write.** Reject a commit whose read-version no longer matches (optimistic concurrency); a lost-update here silently corrupts invariants (Ch 6).
- **Never model an entity as a standalone/top-level persistence object.** Entities exist only inside an aggregate (Ch 6).
- **Name domain events in the past tense** (`OrderShipped`, not `ShipOrder`) — they describe what already happened (Ch 6).

## Value Objects

- **Wrap domain concepts in value objects instead of primitives (fight primitive obsession).** `Email`, `PhoneNumber`, `Money`, `CountryCode` — not `string`/`int`. Validate once at construction/parse, so no downstream code re-validates (Ch 6).
  - ❌ `void setEmail(String email)` with validation scattered at call sites ← likely-default
  - ✅ `Email.parse("...")` — invalid values can't be constructed
- **Give value objects equality-by-value and no identity field.** Adding an ID to something defined purely by its attributes (e.g. a color) is a bug source (Ch 6).

## Transaction Script Correctness

- **Treat any operation touching a DB *and* signalling a caller as a distributed transaction.** A single-row `UPDATE` whose success is reported over a network/process boundary can still corrupt state on retry (Ch 5).
- **Make write operations idempotent or guard them with optimistic concurrency.** Assume the caller may retry after a lost success-signal (Ch 5).
- **Never commit partially-updated state.** The whole operation succeeds or fails atomically (Ch 5/6).

## Event Sourcing

- **Store events as the source of truth; derive current state by projecting them.** Do not persist a mutable state row as the truth and treat events as a side-channel (Ch 7).
- **Make events immutable and append-only. Never update or delete an event** (except controlled data migration) (Ch 7).
  - ❌ `UPDATE events SET ...` / `DELETE FROM events` ← likely-default when "correcting" data
- **Run every command as: load events → project to state → execute → append new events.** Don't mutate an in-memory state object and diff it (Ch 7).
- **Pair an event-sourced domain model with CQRS.** Without a separate read model, querying is limited to fetch-by-ID (Ch 7/10).

## Architecture Pattern Selection

Choose the architecture *from* the business-logic pattern, not independently (Ch 10):

- **Domain model → ports & adapters (hexagonal).** Layered architecture makes persistence-ignorant aggregates/VOs hard.
  - ❌ aggregates importing/annotated by the ORM ← likely-default
- **Active record → layered architecture with an added application/service layer** (the service layer drives the records).
- **Transaction script → minimal 3-layer.** Don't add hexagonal ceremony.
- **Event-sourced domain model → CQRS** (required, see above).
- **Add CQRS to *any* pattern when the subdomain needs multiple persistent read models**, not only for event sourcing.

## Bounded Context Boundaries

- **Size a bounded context as a function of its model — not "as small as possible".** Smallest-possible / one-per-microservice is an anti-heuristic (Ch 10).
  - ❌ splitting into microservices by default before the model is understood ← likely-default
- **Start wide, decompose later — especially for core/volatile subdomains.** Refactoring logical boundaries is cheap; refactoring physical (service) boundaries is expensive (Ch 10).
- **Treat a change that spans multiple bounded contexts as a boundary smell**, not routine work (Ch 10).
- **Keep bounded contexts and subdomains distinct.** One bounded context may contain several subdomains; don't assume 1:1 (Ch 3).
- **Assign exactly one team as owner of a bounded context.** Multiple teams sharing one context (outside a deliberate shared kernel) is a violation (Ch 3/4).

## Context Mapping / Integration

- **Wrap an upstream model you don't control in an anticorruption layer when** your side is a core subdomain, the upstream model is messy/legacy, or it changes often. Don't let a foreign model leak into your domain (Ch 4).
- **When you are the upstream provider, expose an open-host service with a published language** — a stable integration contract decoupled from your internal model — so you can evolve internals freely (Ch 4).
- **Use a shared kernel only when cost-of-duplication > cost-of-coordination.** Keep it minimal (integration contracts / shared data structures only) and trigger integration tests for all consumers on every change. It deliberately breaks single-team ownership, so justify it (Ch 4).
  - ❌ sharing a domain model across contexts for convenience ← likely-default
- **Conform to an upstream model (conformist) only when its model is acceptable or an industry standard.** Otherwise use an anticorruption layer (Ch 4).
- **Publish domain events reliably via the outbox pattern** — write the event to an outbox table in the *same* transaction as the state change, then relay it. Never call the message bus directly inside the business transaction (Ch 9).
  - ❌ `save(order); bus.publish(orderShipped)` in one method ← likely-default (dual-write / lost-message bug)
- **Never share a database or tables across bounded contexts.** Integrate through contracts/events (Ch 3/4/9).

## Subdomains & Ubiquitous Language

- **Classify each subdomain as core / supporting / generic before choosing patterns** — the type drives boundary, integration, and implementation-pattern decisions (Ch 1/10).
- **Re-evaluate subdomain type over time; it can shift** (e.g. core→generic as the market commoditizes) and should trigger a design revisit (Ch 11).
- **Name code artifacts (classes, methods, modules) after the ubiquitous language of *that* bounded context.** One consistent language per context; the same term may legitimately mean different things in different contexts (Ch 2/3).

## Related skills

- **ddd-advisor** — the design-time counterpart: classifying subdomains,
  walking the pattern decision path, and choosing a context-mapping pattern.
  These conventions assume those decisions are made; when a rule here exposes
  a wrong decision (e.g. the sanity-check rules above), go back to that skill.
- **balanced-coupling** — for judging whether a specific cross-context
  dependency is acceptable as designed (integration strength × distance ×
  volatility), e.g. before accepting a conformist relationship or a shared
  kernel.
- **architecture-pattern-advisor** — for the repo-level topology and
  code-organization decision that the "Architecture Pattern Selection"
  section above feeds into.
