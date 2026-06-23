# Pattern Catalog

Reference for step 3 (candidates + pros/cons) and step 5 (scaffolding trees). Two axes — **topology** and **code organization** — plus advanced data patterns. They compose; see the end.

For each pattern: one-line definition, Pros, Cons, When it fits, When to avoid. Code-organization patterns include an annotated example tree.

---

## Axis 1 — System Topology (how many deployable units)

### Monolith
One deployable unit, one process, one database.

- **Pros:** simplest to build/deploy/debug; easy cross-module transactions; no network failure modes; fastest for small teams.
- **Cons:** all-or-nothing deploys; one scaling profile for everything; risk of becoming a Big Ball of Mud without internal discipline.
- **Fits:** solo/small team, low ops maturity, single scaling profile, strong consistency needs, MVPs.
- **Avoid:** independent team release autonomy, components with wildly different scaling needs.

### Modular Monolith
One deployable unit, but internally split into well-bounded modules with explicit public interfaces. **Recommended default when unsure.**

- **Pros:** monolith's operational simplicity + clear seams; modules can later be extracted into services; enforces boundaries without network cost.
- **Cons:** boundaries must be actively maintained (a monolith in disguise if not); still one deploy/scale unit.
- **Fits:** long-lived apps, moderate-to-rich domains, teams that want microservices' decoupling without the ops burden.
- **Avoid:** truly throwaway scripts; cases needing genuine independent deployment today.

### Microservices
Many small independently deployable services, each owning its data, communicating over the network.

- **Pros:** independent deploy/scale per service; team autonomy; fault isolation; tech heterogeneity.
- **Cons:** distributed-systems tax — network failures, eventual consistency, distributed tracing, deployment/observability overhead; hard to get boundaries right up front.
- **Fits:** multiple teams, mature CI/CD + observability, components with distinct scaling/load profiles.
- **Avoid:** small teams, low ops maturity, strong cross-entity transactional needs, greenfield with unclear boundaries (extract from a modular monolith later instead).

### Serverless / Functions
Stateless functions run on demand by a managed platform; scale to zero.

- **Pros:** no server management; pay-per-use; auto-scaling; great for spiky/event-triggered work.
- **Cons:** cold starts; vendor lock-in; local testing/debugging harder; awkward for long-running or stateful work.
- **Fits:** event-driven glue, scheduled jobs, spiky stateless workloads, webhooks.
- **Avoid:** steady high-throughput services, long-lived connections, heavy stateful processing.

### Event-Driven
Components communicate asynchronously through events on a broker rather than direct calls.

- **Pros:** loose coupling; natural scaling/buffering; easy to add consumers; resilient to downstream outages.
- **Cons:** eventual consistency; harder to trace/reason about end-to-end flow; needs broker ops; ordering/idempotency concerns.
- **Fits:** workflows with many reactions to one fact, audit trails, decoupling producers from consumers, integration backbones.
- **Avoid:** simple request/response needs, strong immediate-consistency requirements, teams new to async debugging.

---

## Axis 2 — Code Organization (how one unit is structured)

### Layered (by technical layer)
Group code by technical role: controllers, services, models, repositories.

- **Pros:** familiar; matches many framework conventions; fine for thin CRUD; low ceremony.
- **Cons:** a single feature is smeared across many folders; layers become merge-contention points; encourages anemic models and fat controllers as it grows.
- **Fits:** small/thin apps, framework-convention-heavy stacks, short-lived projects.
- **Avoid:** rich domains, multi-team feature ownership, long-lived fast-evolving code.

```
app/                  # Python — layered
  api/                # transport: routes/controllers
  services/           # business logic
  repositories/       # data access
  models/             # ORM / domain entities
  schemas/            # request/response DTOs
  core/               # config, logging, security
  main.py
tests/
```

### Package-by-Feature / By-Domain
Group code by business capability; each feature folder holds its own transport, logic, and data access (vertical slice).

- **Pros:** high cohesion; a feature is one folder; teams own folders with low collision; maps to bounded contexts; easiest path to later service extraction.
- **Cons:** some cross-cutting duplication; requires discipline on shared code; less "obvious" to devs trained on layered.
- **Fits:** moderate-to-rich domains, multi-team ownership, long-lived apps, anything you might split into services later.
- **Avoid:** tiny CRUD apps where the indirection isn't worth it.

