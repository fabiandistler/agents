---
name: ddd
category: architecture
environments: coding
description: Domain-Driven Design end to end — strategic subdomain classification and context mapping, tactical pattern choice, and implementation conventions for aggregates, value objects, and events.
metadata:
  version: "2.0"
---

# DDD

Domain-Driven Design (per Evans, and as systematized by Vlad Khononov in
*Learning Domain-Driven Design*) operates on two levels that are easy to
conflate. **Strategic design** decides *where* to invest — which parts of the
business are worth custom software at all. **Tactical design** decides *how*
to build the parts that do get built. Getting the strategic call wrong wastes
the best engineers on commodity problems, or worse, ships a hand-rolled
Transaction Script for the one thing that actually differentiates the
business. Getting the tactical call wrong turns a simple ETL job into an
over-abstracted Domain Model, or lets genuinely complex, invariant-heavy logic
rot inside a script that nobody can safely change.

This skill covers both the **design conversation** (Parts 1–2, "should we,
and how") and the **implementation conventions** (Part 3, the concrete
correctness rules for the code that comes out of those decisions).

## When to use

Whenever a design conversation touches subdomain classification, buy-vs-build
for a capability, integration with a legacy or third-party system,
bounded-context boundaries, or how much domain modeling a piece of business
logic actually deserves — *and* whenever implementing domain logic, persisting
aggregates, publishing events, or wiring cross-context integration — even if
the user never says "DDD". Use Parts 1–2 for the upfront design, Part 3 as the
code-review checklist while writing.

## Core principle

Match the investment to the value. A subdomain's strategic classification
(Core / Generic / Supporting) should drive both *how much* engineering effort
it gets and *which tactical pattern* implements it. Never let architectural
enthusiasm outrun the subdomain's actual importance — over-engineering a
Supporting subdomain and under-investing a Core one are both failures of the
same discipline.

---

# Part 1 — Strategic Design

## Classify the subdomain

Before touching an implementation pattern, identify which kind of subdomain is
in play. This is a business-value judgment, ideally made with domain experts,
not a technical one.

| | Core | Generic | Supporting |
|---|---|---|---|
| **Definition** | The interesting problems — done differently than competitors | The solved problems — every company does this the same way | The problems with obvious solutions — necessary, not differentiating |
| **Business complexity** | High | Low | Moderate |
| **Value** | Primary source of competitive advantage | No room for differentiation | Necessary for operations, not differentiating |
| **Resourcing rule** | Best engineers, continuous investment, custom build | Buy, do not build | Pragmatic in-house, minimal investment |
| **Examples** | Amazon's recommendation engine and logistics optimization; Google's search ranking and ad placement; Netflix's content recommendation and streaming tech | Auth (Auth0, Okta, AWS Cognito); payments (Stripe, PayPal, Square); email (SendGrid, Mailgun); monitoring (DataDog, New Relic); base CRM (Salesforce, HubSpot) | Company-specific user/role management, internal reporting/dashboards, integration between internal systems, company-specific ETL |
| **Common failure mode** | Treating it as commodity, buying/outsourcing it, losing the differentiator | Building it in-house anyway — burns developer time, creates tech debt, produces a worse result than the market offers | Over-engineering it with full DDD tactical patterns (wasted effort) *or* neglecting it entirely (tech debt, maintenance pain) |

**Resource-allocation rule of thumb:** Core subdomains never get bought or
treated as commodity — they need full ownership, continuous improvement, and
protection as intellectual property. Generic subdomains are buy-vs-build
decisions that should almost always resolve to *buy*: any in-house
investment there is capacity stolen from Core work. Supporting subdomains sit
in between — too specific to buy, too simple to justify heavy architecture;
the goal is "as simple as possible, as robust as necessary," not
architectural perfection.

Subdomain type is not permanent: **re-evaluate it over time** (e.g. core→generic
as the market commoditizes) and treat a shift as a trigger to revisit the design
(Ch 11).

## Context Mapping: relating bounded contexts

A **Bounded Context** is the boundary within which a domain model and its
Ubiquitous Language are internally consistent — the same term ("Customer")
can mean something different in the Sales context than in the Support
context, without confusion, because meaning is scoped to the context. Bounded
contexts can be developed, deployed, and scaled independently, and are the
natural basis for service boundaries (see `architecture-pattern-advisor` for
the topology/microservice-boundary decision itself — this skill stays focused
on the domain-modeling side).

When two bounded contexts must relate, pick the mapping pattern deliberately;
each has a real trade-off:

