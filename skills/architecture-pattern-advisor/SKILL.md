---
name: architecture-pattern-advisor
category: architecture
environments: coding
description: Choose a repository's architecture — topology (monolith, modular monolith, microservices, serverless) or code organization (layered, by-domain, hexagonal, clean/onion), not generic project setup. Includes a reusable trade-off-analysis method for weighing alternatives.
---

# Architecture Pattern Advisor

## When to Use

Help the user pick the architecture that fits *their* project, then help implement it. The decision spans two independent axes — **system topology** (how many deployable units) and **code organization** (how one unit is structured internally). They compose: a system is, for example, a *modular monolith + by-domain + hexagonal boundaries*.

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

Once chosen, document it. Use the `adr-workflow` skill to write an ADR capturing context, the decision drivers from step 2, the considered options from step 3 (the real candidates, not strawmen), and the consequences — including the downsides of the chosen option.

### 5. Implement — scaffold or migrate

- **New repo:** generate the folder/file skeleton from the annotated example tree for the chosen pattern in [references/pattern-catalog.md](references/pattern-catalog.md), adapted to the repo name and language.
- **Existing repo:** produce an **incremental migration plan** (strangler-fig): smallest first move, what moves where, keeping the build green at every step. Never a big-bang rewrite.
- Apply deep-module thinking when shaping boundaries: narrow interface, deep implementation (Ousterhout) — small interfaces hiding complexity.
- Add a boundary check to the target repo that fails CI when a module reaches into another module's internals (Python: import-linter contract or Tach; Java: Spring Modulith or ArchUnit; JavaScript/TypeScript: dependency-cruiser rule). See `fitness-functions` for the check shape.

### 6. Verify

Sanity-check the result: the project's build/test command passes and the boundary check from step 5 passes. For a migration, confirm the first step is green before listing the rest.

## Trade-off Analysis

When step 3's candidates are close or the choice is contentious, weigh the real alternatives (two is fine; for an existing repo always include the status quo) against the 3–7 characteristics that actually matter, separating short-term effects from long-run ones. Use a weighted matrix as a discussion aid, not a verdict, and record the choice with a review date via the `adr-workflow` skill (step 4).

## Once topology lands on microservices

Stop here for boundary work: find bounded contexts with `ddd`, then cut and wire services with `microservices-design`. This skill's only rule: extract from a modular monolith along module seams already proven by change-locality. Never cut along technical layers.

## Related skills

- `ddd` — use when domain boundaries are unclear and bounded contexts must be found first.
- `microservices-design` — use when services exist and their boundaries, communication, or contracts need design or review.
- `logical-component-design` — use when decomposing a new system or feature into named logical components.
- `fitness-functions` — use when a chosen boundary must be enforced by a check that fails CI.
- `c4-modeling` — use when the chosen architecture must be drawn as Context, Container, or Component diagrams.
- `coupling-cohesion` — use when measuring whether an existing decomposition is sound.
- `adr-workflow` — use when recording the chosen topology or code organization as a decision.

## Common Mistakes

- **Recommending before diagnosing.** The whole value is matching the project. Ask first.
- **Collapsing the two axes.** "Microservices" answers topology, not code organization; "hexagonal" answers code organization, not topology. Keep them separate, then compose.
- **Forcing three options.** Present only the candidates that genuinely apply; skip an axis when there is no real choice.
- **Strawman alternatives.** Each candidate's pros/cons must be honest, or the comparison is theatre.
- **Big-bang migration.** For existing repos, always incremental and build-green.
- **Stopping at a diagram.** Offer the ADR and the actual scaffolding/migration, not just an illustrative tree.
