---
name: logical-component-design
category: architecture
environments: coding
description: Forward, generative decomposition of a NEW system or feature into named logical components — Richards & Ford's iterative identify-and-refine cycle. Creates the decomposition; measuring an existing one is analyze-cohesion.
---

# Logical Component Design

A **logical component** is a building block of the system with a distinct role —
represented in code as a namespace or directory (`com.app.order.placement`,
`order/placement/`). This skill takes a system or feature you are *about to
build* and produces a first set of named components, then refines them. It is the
generative front end to the analysis skills: it *creates* the decomposition;
`analyze-cohesion` and `analyze-coupling` *measure* one that already exists.

The core idea, from *Fundamentals of Software Architecture* (ch. 8), is that
component identification is an **iterative feedback loop**, not a one-shot act of
getting it right. You know least about the system at the very start, so trying to
perfect the initial components is wasted effort. Make a best guess, assign work
to it, see where it strains, and restructure. The loop never fully stops — it
runs on greenfield systems and every time a feature is added or changed.

Detailed approaches, worked examples, the Going-Going-Gone case study, and a
fill-in worksheet live in
[references/component-identification.md](references/component-identification.md).

## When to use

Whenever someone is starting a design and asks "what components / modules do I
need for …", "how do I break this new system into components", "decompose this
domain", "how should I organize these user stories into components", or
"identify the building blocks for my <app>", or is filling empty buckets,
applying the Workflow or Actor/Action approach, or worrying about the Entity
Trap — even without naming the book. Produces descriptively-named components
with role statements, assigned user stories, and a coupling/Law-of-Demeter
refinement pass. Not for analyzing existing code (→ analyze-cohesion /
analyze-coupling) or choosing system topology and folder layout
(→ architecture-pattern-advisor).
Read it when you need the full examples or the worksheet; this file is the
workflow.

## The cycle

Run these five steps in order, then loop. Enter at whatever step matches what the
user already has (they may arrive with components and only need step 3–5).

### 1. Identify initial core components

Think of each component as an **empty bucket**: a placeholder named for its
proposed role, with no responsibilities yet. Pick one of two approaches to
generate the initial buckets — and avoid a third that looks tempting.

- **Workflow approach** — walk the major happy-path (non-error) workflows a user
  takes through the system and assign a component to each meaningful step. It is
  *not* one component per step: steps that do the same job share a component
  (e.g. two "notify the customer" steps both map to `Customer Notification`).
  Good when you know the general flow but not the detailed requirements yet.
- **Actor/Action approach** — list the actors, **including the system itself**
  (it performs automated actions like billing or restocking), and the major
  actions each takes; map actions to components. Generates more, finer-grained
  components than the Workflow approach. It is the sensible **default** when
  there are no special constraints and you want a good general decomposition.
