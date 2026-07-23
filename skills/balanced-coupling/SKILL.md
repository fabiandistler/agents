---
name: balanced-coupling
category: architecture
environments: coding
description: Judge whether a specific dependency between two components is acceptable. Weigh it along Khononov's Balanced Coupling model of integration strength, distance, and volatility, not by counting edges — qualitative, one relationship at a time.
compatibility: Works on any codebase or design document. The bundled checker script is stdlib-only Python 3.8+. No dependency-graph tooling required — the assessment is qualitative, per relationship.
---

# Balanced Coupling

## When to use

When the user asks "is this coupling ok?", "should these services share this
model?", "is this dependency too strong for a service boundary?", wants to
evaluate module or service boundaries qualitatively, or mentions balanced
coupling, integration strength, knowledge leaks, shared knowledge between
components, distributed-monolith risk, or Khononov — even without naming the
model. The workflow classifies each dependency's strength, distance, and
volatility, applies the balance rule (STRENGTH XOR DISTANCE, rescued by low
volatility), and recommends how to rebalance the flagged ones.

## Overview

Judge individual dependencies by *weight*, not count: how much knowledge flows
across the boundary (**integration strength**), how far apart the coupled
components live (**distance**), and how likely that shared knowledge is to
change (**volatility**). The model is Vlad Khononov's Balanced Coupling, from
*Balancing Coupling in Software Design* (Addison-Wesley, 2024) and
[coupling.dev](https://coupling.dev). Its core rule:

```
MODULARITY = STRENGTH XOR DISTANCE
BALANCE    = (STRENGTH XOR DISTANCE) OR NOT VOLATILITY
```

A dependency is balanced when strength and distance offset each other — heavy
knowledge-sharing is fine up close (cohesion), and only light, contract-level
knowledge should cross large distances (loose coupling). Strong coupling across
a large distance is a **knowledge leak** heading toward a distributed monolith;
it is tolerable only when the shared knowledge is stable (low volatility).

This is the qualitative counterpart to `analyze-coupling`: that skill counts
and ranks dependencies with Martin's graph metrics; this one weighs a specific
relationship and tells you whether it is the *kind* of coupling that belongs at
that boundary. Use both when auditing a whole codebase — the metrics find the
hotspots, this model explains and fixes them.

Dimension definitions, the strength levels with recognition cues, the distance
and volatility ladders, and the balance quadrants live in
[references/balanced-coupling-model.md](references/balanced-coupling-model.md).
Fixes per imbalance live in [references/rebalancing.md](references/rebalancing.md).

## When to use

- "Is it ok that these two services share this domain model / database?"
- "Is this dependency too strong for a module / package / service boundary?"
- Evaluating a proposed decomposition: which pieces may stay close, which
  boundaries need a contract.
- Reviewing an integration design (API, events, shared library) for knowledge
  leaks and distributed-monolith risk.
- Any mention of balanced coupling, integration strength, shared knowledge,
  or coupling volatility.

**Not for:** computing repo-wide dependency metrics (that's
`analyze-coupling`), judging whether one module's *contents* belong together
(that's `analyze-cohesion`), or classifying subdomains and picking DDD
patterns (that's `ddd-advisor` — though its subdomain types feed step 4 here).

## Workflow

The model is fractal: the same steps apply between methods, classes, packages,
services, or whole systems. Hold the level constant within one assessment.

### 1. List the dependencies to assess

Name the coupled pairs explicitly: *upstream* (owns the knowledge) and
*downstream* (depends on it). For a focused question this is one pair; for a
boundary review, enumerate every relationship that crosses the boundary in
question. Only cross-boundary relationships need assessing — coupling wholly
inside one component is that component's own business (and `analyze-cohesion`
territory).

### 2. Classify integration strength

Identify the *strongest* kind of knowledge the downstream consumes, per the
four levels in the reference (strongest to weakest):

| Level | The downstream depends on… |
|---|---|
| **Intrusive** | private implementation details — internals, another component's database, undocumented behavior |
| **Functional** | the same business rules — duplicated or interleaved logic that must change in lockstep |
| **Model** | the upstream's model of the domain — its entities and concepts, but not its logic |
| **Contract** | an integration-specific contract that hides implementation, logic, and model |

Recognition cues per level, and how the classic module-coupling and
connascence scales map onto them, are in the reference.

### 3. Assess distance

Place the pair on the distance ladder: same function → same class/file → same
package → same component/library → same service → different systems owned by
different teams. Distance is socio-technical: a team boundary adds distance
even between services in one repo, and asynchronous integration adds lifecycle
slack. Greater distance makes each coordinated change cost more.

### 4. Assess volatility

How likely is the *shared* knowledge to change? Use the subdomain type as the
first proxy — core subdomains churn, generic ones don't (classify with
`ddd-advisor` if unclear) — then correct with evidence: commit history of the
shared surface, roadmap pressure, and whether the upstream is actively evolved
or in maintenance mode.

### 5. Apply the balance rule

Reduce strength and distance to high/low for the pair and check the quadrant:

- **High strength, low distance** — high cohesion. Balanced.
- **Low strength, high distance** — loose coupling. Balanced.
- **High strength, high distance** — knowledge leak; global complexity.
  Imbalanced unless volatility is low.
- **Low strength, low distance** — unrelated neighbors; local complexity.
  Imbalanced unless volatility is low (mostly a cohesion smell).

For more than a couple of pairs, record the assessments in the checker's JSON
format and run it — it applies the rule uniformly and sorts the leaks first:

```bash
python3 scripts/balance_check.py <your-input>.json
```

See `scripts/example_input.json` for the format and
[references/balanced-coupling-model.md](references/balanced-coupling-model.md)
for how levels reduce to high/low.

### 6. Rebalance what's flagged

An imbalance has exactly three exits — pick per pair, using
[references/rebalancing.md](references/rebalancing.md):

- **Reduce strength**: introduce or harden a contract at the boundary so less
  knowledge crosses it (intrusive → functional → model → contract).
- **Reduce distance**: co-locate what genuinely must change together — merge
  services, move code into one package, put it under one team.
- **Accept, eyes open**: if the shared knowledge is demonstrably stable,
  document the imbalance and the stability assumption (an ADR via
  `adr-workflow`) so it is revisited when volatility returns.

### 7. Sanity-check the verdicts

Binary high/low is a deliberate simplification — the book grades each
dimension on finer scales. Before reporting: a "balanced" verdict built on a
generous distance guess or an optimistic "that model never changes" is worth
rechecking against git history; and low-volatility acceptances are loans, not
gifts — they must carry a revisit condition.

## Quick reference

| Step | Output |
|------|--------|
| 1. Pairs | Upstream → downstream list at one abstraction level |
| 2. Strength | Intrusive / functional / model / contract per pair |
| 3. Distance | Rung on the ladder, adjusted for team boundaries |
| 4. Volatility | High/low with the evidence (subdomain type, churn) |
| 5. Balance | Quadrant per pair; `balance_check.py` table for many |
| 6. Rebalance | Reduce strength, reduce distance, or accept via ADR |
| 7. Sanity | Verdicts challenged; acceptances given revisit conditions |

## Common mistakes

- **Counting instead of weighing.** One intrusive dependency outweighs a
  hundred contract-coupled ones. Never report "N dependencies" as the finding.
- **Calling every strong coupling bad.** High strength at low distance is
  cohesion — the good kind. Only strength *across distance* leaks knowledge.
- **Ignoring volatility.** A stable big ball of mud may be a perfectly sound
  thing to leave alone; flagging it wastes the team's change budget.
- **Contract in name only.** An "API" that mirrors the upstream's internal
  entities field-for-field is model coupling wearing a contract's clothes.
  A contract must be a model *of* the model, owned by the boundary.
- **Mixing abstraction levels.** Method-level and service-level assessments
  don't compare. Fix the level in step 1 and stay there.
