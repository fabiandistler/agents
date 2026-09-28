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
| **Partnership** | Two contexts succeed or fail together with a cooperative, mutually dependent relationship | Two teams must evolve their models in lockstep toward a shared goal | Joint success needs synchronized planning and continuous coordination — high coordination cost, stalls if either side stops cooperating |
| **Published Language** | A shared, well-documented contract language for integration, usually served through an OHS | Many consumers need one stable contract, or integration needs a common tongue decoupled from any internal model | One more language to design, version, and translate to and from — pays off only when consumer count or stability need justifies it |
| **Separate Ways** | Contexts proceed independently with no integration | No leverage over the other side and low integration value — duplicating the sliver you need costs less than integrating | Duplication instead of reuse; if the overlap grows, two diverging models cost more — revisit if integration value rises |
| **Big Ball of Mud** | An unmodelable legacy tangle acknowledged as-is and bounded | A legacy system too tangled to model or remap pattern by pattern | No real integration pattern applies — wall it off with an ACL and don't let its model leak outward |

No leverage and low integration value → Separate Ways; no leverage but data needed → Conformist, plus an ACL if your side is Core. The same protection
works in both directions: an ACL guards a downstream consumer, an OHS guards
an upstream provider — a context that is both consumes through ACLs and
serves through a published language.

To judge whether a specific cross-context dependency is acceptable as
designed — how much knowledge crosses the boundary, at what distance, and how
volatile it is — use the balance-a-dependency mode of the `coupling-cohesion`
skill; its volatility step in turn leans on the subdomain classification above.

## Migration paths

Patterns are not a one-time, irreversible choice — migrating along the
spectrum as complexity grows is normal and expected:

- Transaction Script → Domain Model, when procedural complexity grows.
- Active Record → Domain Model, when business logic outgrows CRUD.
- Domain Model → Event-Sourced Domain Model, when history/audit becomes
  important.

The **Strangler Fig Pattern** applies well here: migrate incrementally behind
a stable interface rather than rewriting in one step.