- **Entity Trap (antipattern — avoid)** — deriving components from entities
  (`Customer` → `Customer Manager`, `Order` → `Order Manager`). Avoid it:
  entity-noun names describe nothing ("Order Manager manages orders"), and the
  component becomes a dumping ground for every bit of order logic — a god-
  component that is hard to test and deploy. Red-flag suffixes: **Manager,
  Supervisor, Controller, Handler, Engine, Processor**. Prefer role names that
  say what the component *does* — `Validate Order`, not `Order Manager`.
  *(Escape hatch: if the system truly is CRUD over entities with no real logic,
  it doesn't need an architecture at all — reach for a CRUD/low-code framework.)*

### 2. Assign user stories / requirements to components

Start filling the buckets: attach each user story or requirement to the
component whose role it belongs to. This is what gives a component its concrete
responsibility. When a story fits **no** existing component cleanly — a cross-
cutting concern like "email the customer on every status change" that three
components would otherwise duplicate — that is the signal to **create a new
component** (`Customer Notification`) and have the others communicate with it,
rather than copying the code. Stories arrive over time, so this step recurs.

### 3. Analyze roles and responsibilities (cohesion)

Check that each component's assigned work actually belongs together and that no
component is doing too much. Write a one-paragraph **role and responsibility
statement** for the component and read it critically:

> The **conjunction test**: if the statement leans on *and*, *also*, *in
> addition*, *as well as*, or a pile-up of commas to list what the component
> does, it is probably carrying too many responsibilities → split it.

Because a component maps to a single directory/namespace, "too much
responsibility" is also literally "too much code in one place." Extract the
strayed responsibilities into their own components (e.g. pull payment,
inventory, and email out of an over-broad `Order Placement`). For a deeper,
metric-backed split/merge/leave decision on a specific class or module, hand off
to the **`analyze-cohesion`** skill.

### 4. Analyze architectural characteristics

Look at the architecture characteristics the system must support — scalability,
reliability, availability, elasticity, fault tolerance, agility — and ask whether
any of them should reshape a component. A purely functional view might put all of
some capability in one component, but differing characteristic needs can force a
split: in the GGG auction, one `Bid Capture` component handled bids from both
bidders and the auctioneer, but bidders need high scalability/elasticity
(thousands of them) while the auctioneer needs high reliability/availability
(one connection that must not drop) — so it splits into `Bid Capture` and
`Auctioneer Capture`. This step assumes you already know which characteristics
matter most; determine those first.

### 5. Restructure and iterate

Feedback is the point. Expect to restructure components frequently across the
whole lifecycle — not just on greenfield systems — as edge cases surface and you
and the developers understand the behaviors more deeply. Fold the results back
into step 1 and go around again. Stopping "because the diagram is done" is the
mistake; the loop is the method.

## Refinement lens: coupling

Once a candidate set of components exists, examine how they depend on each other
— more coupling means the system is harder to maintain and test.

- **Static coupling** — synchronous dependencies. Two directions to track per
  component: **afferent coupling (Cᴀ)**, the incoming / fan-in count of other
  components that depend on it (e.g. `Customer Notification`, called by both
  `Order Placement` and `Order Shipment`, has Cᴀ = 2); and **efferent coupling
  (Cᴇ)**, the outgoing / fan-out count of components it depends on.
- **Temporal coupling** — non-static dependencies of timing or transaction
  order: `Order Placement` must run before `Order Shipment`. Tooling rarely
  catches this; surface it from the design and note it explicitly.

For coupling **metrics on code that already exists** (instability, distance from
the main sequence, zones of pain/uselessness), hand off to **`analyze-coupling`**.

## Refinement lens: Law of Demeter (Least Knowledge)

A component should have **limited knowledge** of the rest of the system — the
Principle of Least Knowledge. Knowledge is coupling: if `Order Placement` knows
that inventory must be decremented, *and* that low stock means reorder from a
supplier, *and* that low stock means adjust the price, *and* that the customer
must be emailed, it is tightly coupled to four components. Push the knowledge
that doesn't have to live there *into* the downstream component (let `Inventory
Management` own the "if stock is low, reorder and reprice" knowledge), shrinking
the hub's efferent coupling.

Be honest about the trade-off: applying the Law of Demeter usually
**redistributes** coupling rather than removing it system-wide — the downstream
component's coupling goes up as the hub's goes down. Move knowledge to where it
naturally belongs, don't just chase a lower number on one node.

## Output format

Lead with the approach used, then the component table, then what's still open.
Keep it proportional — a small feature needs a few rows, not a report.

```
Approach: <Workflow | Actor/Action> — <one-line why>

| Component | Role / responsibility | Assigned stories | Cᴀ / Cᴇ | Notes |
|-----------|-----------------------|------------------|---------|-------|
| ...       | (single-sentence role, passes the conjunction test) | ... | .. | ... |

Characteristics reviewed: <which -ilities drove any split>
Next iteration / open questions: <what to revisit as requirements firm up>
```

## Common mistakes

- **Perfectionism up front.** You know least at the start; iterate instead.
- **The Entity Trap.** `*Manager` / `*Handler` names and god-components; name for
  role, not entity.
- **One component per step / per action.** Reused steps and actions share a
  component; don't inflate the count mechanically.
- **Skipping the characteristics pass.** Function-only decomposition misses
  splits that scalability or reliability demand.
- **Treating the first design as final.** Restructuring is expected, continuously.
- **Chasing "the one true design."** Few systems have only one valid
  decomposition. Assess trade-offs honestly and pick the **least-worst** set.

## Source

Mark Richards & Neal Ford, *Fundamentals of Software Architecture*, 2nd ed.
(O'Reilly), ch. 8, "Component-Based Thinking" — the component identification and
refactoring cycle, the Workflow / Actor-Action approaches, the Entity Trap,
component coupling, and the Law of Demeter.
