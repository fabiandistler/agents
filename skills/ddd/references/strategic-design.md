# Strategic Design

How to decide *where* to invest: subdomain classification, context mapping,
and migration triggers. Read this at workflow step 1–2, before any
implementation pattern is chosen.

## Contents

- [Discovering subdomains and boundaries](#discovering-subdomains-and-boundaries)
- [Classify the subdomain](#classify-the-subdomain)
- [Context Mapping: relating bounded contexts](#context-mapping-relating-bounded-contexts)
- [Migration paths](#migration-paths)

## Discovering subdomains and boundaries

"Classify with domain experts" needs a concrete method behind it. Run
discovery before classifying — the events and boundaries it surfaces are the
input the classification table below consumes:

- **Big Picture EventStorming** — gather domain experts and walk the end-to-end flow of domain events on a wide timeline. Clusters of pivotal events suggest where one subdomain (and later one bounded context) ends and the next begins.
- **Core Domain Chart** — place each discovered subdomain on the chart to decide its Core, Supporting, or Generic placement before any resourcing call is made.
- **Bounded Context Canvas** — document each candidate context (name, ubiquitous language, responsibilities, relationships) so the boundary decision is written down, not tribal knowledge.
- **Process- and Design-level EventStorming** — zoom into one context's flow (process level) and then into its commands, policies, and aggregates (design level); this feeds aggregate design directly.

References: the DDD starter modelling process
(<https://ddd-crew.github.io/ddd-starter-modelling-process/>), the Bounded
Context Canvas (<https://github.com/ddd-crew/bounded-context-canvas>), and
the EventStorming glossary cheat sheet
(<https://ddd-crew.github.io/eventstorming-glossary-cheat-sheet/>).

## Classify the subdomain

Before touching an implementation pattern, identify which kind of subdomain is
in play. This is a business-value judgment, ideally made with domain experts,
not a technical one.

- **Core**
  - Definition: The interesting problems — done differently than competitors
  - Business complexity: High
  - Value: Primary source of competitive advantage
  - Resourcing rule: Best engineers, continuous investment, custom build
  - Examples: Recommendation engine; logistics optimization
  - Common failure mode: Treating it as commodity, buying/outsourcing it, losing the differentiator
- **Generic**
  - Definition: The solved problems — every company does this the same way
  - Business complexity: Low
  - Value: No room for differentiation
  - Resourcing rule: Buy, do not build
  - Examples: Auth; payments; email delivery
  - Common failure mode: Building it in-house anyway — burns developer time, creates tech debt, produces a worse result than the market offers
- **Supporting**
  - Definition: The problems with obvious solutions — necessary, not differentiating
  - Business complexity: Moderate
  - Value: Necessary for operations, not differentiating
  - Resourcing rule: Pragmatic in-house, minimal investment
  - Examples: Internal reporting dashboards; company-specific ETL
  - Common failure mode: Over-engineering it with full DDD tactical patterns (wasted effort) *or* neglecting it entirely (tech debt, maintenance pain)

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
natural basis for service boundaries (see `members/architecture-pattern-advisor/SKILL.md`, read via the `architecture` router, for
the topology/microservice-boundary decision itself — this skill stays focused
on the domain-modeling side).

When two bounded contexts must relate, pick the mapping pattern deliberately;
each has a real trade-off:

- **Shared Kernel**
  - Relationship: Contexts deliberately share part of a model or a library ("the kernel")
  - When it fits: Only for stable, well-defined, rarely-changing components (base types, shared calculations, invariant business rules)
  - Trade-off: Increases coupling between teams; any kernel change needs coordination across every dependent context — a bottleneck if overused
- **Customer-Supplier**
  - Relationship: Directed dependency: an upstream context provides services/data, a downstream context consumes them
  - When it fits: Clear provider/consumer relationship, formalized by SLAs and API contracts
  - Trade-off: Upstream has design priority and must manage backward compatibility; downstream must handle versioning/migration — needs active relationship management
- **Conformist**
  - Relationship: Downstream adapts to an upstream model it cannot influence
  - When it fits: Integrating with an external or legacy system where you have no leverage over the upstream model
  - Trade-off: Simplest to implement, but you inherit the upstream's modeling choices, good or bad, with no ability to push back
- **Anti-Corruption Layer (ACL)**
  - Relationship: A translation/adapter layer isolates your model from an external model
  - When it fits: Legacy integration, third-party APIs, or any Conformist situation where you want to protect model integrity anyway
  - Trade-off: Adds complexity and a translation layer (possible performance overhead), but buys long-term maintainability — your model stays clean and changeable independent of the external system
- **Open-Host Service (OHS)**
  - Relationship: The *upstream* mirror of the ACL: the provider exposes a stable integration contract — a **published language** — decoupled from its internal model
  - When it fits: You are the upstream provider and want to evolve internals freely without breaking every consumer, or serve many downstream contexts through one contract
  - Trade-off: The published language is a second model to design and maintain; contract changes still need versioning and consumer migration — but internal refactoring stops being a breaking change
- **Partnership**
  - Relationship: Two contexts succeed or fail together with a cooperative, mutually dependent relationship
  - When it fits: Two teams must evolve their models in lockstep toward a shared goal
  - Trade-off: Joint success needs synchronized planning and continuous coordination — high coordination cost, stalls if either side stops cooperating
- **Published Language**
  - Relationship: A shared, well-documented contract language for integration, usually served through an OHS
  - When it fits: Many consumers need one stable contract, or integration needs a common tongue decoupled from any internal model
  - Trade-off: One more language to design, version, and translate to and from — pays off only when consumer count or stability need justifies it
- **Separate Ways**
  - Relationship: Contexts proceed independently with no integration
  - When it fits: No leverage over the other side and low integration value — duplicating the sliver you need costs less than integrating
  - Trade-off: Duplication instead of reuse; if the overlap grows, two diverging models cost more — revisit if integration value rises
- **Big Ball of Mud**
  - Relationship: An unmodelable legacy tangle acknowledged as-is and bounded
  - When it fits: A legacy system too tangled to model or remap pattern by pattern
  - Trade-off: No real integration pattern applies — wall it off with an ACL and don't let its model leak outward

No leverage and low integration value → Separate Ways; no leverage but data needed → Conformist, plus an ACL if your side is Core. The same protection
works in both directions: an ACL guards a downstream consumer, an OHS guards
an upstream provider — a context that is both consumes through ACLs and
serves through a published language.

To judge whether a specific cross-context dependency is acceptable as
designed — how much knowledge crosses the boundary, at what distance, and how
volatile it is — use the balance-a-dependency mode of `members/coupling-cohesion/SKILL.md`,
read via the `architecture` router; its volatility step in turn leans on the subdomain classification above.

## Migration paths

Patterns are not a one-time, irreversible choice — migrating along the
spectrum as complexity grows is normal and expected:

- Transaction Script → Domain Model, when procedural complexity grows.
- Active Record → Domain Model, when business logic outgrows CRUD.
- Domain Model → Event-Sourced Domain Model, when history/audit becomes
  important.

The **Strangler Fig Pattern** applies well here: migrate incrementally behind
a stable interface rather than rewriting in one step.
