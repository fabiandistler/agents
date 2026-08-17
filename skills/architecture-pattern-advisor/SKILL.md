---
name: architecture-pattern-advisor
category: architecture
environments: coding
description: Use when choosing the architecture of a repository — topology (monolith, modular monolith, microservices, serverless) or code organization (layered, by-domain, hexagonal, clean/onion). Includes a reusable trade-off-analysis method for weighing alternatives. Not for generic project setup with no architecture-shape decision.
---

# Architecture Pattern Advisor

## Overview

Help the user pick the architecture that fits *their* project, then help them implement it. The decision spans two independent axes — **system topology** (how many deployable units) and **code organization** (how one unit is structured internally). They compose: a system is, for example, a *modular monolith + by-domain + hexagonal boundaries*.

An unaided answer tends to (1) jump straight to one opinionated recommendation, (2) blend the two axes, and (3) stop at a folder diagram. This skill instead **diagnoses first, presents up to three candidates per axis with honest trade-offs, records the decision, and scaffolds or migrates.**

## When to Use

- "Which architecture / pattern should I use for this project?"
- "How should I structure this repo?" / "organize the code?"
- "Monolith or microservices?" / "should I split this into services?"
- "by-domain vs by-layer", "hexagonal / ports & adapters", "clean architecture", "onion"
- Restructuring an existing repo whose layout has become hard to maintain

**Not for:** generic project bootstrapping with no shape decision ("run `uv init`", "create a new file", "set up CI").

## Workflow

Follow these steps in order. Do not skip step 2 to reach a recommendation faster — the diagnosis is what makes the recommendation honest.

### 1. Establish context: new or existing repo

- **Existing repo:** inspect it read-only first — main language, build system, current layout. Name the current pattern and any smells (God-modules, circular dependencies, technical-only layering, business logic in transport/ORM code). Read [references/decision-drivers.md](references/decision-drivers.md) for what to look for.
- **New repo:** go straight to diagnosis.

### 2. Diagnose — ask before recommending

Ask a short, focused set of the diagnostic questions in [references/decision-drivers.md](references/decision-drivers.md): project type and language, team size, domain complexity, scaling and deployment needs, independent deployability, data-consistency needs, testability and external integrations, expected lifetime and rate of change, operational maturity (CI/CD, observability).

Ask the few that actually discriminate for this project — not all of them. Prefer one multiple-choice question at a time. **Recommend nothing until you have these answers.**

### 3. Recommend — up to three candidates per axis, topology first

Work the two axes **sequentially**: first topology, then code organization. For each axis, present the candidates using this exact shape:

- **Every candidate gets the same treatment** — recommended option and alternatives alike: a one-line definition, **Pros**, and **Cons**. Honest trade-offs, no strawmen. The recommended option is not exempt from showing its cons.
- Put the **recommended option first** and label it as recommended; in addition to its pros/cons, give it one "fits you because …" line grounded in the diagnosis answers.
- Up to three candidates per axis. Present **fewer** when the context makes an option irrelevant — do **not** invent a third. (A small library or R package usually has no real topology choice; skip the topology axis entirely and say so.)
- Close by stating how the chosen topology and code organization compose.

Pull the candidate set, their pros/cons, and "when it fits / when to avoid" from [references/pattern-catalog.md](references/pattern-catalog.md). Map diagnosis answers to candidates using the heuristic table in [references/decision-drivers.md](references/decision-drivers.md).

Let the user choose. If they pick against the recommendation, accept it and note any consequence worth flagging.

### 4. Record the decision as an ADR

Once chosen, document it. **REQUIRED SUB-SKILL:** use the `adr-workflow` skill to write an ADR capturing context, the decision drivers from step 2, the considered options from step 3 (the real candidates, not strawmen), and the consequences — including the downsides of the chosen option.

### 5. Implement — scaffold or migrate

- **New repo:** generate the folder/file skeleton from the annotated example tree for the chosen pattern in [references/pattern-catalog.md](references/pattern-catalog.md), adapted to the repo name and language.
- **Existing repo:** produce an **incremental migration plan** (strangler-fig): smallest first move, what moves where, keeping the build green at every step. Never a big-bang rewrite.
- Apply deep-module thinking when shaping boundaries: small interfaces hiding complexity.

### 6. Verify

Sanity-check the result: Python — package imports, a minimal `pyproject.toml`; R — package loads via `devtools::load_all()`. For a migration, confirm the first step builds before listing the rest.

## Trade-off Analysis

Every architecture decision trades some qualities for others — there is no dominant option once real constraints apply. Use this five-step method whenever step 3's candidates are close or the choice is contentious, before writing the ADR.

