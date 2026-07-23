---
name: microservices-design
category: architecture
environments: coding
description: Apply distilled microservices design conventions from Newman's *Building Microservices* when designing or reviewing how services interact. Covers boundaries, coupling, communication style, contract versioning, sagas, and resiliency patterns.
metadata:
  version: "1.0"
---

# Microservices Design

A distilled ruleset of non-obvious design forks from Sam Newman's *Building
Microservices* (2nd ed.) — the calls where an unaided implementation tends to
pick the wrong default: reading a neighbor's database, sharing a
`domain-models` package, using Kafka for request-response, reaching for 2PC,
shipping calls without timeouts, or binding whole payloads into strict typed
objects.

The binding rules live in
[references/design-conventions.md](references/design-conventions.md). **Read
that file before designing or reviewing any cross-service interaction** — the
`← likely-default` markers flag exactly the habits to override.

## When to use

Whenever the work touches an interaction between two or more services — a new
service or endpoint, an event or message schema, a shared library crossing
service boundaries, a cross-service workflow, or code that calls another
service. Not for deciding whether to use microservices at all
(→ architecture-pattern-advisor) or where domain boundaries lie
(→ ddd).

## How to apply

1. **Identify which clusters the change touches** (see map below). A single
   change usually hits two or three clusters — a new endpoint touches
   Communication Style *and* Contracts & Versioning; a new cross-service
   workflow touches Workflow & Transactions *and* Resiliency.
2. **Load the matching sections of the reference file** and walk the change
   against each rule as a pass/fail checklist. Every rule is falsifiable by
   design.
3. **Flag violations with the rule, not just an opinion.** Quote the rule and
   its `❌` example when the code matches the likely-default anti-pattern.
4. **Record consequential design calls** (e.g. choreography vs orchestration,
   breaking-change migration strategy) as an ADR via the `adr-workflow`
   skill.

## Cluster map

| Cluster | Applies when the change involves… |
|---|---|
| Service Boundaries | creating/splitting services, deciding what a service owns, monolith extraction |
| Coupling | any data access or data flow between services |
| Communication Style | choosing sync/async, request-response vs events, broker vs direct calls |
| Contracts & Versioning | changing a published interface, event schema, or API payload |
| Code Reuse | shared libraries, client libraries, common packages across services |
| Workflow & Transactions | any business process spanning more than one service |
| Resiliency | any out-of-process call — timeouts, retries, pools, breakers, degradation |
| Data & Security | sensitive data flows, reporting/analytics access, post-split integrity |

## Division of labor with related skills

- **architecture-pattern-advisor** — decides *whether* microservices are the
  right topology and where to cut boundaries; this skill governs how the
  resulting services *interact*. The boundary rules here (bounded contexts,
  database-per-service, strangler-fig) intentionally restate that skill's
  Microservice Boundary Design section so the reference file stands alone as
  a review checklist.
- **ddd** — derives the bounded contexts and aggregates that the
  Service Boundaries cluster assumes as given; context-mapping patterns live
  there.
- **coupling-cohesion** — when a specific inter-service dependency flagged by
  the Coupling cluster needs a deeper verdict (integration strength ×
  distance × volatility), hand it to that skill's balanced-coupling mode.
- **adr-workflow** — record saga orchestration choices, versioning
  strategies, and boundary decisions as ADRs.

## Source

Distilled from Sam Newman, *Building Microservices: Designing Fine-Grained
Systems*, 2nd ed. (O'Reilly, 2021), chapters 2–6 and 12, via the
`guideline-distillation` method: generic best practice is omitted; only
non-obvious forks with a wrong likely-default survive.