| Pattern | Relationship | When it fits | Trade-off |
|---|---|---|---|
| **Shared Kernel** | Contexts deliberately share part of a model or a library ("the kernel") | Only for stable, well-defined, rarely-changing components (base types, shared calculations, invariant business rules) | Increases coupling between teams; any kernel change needs coordination across every dependent context — a bottleneck if overused |
| **Customer-Supplier** | Directed dependency: an upstream context provides services/data, a downstream context consumes them | Clear provider/consumer relationship, formalized by SLAs and API contracts | Upstream has design priority and must manage backward compatibility; downstream must handle versioning/migration — needs active relationship management |
| **Conformist** | Downstream adapts to an upstream model it cannot influence | Integrating with an external or legacy system where you have no leverage over the upstream model | Simplest to implement, but you inherit the upstream's modeling choices, good or bad, with no ability to push back |
| **Anti-Corruption Layer (ACL)** | A translation/adapter layer isolates your model from an external model | Legacy integration, third-party APIs, or any Conformist situation where you want to protect model integrity anyway | Adds complexity and a translation layer (possible performance overhead), but buys long-term maintainability — your model stays clean and changeable independent of the external system |
| **Open-Host Service (OHS)** | The *upstream* mirror of the ACL: the provider exposes a stable integration contract — a **published language** — decoupled from its internal model | You are the upstream provider and want to evolve internals freely without breaking every consumer, or serve many downstream contexts through one contract | The published language is a second model to design and maintain; contract changes still need versioning and consumer migration — but internal refactoring stops being a breaking change |

If none of Shared Kernel, Customer-Supplier, or Conformist apply and there is
no leverage over the other side, default to Conformist plus an ACL: adapt to
the external model but don't let it leak into your own. The same protection
works in both directions: an ACL guards a downstream consumer, an OHS guards
an upstream provider — a context that is both consumes through ACLs and
serves through a published language.

To judge whether a specific cross-context dependency is acceptable as
designed — how much knowledge crosses the boundary, at what distance, and how
volatile it is — use the balance-a-dependency mode of the `coupling-cohesion`
skill; its volatility step in turn leans on the subdomain classification above.

---

# Part 2 — Tactical Design

Once a subdomain and its bounded context are identified, choose *how* to
implement it. The four implementation patterns form a spectrum of rising
complexity and abstraction. Match the pattern to the subdomain classification
and to the actual complexity of the data and the business rules — do not
default to the most sophisticated pattern out of habit.

| # | Pattern | Complexity | Typical subdomain fit | Characteristic | Pro | Con |
|---|---|---|---|---|---|---|
| 1 | **Transaction Script** | Low | Supporting / Generic | Business operations as straightforward, sequential procedural scripts; explicit BEGIN/COMMIT/ROLLBACK; direct DB access, no ORM overhead | Simple, clear control flow | Becomes unmanageable as business logic grows: duplicated logic across scripts, hard to test, no encapsulated business rules |
| 2 | **Active Record** | Low–Medium | Supporting, DB-centric | Data + CRUD operations combined in one object; handles richer (non-flat) data structures than Transaction Script, e.g. object trees and 1:n/n:m relations | Direct, simple persistence | Tight coupling to the DB schema; mixes persistence with business logic — **not a DDD pattern**, it contradicts the DDD principle of separating domain model from persistence (DDD uses the Repository pattern instead) |
| 3 | **Domain Model** | Medium–High | Core (complex) | Rich objects that encapsulate both data and behavior; business rules and invariants live inside the domain objects; persistence is decoupled via Repository + typically a layered or ports & adapters architecture | Flexibility, testability, maintainability for changing business rules | Higher entry complexity; needs Repository, Unit of Work, and (usually) a layered or hexagonal architecture around it |
| 4 | **Event-Sourced Domain Model** | High | Core (very complex, auditable) | State is reconstructed by replaying a full history of domain events rather than storing current state directly | Complete history, point-in-time reconstruction, audit trail | Conceptual complexity, event-schema evolution over time |

## Decision path

Walk questions 1–3 in order and stop at the first "yes"; questions 4 and 5 are follow-ups, not further rungs:

1. **Is the data structure flat/simple and the process a linear, straightforward operation** (ETL, batch/report generation, simple CRUD)? → **Transaction Script.**
2. **Is the data structure complex** (object trees, hierarchies, 1:n or n:m relations) **but the logic is still essentially CRUD**, with no rich business rules to enforce? → **Active Record.**
3. **Does the subdomain carry complex, changing business logic or domain invariants that must be enforced** (this is where Core subdomains usually land)? → **Domain Model.**
4. **If step 3 selected Domain Model, additionally ask: does the subdomain involve monetary transactions, regulatory audit requirements, or a genuine need for full history / point-in-time reconstruction?** → Upgrade to an **Event-Sourced Domain Model.**
5. **Does the system need multiple persistence models** (e.g. a write model and separately optimized read models)? → Layer **CQRS + Event Sourcing**, or a **Ports & Adapters** architecture, on top of whichever pattern steps 1–4 selected — this is an orthogonal concern, not a fifth rung on the ladder.

