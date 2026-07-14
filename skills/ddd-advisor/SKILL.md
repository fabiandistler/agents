---
name: ddd-advisor
category: architecture
environments: coding
description: Advise on Domain-Driven Design at the strategic level (classifying subdomains as Core, Generic, or Supporting; context-mapping between bounded contexts) and the tactical level (picking an implementation pattern along the Transaction Script → Active Record → Domain Model → Event-Sourced Domain Model spectrum, then modeling with Entities, Value Objects, and Aggregates) — use it whenever a design conversation touches subdomain classification, buy-vs-build for a capability, integration with a legacy or third-party system, bounded-context boundaries, or how much domain modeling a piece of business logic actually deserves. Applies even if the user never says "DDD" or "domain-driven design" explicitly.
compatibility: Domain- and language-agnostic; the reasoning applies to any codebase practicing or considering Domain-Driven Design (examples below use SQL and R, but nothing is R-specific). Pairs with architecture-pattern-advisor for topology/microservice-boundary decisions and with adr-workflow to record the classification and pattern choices.
metadata:
  version: "1.0"
---

# DDD Advisor

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

This skill helps classify the problem correctly at both levels before writing
or restructuring code.

## Core principle

Match the investment to the value. A subdomain's strategic classification
(Core / Generic / Supporting) should drive both *how much* engineering effort
it gets and *which tactical pattern* implements it. Never let architectural
enthusiasm outrun the subdomain's actual importance — over-engineering a
Supporting subdomain and under-investing a Core one are both failures of the
same discipline.

## Level 1 — Strategic Design: classify the subdomain

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

## Level 1 — Context Mapping: relating bounded contexts

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

If none of Shared Kernel, Customer-Supplier, or Conformist apply and there is
no leverage over the other side, default to Conformist plus an ACL: adapt to
the external model but don't let it leak into your own.

To judge whether a specific cross-context dependency is acceptable as
designed — how much knowledge crosses the boundary, at what distance, and how
volatile it is — use the `balanced-coupling` skill; its volatility step in
turn leans on the subdomain classification above.

## Level 2 — Tactical Design: pick the implementation pattern

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

### Decision path

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

### Migration paths

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

## Workflow

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
- **adr-workflow** — record the subdomain classification and the chosen
  context-mapping / implementation pattern as an ADR when the decision is
  significant or likely to be revisited.
- **codebase-design** — general deep-module vocabulary for shaping the
  interface of a Domain Model or Aggregate Root once the pattern is chosen.
- **analyze-cohesion** — Aggregates are, among other things, a cohesion
  boundary; use this skill if an aggregate's internal cohesion itself is in
  question.

## Source

Based on Vlad Khononov, *Einführung in Domain-Driven Design* (O'Reilly, 2022),
and Eric Evans, *Domain-Driven Design* (2003); the Active Record vs. Domain
Model contrast also draws on Martin Fowler, *Patterns of Enterprise
Application Architecture* (2002).
