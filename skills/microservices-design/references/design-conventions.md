# Microservices Design Conventions

> Non-obvious design forks distilled from *Building Microservices*, 2nd ed. (Newman), chapters 2–6 and 12.
> Generic best practice ("loose coupling good", "write tests", "monitor everything", ACID definitions) is assumed and omitted.
> These are design-principle rules, not project rules — nothing here is specific to any codebase.
> Chapter references in `(ch N)` instead of rationale.

## Service Boundaries

- **Draw boundaries around business domains (bounded contexts), never technical layers.** (ch2)
  - ❌ splitting into `ui-service` / `logic-service` / `data-service`, or a shared `repository-service` fronting a datastore over RPC   ← likely-default
  - ✅ `orders`, `warehouse`, `payments`, each owning its own logic *and* storage
- **Start coarse — one service per bounded context — and only subdivide into finer services later.** Resist creating many tiny services up front. (ch2, ch3)
- **Own each aggregate in exactly one service.** One service may own several aggregates; one aggregate must never be split across services. (ch2)
- **Treat an inbound state-change as a request the owning service may reject** by validating it against the aggregate's state machine — not a command it blindly applies. (ch2)
- **Don't build a service that is a thin CRUD wrapper over a table.** Public get/set over private rows leaks state-transition logic to callers and weakens cohesion. (ch2)
- **Reference an aggregate living in another service by an explicit URI or pseudo-URI, not a bare foreign-key ID.** `soundcloud:tracks:123` over `track_id = 123`. (ch2)
- **Name endpoints, events, and fields in the domain's ubiquitous language;** don't impose a generic canonical/"universal" data model across contexts. (ch2)
- **When migrating a monolith, extract incrementally (strangler-fig intercept + redirect); never big-bang rewrite,** and try scaling/other fixes before decomposing at all. (ch3)

## Coupling

- **Never read from or write to another service's database or internal tables.** The DB is not a public interface; go through the owning service's API. (ch2)
  - ❌ `SELECT ... FROM orders_db.order` from the warehouse service   ← likely-default
- **Avoid a shared mutable database across services.** Sharing *read-only static reference data* is tolerable; shared writable data is not. (ch2, ch4)
- **Don't pass data through an intermediary service purely because a further-downstream service needs it.** Either call the downstream directly, have the intermediary build the payload itself, or make the intermediary treat it as an opaque blob it never parses. (ch2)
- **Send the minimum data a call or event requires.** Every extra field becomes an assumption consumers couple to — and, in an event, part of your contract. (ch2, ch4)
- **Treat a service that depends on many downstreams as a smell** — logic has likely been over-centralized into it. (ch2)

## Communication Style

- **Pick the communication style (request-response vs event-driven, sync vs async) before picking the technology.** Don't start from a favorite tool. (ch4)
- **Don't use an event-streaming broker (e.g. Kafka) for request-response.** Match the tool to the style. (ch4)
  - ❌ Kafka topic used as an RPC call/response channel   ← likely-default
- **Drive client behavior off transport error semantics.** With HTTP: 4xx (e.g. 404) → don't retry; 503/504 and most 5xx → retryable. (ch4)
- **Publish an explicit schema for every interface, even over "schemaless" JSON.** A schemaless consumer still has a schema — just an implicit, unenforced one. (ch5)
- **Consume as a tolerant reader: extract only the fields you need and ignore the rest;** don't bind the entire payload into a strict typed object. (ch5)
  - ❌ deserializing the whole response into a fixed class that breaks when an unused field moves or disappears   ← likely-default

## Contracts & Versioning

- **Make only additive (expansion) changes to a published interface** — add fields; never remove, rename, or restructure existing ones in place. (ch5)
- **Gate CI on a schema-diff *compatibility* check that fails the build on breaking changes,** not one that merely reports a diff (Protolock / json-schema-diff-validator / openapi-diff; Confluent Schema Registry). (ch5)
- **When a breaking change is unavoidable, coexist the old and new endpoints inside one service and let consumers migrate,** then delete the old. Avoid lockstep deploys; avoid running two whole service versions side-by-side for anything longer than a canary. (ch5)

## Code Reuse

- **Never share domain or business-model code across service boundaries via a shared library** — it silently recouples them, so a model change forces a fan-out redeploy (and message-queue drains). Sharing internal-only libs (logging, transport) that are invisible outside the service is fine. (ch5)
  - ❌ a common `domain-models`/`entities` package imported by every service   ← likely-default
- **Assume multiple versions of a shared library run at once;** you cannot atomically upgrade all consumers. If a change truly must land everywhere simultaneously, expose it as a service, not a library. (ch5)
- **If you ship a client library: keep transport concerns (discovery, retries, failure handling) separate from service logic, keep server logic out of it, and let the *consumer* choose when to upgrade.** (ch5)

## Workflow & Transactions

- **Never use distributed transactions / two-phase commit to coordinate state across services.** (ch6)
  - ❌ a 2PC coordinator spanning `payments` + `warehouse` to keep an order atomic   ← likely-default
- **Model any multi-service business process as an explicit saga with compensating transactions.** You get no cross-service ACID atomicity; compensations are *semantic* rollbacks (you can't un-send an email — send a correcting one). (ch6)
- **Order saga steps so the most-likely-to-fail steps run first,** so fewer already-committed steps need compensating. (ch6)
- **Use sagas to recover from *business* failures only** (e.g. insufficient funds); handle *technical* failures (timeouts, 5xx) with the resiliency patterns below. (ch6)
- **Choose orchestration when one team owns the whole flow; choose choreography when multiple teams are involved.** (ch6)
- **Thread a single correlation ID through every call and event in a workflow** — mandatory for choreographed sagas to reconstruct state. (ch6)

## Resiliency

- **Put a timeout on every out-of-process call.** Default one everywhere, then tune from observed healthy latencies; log every timeout. A missing or huge (e.g. 30s) default lets a slow dependency hang the caller — and slow is worse than down. (ch12)
  - ❌ an out-of-process call with no timeout, or a 30s blanket default   ← likely-default
- **Set an overall operation time budget and propagate the remaining time downstream;** abort when the budget is exhausted rather than summing per-call timeouts. (ch12)
- **Use a separate connection/thread pool per downstream dependency (bulkhead),** so one slow dependency can't exhaust the pool for all of them. (ch12)
  - ❌ one shared HTTP connection pool for every downstream service   ← likely-default
- **Wrap every synchronous downstream call in a circuit breaker** that fails fast while open and probes for recovery. (ch12)
- **Retry only idempotent operations and only retryable errors** (timeouts / 5xx, not 4xx); add a delay/backoff; count retry time against the operation budget. (ch12)
- **Make an operation idempotent by carrying a business key** (e.g. the originating order ID), not by trusting HTTP-verb idempotency alone. (ch12)
- **Design explicit graceful degradation per dependency — ask "what if this is down?" for each one.** A page assembled from N services must not fail wholesale when one is unavailable. (ch12)
- **Spread instances across real failure domains (distinct availability zones / physical hosts), not just distinct logical hosts.** (ch12)

## Data & Security

- **Segregate services that handle sensitive data (PII, PCI card data) so that data never flows into out-of-scope services or networks;** narrowing that zone narrows audit and breach scope. (ch2)
- **After splitting a shared database, expect to lose DB-enforced referential integrity and cross-entity transactions** — replace them deliberately (soft deletes, denormalized copies, sagas), don't assume they still hold. (ch3)
- **Expose cross-service/reporting data through a dedicated, owned reporting database treated as a versioned public contract** — not by letting consumers query the service's internal store. (ch3)