Never select a pattern above what the subdomain's classification and actual
complexity justify. A Supporting subdomain implemented as a full Domain Model
is over-engineering; a Core subdomain implemented as a Transaction Script is
under-investment in the one place that should differentiate the business.

The check runs in both directions: the pattern the logic *actually needs* is
a sanity check on the strategic classification. If a "Core" subdomain turns
out to need only a Transaction Script, or a "Supporting" one genuinely needs
a Domain Model, revisit the classification from Part 1 before proceeding —
one of the two judgments is wrong. Treat "complex logic" (invariants +
algorithms), not "important feature", as the trigger for a richer pattern.

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

## Migration paths

Patterns are not a one-time, irreversible choice — migrating along the
spectrum as complexity grows is normal and expected:

- Transaction Script → Domain Model, when procedural complexity grows.
- Active Record → Domain Model, when business logic outgrows CRUD.
- Domain Model → Event-Sourced Domain Model, when history/audit becomes
  important.

The **Strangler Fig Pattern** applies well here: migrate incrementally behind
a stable interface rather than rewriting in one step.

## Building blocks (used by patterns 3 and 4, and useful even in simpler ones)

### Entities — identity over attributes

An Entity's identity matters more than its current attribute values. It is
defined by an immutable ID assigned at creation; two entities are equal iff
their IDs match, regardless of any other attribute. Attributes are expected
to change over the entity's lifetime (a customer's address changes; an
order's status progresses; a bank account's balance moves) — that mutability,
tracked over time, is the point. Entities always exist as part of an
Aggregate: either as the Aggregate Root itself, or as an internal entity
reachable only through the root.

### Value Objects — identity through values, no lifecycle

A Value Object has no ID; it is defined entirely by the combination of its
attribute values. Two Value Objects with identical values are interchangeable
(value equality, not reference equality).

- **Immutable.** Changing an attribute produces a new instance; the original
  is untouched. This avoids side effects and race conditions and simplifies
  caching and parallel processing.
- **No lifecycle.** Created, used, discarded — never persisted as a
  standalone entity, never given its own Repository. In storage, a Value
  Object is embedded as columns or an embeddable/component on its owning
  Entity, not a separate table.
- **Validated at construction.** Business rules are enforced in the
  constructor so an invalid instance can never exist — "make illegal states
  unrepresentable."
- **Guards against primitive obsession.** `salary <- 50000` says nothing
  about currency or period; `Money(amount = 50000, currency = "EUR", period =
  "annual")` makes the domain concept explicit and type-safe.

### Aggregates — the consistency and access boundary

An Aggregate groups Entities and Value Objects that must be immediately,
transactionally consistent into one coherent unit, and defines a
transactional/consistency boundary: a change to the aggregate is committed in
full or not at all (ACID at the domain level). Invariants are guaranteed
*within* an aggregate; *between* aggregates, only eventual consistency
applies.

**Design rule: keep aggregates small.** Include only the objects that truly
must be consistent together — this improves performance and scalability, and
oversized aggregates are a common source of contention and complexity.

**The Aggregate Root is the only entity accessible from outside the
aggregate** — a gatekeeper:

- All operations on the aggregate go through the root; internal entities and
  value objects are never reached directly from outside.
- The root controls every change and guarantees the aggregate never ends up
  in an inconsistent state.
- The root holds the aggregate's one globally unique identity; internal
  entities have only locally-meaningful identities.
- When one aggregate needs to reference another, it stores only the other
  root's ID, never the object itself — this keeps coupling low and respects
  each aggregate's consistency boundary.

## Design workflow

1. **Classify the subdomain first** (Core / Generic / Supporting) with input
   from domain experts — this is a business-value judgment, not a coding
   decision. State the classification explicitly before recommending
   anything.
2. **Apply the resourcing rule** that follows from the classification: buy
   Generic, invest best engineers in Core, keep Supporting pragmatic and
   in-house.
3. **Identify the bounded context(s) involved** and, for each relationship to
   another context, pick a context-mapping pattern (Shared Kernel,
   Customer-Supplier, Conformist, or ACL) and name the trade-off being
   accepted.
4. **Walk the tactical decision path** (above) to choose an implementation
   pattern for the subdomain's logic, keeping the pattern proportional to the
   subdomain's classification and complexity.
5. **Model with the building blocks**: identify Entities (identity + a
   lifecycle worth tracking), Value Objects (validated, immutable, no
   identity), and the Aggregate boundary that groups them — keep the
   aggregate as small as the actual consistency requirement allows.
