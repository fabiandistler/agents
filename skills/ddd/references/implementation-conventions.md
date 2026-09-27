# Implementation Conventions

> Distilled from Vlad Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021).
> Non-obvious rules that correct a coding model's likely default behavior. Generic DDD
> vocabulary (what an entity/VO/aggregate *is*, "use a ubiquitous language", "talk to
> domain experts") is assumed and omitted. Chapter refs anchor each rule to the source.
> The pattern/architecture *choice* these rules assume is made in SKILL.md; the
> context-mapping *patterns* they reference are defined in `strategic-design.md`.

## Contents

- [Aggregates](#aggregates)
- [Value Objects](#value-objects)
- [Transaction Script correctness](#transaction-script-correctness)
- [Bounded Context boundaries](#bounded-context-boundaries)
- [Context Mapping / integration](#context-mapping--integration)
- [Ubiquitous Language](#ubiquitous-language)

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

## Transaction Script correctness

- **Treat any operation touching a DB *and* signalling a caller as a distributed transaction.** A single-row `UPDATE` whose success is reported over a network/process boundary can still corrupt state on retry (Ch 5).
- **Make write operations idempotent or guard them with optimistic concurrency.** Assume the caller may retry after a lost success-signal (Ch 5).
- **Never commit partially-updated state.** The whole operation succeeds or fails atomically (Ch 5/6).

## Bounded Context boundaries

- **Size a bounded context as a function of its model — not "as small as possible".** Smallest-possible / one-per-microservice is an anti-heuristic (Ch 10).
  - ❌ splitting into microservices by default before the model is understood ← likely-default
- **Start wide, decompose later — especially for core/volatile subdomains.** Refactoring logical boundaries is cheap; refactoring physical (service) boundaries is expensive (Ch 10).
- **Treat a change that spans multiple bounded contexts as a boundary smell**, not routine work (Ch 10).
- **Keep bounded contexts and subdomains distinct.** One bounded context may contain several subdomains; don't assume 1:1 (Ch 3).
- **Assign exactly one team as owner of a bounded context.** Multiple teams sharing one context (outside a deliberate shared kernel) is a violation (Ch 3/4).

## Context Mapping / integration

For the mapping patterns themselves (Shared Kernel, ACL, OHS, Conformist, …)
see the table in `strategic-design.md`; the rules below govern how to apply
them in code.

- **Wrap an upstream model you don't control in an anticorruption layer when** your side is a core subdomain, the upstream model is messy/legacy, or it changes often. Don't let a foreign model leak into your domain (Ch 4).
- **When you are the upstream provider, expose an open-host service with a published language** — a stable integration contract decoupled from your internal model — so you can evolve internals freely (Ch 4).
- **Use a shared kernel only when cost-of-duplication > cost-of-coordination.** Keep it minimal (integration contracts / shared data structures only) and trigger integration tests for all consumers on every change. It deliberately breaks single-team ownership, so justify it (Ch 4).
  - ❌ sharing a domain model across contexts for convenience ← likely-default
- **Conform to an upstream model (conformist) only when its model is acceptable or an industry standard.** Otherwise use an anticorruption layer (Ch 4).
- **Publish domain events reliably via the outbox pattern** — write the event to an outbox table in the *same* transaction as the state change, then relay it. Never call the message bus directly inside the business transaction (Ch 9).
  - ❌ `save(order); bus.publish(orderShipped)` in one method ← likely-default (dual-write / lost-message bug)
- **Never share a database or tables across bounded contexts.** Integrate through contracts/events (Ch 3/4/9).

## Ubiquitous Language

- **Name code artifacts (classes, methods, modules) after the ubiquitous language of *that* bounded context.** One consistent language per context; the same term may legitimately mean different things in different contexts (Ch 2/3).