```
app/                  # Python — package-by-domain
  domains/
    users/
      router.py       # HTTP layer for this domain
      schemas.py      # DTOs
      service.py      # business logic
      models.py       # ORM/entities
      repository.py   # data access
    billing/
      ...
    projects/
      ...
  shared/             # genuinely cross-cutting helpers only
  core/               # config, db engine/session, logging
  main.py
tests/
  users/  billing/  projects/
```

```
# R package — by-domain grouping within R/
R/
  users-service.R     # business logic for users
  users-repo.R        # data access for users
  billing-service.R
  billing-repo.R
  shared-utils.R
tests/testthat/
  test-users-service.R
  test-billing-service.R
# Delegate package scaffolding (DESCRIPTION, NAMESPACE, etc.) to the r-package-dev skill.
```

### Ports & Adapters (Hexagonal)
A framework-agnostic core defines **ports** (interfaces); **adapters** implement them for specific tech (DB, HTTP, queues). Dependencies point inward.

- **Pros:** core domain has zero framework/DB coupling; trivially testable with fake adapters; swap infrastructure without touching logic.
- **Cons:** more upfront indirection (interfaces, mappers); overkill for thin CRUD; team must understand the dependency rule.
- **Fits:** rich domains, many swappable integrations, heavy testing/mocking needs, long-lived cores expected to outlive their frameworks.
- **Avoid:** simple apps, framework-convention-heavy stacks where the conventions already give you enough.

```
app/                  # Python — hexagonal (one domain shown)
  domain/             # pure core: entities, value objects, domain services
    model.py
    ports.py          # interfaces: Repository, NotificationPort, ...
  application/         # use cases orchestrating the domain via ports
    use_cases.py
  adapters/
    inbound/
      http.py         # FastAPI/Flask routes calling use cases
    outbound/
      sql_repository.py     # implements Repository port
      email_notifier.py     # implements NotificationPort
  config/             # wiring: bind ports to adapters
  main.py
tests/
  domain/             # fast, no infra
  adapters/           # integration
```

### Clean / Onion
Concentric layers (entities → use cases → interface adapters → frameworks); the Dependency Rule: source dependencies point only inward. A close cousin of hexagonal with named rings.

- **Pros:** strong separation; domain independent of UI/DB/framework; very testable; clear dependency direction.
- **Cons:** most ceremony of the code-org options; mapping between layers adds boilerplate; easy to over-engineer.
- **Fits:** complex, long-lived enterprise domains; teams valuing strict dependency inversion.
- **Avoid:** small/medium apps where hexagonal or by-domain already suffice.

---

## Advanced — Data & Interaction Patterns (add on top, when justified)

### CQRS (Command Query Responsibility Segregation)
Separate the write model (commands) from the read model (queries).

- **Pros:** read and write sides scale and optimize independently; clean for complex reporting.
- **Cons:** two models to maintain; usually eventual consistency between them; significant complexity.
- **Fits:** read-heavy systems with very different read vs write shapes; alongside event sourcing.
- **Avoid:** simple CRUD; when one model serves both fine.

### Event Sourcing
Persist state as an append-only log of events; current state is a fold over events.

- **Pros:** full audit history; temporal queries; natural fit with event-driven/CQRS.
- **Cons:** high complexity; schema/versioning of events; rebuilding projections; steep learning curve.
- **Fits:** domains where history/audit is first-class (finance, ledgers).
- **Avoid:** most apps; when you don't need the history.

### Pub/Sub
Publishers emit messages to topics; subscribers consume independently. The messaging mechanism behind event-driven topologies.

- **Pros:** decouples producers/consumers; easy fan-out; buffers load.
- **Cons:** broker ops; delivery/ordering/idempotency semantics to handle.
- **Fits:** broadcasting facts to many consumers; integration backbones.
- **Avoid:** simple direct request/response.

---

## Combinations (how the axes compose)

State the composition explicitly when recommending. Common, healthy stacks:

- **MVP / small team:** Monolith + Layered. Ship fast; revisit later.
- **Long-lived service, one team (sweet spot):** Modular Monolith + By-Domain + Hexagonal boundaries. Decoupling and testability without distributed-systems tax; extract a service only when a real scaling/ownership need appears.
- **Multiple teams, mature ops:** Microservices, each internally By-Domain or Hexagonal, integrated via Event-Driven / Pub-Sub.
- **Spiky glue & automation:** Serverless functions + Event-Driven.
- **Audit-critical core:** Event Sourcing + CQRS inside a modular monolith or a dedicated service.

Rule of thumb: choose the **simplest topology** that meets scaling/ownership needs, and the **code organization** that matches domain richness — then add data patterns (CQRS, event sourcing) only when a concrete requirement demands them.