6. **Flag over/under-investment** explicitly: a Domain Model proposed for a
   Supporting subdomain, or a Transaction Script proposed for a Core one, is
   worth calling out before implementation starts.
7. **Note migration triggers**, not migrations to do immediately: if a
   Transaction Script or Active Record implementation is starting to show the
   scaling limits described above, name the next pattern on the spectrum as
   the future move, ideally via a Strangler Fig migration.

---

# Part 3 — Implementation conventions

> Distilled from Vlad Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021).
> Non-obvious rules that correct a coding model's likely default behavior. Generic DDD
> vocabulary (what an entity/VO/aggregate *is*, "use a ubiquitous language", "talk to
> domain experts") is assumed and omitted. Chapter refs anchor each rule to the source.
> These are the code-review rules; the pattern/architecture *choice* they assume is made
> in Parts 1–2 above.

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

## Event Sourcing

- **Store events as the source of truth; derive current state by projecting them.** Do not persist a mutable state row as the truth and treat events as a side-channel (Ch 7).
- **Make events immutable and append-only. Never update or delete an event** (except controlled data migration) (Ch 7).
  - ❌ `UPDATE events SET ...` / `DELETE FROM events` ← likely-default when "correcting" data
- **Run every command as: load events → project to state → execute → append new events.** Don't mutate an in-memory state object and diff it (Ch 7).
- **Pair an event-sourced domain model with CQRS.** Without a separate read model, querying is limited to fetch-by-ID (Ch 7/10).

## Bounded Context boundaries

- **Size a bounded context as a function of its model — not "as small as possible".** Smallest-possible / one-per-microservice is an anti-heuristic (Ch 10).
  - ❌ splitting into microservices by default before the model is understood ← likely-default
- **Start wide, decompose later — especially for core/volatile subdomains.** Refactoring logical boundaries is cheap; refactoring physical (service) boundaries is expensive (Ch 10).
- **Treat a change that spans multiple bounded contexts as a boundary smell**, not routine work (Ch 10).
- **Keep bounded contexts and subdomains distinct.** One bounded context may contain several subdomains; don't assume 1:1 (Ch 3).
- **Assign exactly one team as owner of a bounded context.** Multiple teams sharing one context (outside a deliberate shared kernel) is a violation (Ch 3/4).

## Context Mapping / integration

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

## Common mistakes

- **Buying a Core subdomain, or building a Generic one.** Both misallocate
  the resource that actually matters — engineering time on the thing that
  differentiates the business.
- **Over-engineering Supporting subdomains** with full DDD tactical patterns
  when a Transaction Script would do — and the opposite failure,
  **neglecting them entirely**, which creates its own tech debt.
- **Treating Active Record as a DDD pattern.** It mixes persistence with
  business logic and is explicitly not what DDD's Repository-based separation
  intends — don't reach for it when a subdomain actually needs a Domain
  Model.
- **Oversized aggregates.** Grouping objects into one aggregate "just in
  case" instead of only what must be immediately consistent; this hurts
  performance and creates unnecessary contention.
- **Reaching outside the Aggregate Root.** Any external reference to an
  internal entity or value object breaks the consistency guarantee the
  aggregate exists to provide.
- **Skipping the context-mapping choice.** Integrating two bounded contexts
  without naming Shared Kernel / Customer-Supplier / Conformist / ACL hides a
  real trade-off (usually coupling vs. control) that should be made
  consciously.
- **Jumping straight to Event Sourcing** for complexity's sake, without an
  actual audit/history/monetary-transaction requirement driving it — that
  requirement is the trigger, not general "Core-ness."

## Related skills

- **architecture-pattern-advisor** — once bounded contexts are identified,
  use this skill for the topology decision (monolith vs. modular monolith vs.
  microservices) and code-organization pattern; bounded contexts are the
  natural seams, but the topology call is out of scope here.
- **coupling-cohesion** — to judge whether a specific cross-context dependency
  is acceptable as designed (integration strength × distance × volatility),
  e.g. before accepting a conformist relationship or a shared kernel; and
  because Aggregates are, among other things, a cohesion boundary.
- **adr-workflow** — record the subdomain classification and the chosen
  context-mapping / implementation pattern as an ADR when the decision is
  significant or likely to be revisited.
- **codebase-design** — general deep-module vocabulary for shaping the
  interface of a Domain Model or Aggregate Root once the pattern is chosen.

## Source

Based on Vlad Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021) /
*Einführung in Domain-Driven Design* (O'Reilly, 2022), and Eric Evans,
*Domain-Driven Design* (2003); the Active Record vs. Domain Model contrast
also draws on Martin Fowler, *Patterns of Enterprise Application
Architecture* (2002).