1. **Define the context.** Business requirements, technical constraints, stakeholder needs, and the timeline/budget envelope — the same inputs gathered in step 2 (Diagnose).
2. **Generate at least three alternatives**, including a genuine "do nothing" / status-quo option. Don't stop at the first two options that come to mind; include an extreme or hybrid option if one realistically applies.
3. **Weight the relevant -ilities.** Pick the 3–7 characteristics that actually matter for this decision (performance, maintainability, cost, scalability, time-to-market, etc. — see the diagnostic questions in [references/decision-drivers.md](references/decision-drivers.md)) and assign each a weight; not all qualities matter equally for a given project.
4. **Analyze trade-offs short-term vs. long-term.** For each alternative, separate immediate effects (time-to-market, initial cost) from long-run effects (maintainability, technical debt, lock-in), and note which assumptions the analysis depends on.
5. **Document the decision with a review date.** Record the chosen alternative, the rejected ones and why, the accepted downsides, and *when* to re-evaluate — conditions change, and a decision that was right last year may not be right today.

This output is ADR-ready: use the `adr-workflow` skill (step 4 of the Workflow) to turn steps 1–2 into the ADR's Context and Considered Options, and steps 3–5 into Decision Drivers and Consequences.

### Scoring-matrix shape

Use a weighted matrix when more than two close alternatives need a side-by-side comparison:

| Characteristic | Weight | Option A | Option B | Option C |
|---|---|---|---|---|
| Performance | 30% | 8/10 | 6/10 | 9/10 |
| Maintainability | 25% | 9/10 | 7/10 | 5/10 |
| Cost | 20% | 6/10 | 9/10 | 7/10 |
| Scalability | 15% | 7/10 | 8/10 | 9/10 |
| Time-to-market | 10% | 5/10 | 9/10 | 6/10 |
| **Weighted avg** | | **7.4** | **7.5** | **7.3** |

Treat the weighted average as a discussion aid, not a verdict — a close score is a signal to re-check the weights or surface a qualitative factor the matrix can't capture, not to default to the highest number.

## Microservice Boundary Design

When the topology axis lands on microservices — or an existing repo is being decomposed into them — the hardest and most consequential call is where to cut. Apply these checks before finalizing service boundaries in step 5 (Implement):

- **Bounded context as the natural boundary.** A domain's bounded context — the boundary within which a model and its terms carry one consistent meaning — is the strongest starting point for a service boundary. Context boundaries change more slowly than technical architecture, so services cut along them stay stable longer. If contexts aren't already identified, use the `ddd` skill to find and map them first; this skill consumes that boundary, it doesn't derive it (context-mapping patterns live there, not here).
- **Start wide, decompose later.** "As small as possible" is an anti-heuristic for cutting services: size a boundary as a function of the model it protects, not of a target service count. For core or volatile subdomains especially, keep the boundary wide (fewer, larger services) until the model is understood — refactoring a *logical* boundary inside one deployable is cheap, while moving a *physical* service boundary (APIs, data ownership, deploy pipelines, consumers) is expensive. Defaulting to microservices before the model is understood locks in guesses at the most expensive layer.
- **Cohesion / change-locality test.** A well-cut service absorbs a change entirely within itself. If two or more services are habitually modified together for the same feature, that is a direct signal the cut is wrong — either the boundary split a single cohesive capability, or a shared concept was duplicated incorrectly. Treat repeated cross-service changes for one feature as a boundary smell, not a normal cost of doing business.
- **Database-per-service.** Each service owns its data exclusively; other services reach it only through its API, never through a direct foreign-database connection or shared schema. A shared database is coupling in disguise — it silently reintroduces the monolith's shared-state problem across process boundaries. Expect some data duplication and eventual consistency as the accepted trade-off (see Trade-off Analysis above); resolve cross-service queries with API composition or CQRS rather than joins.
- **Anti-pattern: cutting along technical layers.** Do not carve out a "data-access service," "business-logic service," or "UI service" — that is the by-layer code-organization mistake (see the Code-organization axis in [references/pattern-catalog.md](references/pattern-catalog.md)) applied at the topology level, and it produces the worst of both: network calls for what used to be a function call, with none of the domain cohesion microservices are meant to buy. Name services after business capabilities (`Order Service`, `Customer Service`), not technical roles.

## Quick Reference

| Step | Output |
|------|--------|
| 1. Context | New vs existing; for existing, current pattern + smells |
| 2. Diagnose | Answers to the few discriminating decision-driver questions |
| 3. Recommend | Topology candidates (≤3, recommended first, pros/cons), then code-org candidates, then how they compose |
| 4. Record | ADR via `adr-workflow` |
| 5. Implement | New: scaffold from annotated tree. Existing: incremental migration plan |
| 6. Verify | Structure imports/builds |

## Common Mistakes

- **Recommending before diagnosing.** The whole value is matching the project. Ask first.
- **Collapsing the two axes.** "Microservices" answers topology, not code organization; "hexagonal" answers code organization, not topology. Keep them separate, then compose.
- **Forcing three options.** Present only the candidates that genuinely apply; skip an axis when there is no real choice.
- **Strawman alternatives.** Each candidate's pros/cons must be honest, or the comparison is theatre.
- **Big-bang migration.** For existing repos, always incremental and build-green.
- **Stopping at a diagram.** Offer the ADR and the actual scaffolding/migration, not just an illustrative tree.
