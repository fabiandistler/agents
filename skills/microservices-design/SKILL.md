---
name: microservices-design
category: architecture
environments: coding
description: Guides microservice interaction design and review — boundaries, coupling, communication style, contract versioning, sagas, and resiliency patterns from Newman's *Building Microservices*. Use when designing or reviewing how services communicate.
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

For review, use each rule's negative example to locate the matching code shape.

## When to use

Whenever the work touches an interaction between two or more services — a new
service or endpoint, an event or message schema, a shared library crossing
service boundaries, a cross-service workflow, or code that calls another
service. Read `members/architecture-pattern-advisor/SKILL.md` via the
`architecture` router to choose the topology, size boundaries or extract services.
Read `members/ddd/SKILL.md` via the same router to derive bounded contexts and
aggregates or choose context-mapping patterns.

## How to apply

1. **Identify which clusters the change touches** (see map below). A single
   change usually hits two or three clusters — a new endpoint touches
   Communication Style *and* Contracts & Versioning; a new cross-service
   workflow touches Workflow & Transactions *and* Resiliency.
2. Read [references/design-conventions.md](references/design-conventions.md)
   before designing or reviewing any interaction. Check each rule in the
   matching sections as pass/fail.
3. **Flag violations with the rule, not just an opinion.** Quote the rule, and
   its `❌` example when the code matches that shape.
4. **Record consequential design calls** (e.g. choreography vs orchestration,
   breaking-change migration strategy) as an ADR.

## Cluster map

| Cluster | Applies when the change involves… |
|---|---|
| Service Boundaries | creating/splitting services, deciding what a service owns, monolith extraction |
| Coupling | any data access or data flow between services |
| Communication Style | choosing sync/async, request-response vs events, broker vs direct calls |
| Contracts & Versioning | changing a published interface, event schema, or API payload |
| Code Reuse | shared libraries, client libraries, common packages across services |
| Workflow & Transactions | any business process spanning more than one service |
| Messaging Reliability | publishing or consuming events, outbox use, at-least-once delivery, consumer dedupe |
| Resiliency | any out-of-process call — timeouts, retries, pools, breakers, degradation |
| Data & Security | sensitive data flows, reporting/analytics access, post-split integrity |

For modules in a modular monolith, Coupling / Contracts / Code Reuse apply; Resiliency does not.

## Division of labor with related skills

Sibling sub-skills, each read via the `architecture` router:
- `members/coupling-cohesion/SKILL.md` — when a specific inter-service dependency flagged by
  the Coupling cluster needs a deeper verdict (integration strength ×
  distance × volatility), hand it to that skill's balanced-coupling mode.

## Source

Distilled from Sam Newman, *Building Microservices: Designing Fine-Grained
Systems*, 2nd ed. (O'Reilly, 2021), chapters 2–6, 9, and 12.
