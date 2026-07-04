---
name: analyze-cohesion
description: Analyze the cohesion of a class, module, file, or package and recommend whether to split it, merge it, or leave it. Classifies code on the best-to-worst cohesion scale (functional, sequential, communicational, procedural, temporal, logical, coincidental) and computes the LCOM (Lack of Cohesion in Methods) metric. Use this whenever code is reviewed for whether its parts belong together — a god-class or god-module, a grab-bag utility or `*Utils` / `helpers` file, "is this class doing too much", "should I split this module", separation-of-concerns questions, or any request to reason about or compute LCOM. Applies to object-oriented code AND to files or namespaces of plain functions (Python, R, Bash, and others). Also frames cohesion within the broader "zeroth law" (high cohesion, low coupling) that underlies design principles at every level from function to service, and maps classic violation patterns — God Object, Shotgun Surgery, Feature Envy — to cohesion and coupling failures.
compatibility: The bundled LCOM script needs Python 3.8+. It analyzes Python (precise, via AST), R, and Bash (heuristic) sources. The reasoning workflow is language-agnostic.
---

# Analyze Cohesion

Cohesion is the degree to which a module's parts belong together. This skill
takes a class, module, file, or package and answers three things: **which kind
of cohesion does it have**, **is the cohesion weak enough to be a problem**, and
**what — if anything — should change**.

The point is not to maximize a metric. It is to spot modules whose parts are
merely colocated rather than genuinely related, while resisting the opposite
mistake: splitting a cohesive module and re-coupling the pieces. As Larry
Constantine warned, "attempting to divide a cohesive module would only result in
increased coupling and decreased readability."

Full definitions, the source examples, and the LCOM equations live in
[references/cohesion-taxonomy.md](references/cohesion-taxonomy.md). Read it when
you need precision on a type or on the metric; this file is the workflow.

## The cohesion scale

Identify the *dominant* relationship binding the parts — the strongest one that
actually holds. Best to worst:

| Type | The parts are bound by… |
|------|-------------------------|
| **Functional** *(best)* | Everything essential to one job; nothing extra. |
| **Sequential** | One part's output is the next part's input. |
| **Communicational** | They operate on the same information / build one output. |
| **Procedural** | They must run in a particular order. |
| **Temporal** | *When* they run (e.g. startup init), not what they touch. |
| **Logical** | A category ("conversions", "string utils") — related in kind, not in function. |
| **Coincidental** *(worst)* | Nothing but being in the same file. |

Functional and sequential are healthy. Temporal, logical, and coincidental are
the smells worth flagging. Procedural and communicational sit in between — judge
them in context.

## Workflow

### 1. Scope the unit

Decide what the "module" is for this analysis: a class, a single file, a
package directory. Cohesion is scale-agnostic — the same questions apply at each
level, so be explicit about which one you are judging.

### 2. Inventory the parts and what binds them

List the parts (methods, or top-level functions) and, for each, the data it
touches — fields for a class; shared module-level symbols or called siblings for
a file of functions. You are building a mental graph: which parts are connected,
and through what.

### 3. Classify the dominant cohesion type

Using the scale above and the definitions in the reference, name the strongest
relationship that holds the parts together. Be honest about the *dominant* one:
a class can have one functional core plus a coincidental straggler.

### 4. Structural check with LCOM (where it applies)

For anything with the structure of methods-and-fields or functions-and-shared-
state, get the structural signal from the bundled script:

```
python3 skills/analyze-cohesion/scripts/lcom.py <path...> [--lang auto|python|r|bash]
```

It reports, per class and per file:
- **components** — how many disconnected clusters the parts fall into. **This is
  the actionable number:** 1 means well connected (like the book's Class X);
  2+ means the module could split into that many (Class Y / Z).
- **LCOM** — the Chidamber & Kemerer score (`|P| − |Q|`); higher means more
  pairs of parts share nothing.

Read the result as evidence, not a verdict — see step 6 and the reference's
"What LCOM cannot tell you." Treat the script as optional: skip it for tiny
modules or where it doesn't fit, and rely on steps 2–3.

### 5. Apply the trade-off questions before recommending a split

A multi-component result is an *invitation* to split, not an order. Run the
three questions from the source's Customer/Order Maintenance example
([reference](references/cohesion-taxonomy.md#worked-example-when-to-split-a-module)):

1. Is the candidate new module just a couple of operations that will never
   grow? Then collapsing it back may be better than the extra coupling.
2. Is the current module expected to grow large? Then extracting now prevents a
   god-module later.
3. Would the split force so much shared knowledge that the two modules become
   tightly coupled anyway? Then the parts are genuinely cohesive — leave them.

### 6. Recommend: split, merge, or leave — with the refactor

Give a concrete recommendation:
- **Split** — name the cluster to extract and the module it becomes; show the
  seam. (If this is a significant structural decision, record it with the
  `adr-workflow` skill.)
- **Merge** — when an over-extracted module just re-couples; fold it back.
- **Leave** — when cohesion is fine or the split would cost more than it buys.
  Saying "leave it" is a real, valuable outcome.

## Output format

Lead with the verdict, then the evidence, then the recommendation:

```
Cohesion: <type> (<one-line why>)
Structure: LCOM=<n>, components=<n> — <what that means here>
Recommendation: <split / merge / leave> — <concrete next step>
```

Keep it proportional: a clean module needs a sentence, not a report.

## Common mistakes

- **Treating LCOM as the answer.** It finds only *structural* lack of cohesion;
  it cannot tell whether parts belong together logically. Why matters more than
  how. Always close with the step-5 judgment.
- **Splitting reflexively on a high score.** A constructor or a shared cache can
  hide a real split, and a high score can flag a split that would just re-couple
  the pieces. Constantine's warning cuts both ways.
- **Conflating "low cohesion" with "bad code".** Temporal grouping (startup
  init) and some logical grouping are legitimate and stable. Flag, then judge.
- **Forgetting non-OO code.** A `helpers.py`, an R script of free functions, or a
  Bash library can be just as incohesive as a god-class. Analyze files of
  functions too.

## The zeroth law: cohesion and coupling as one meta-principle

"High cohesion, low coupling" is not a design principle alongside the others —
it is the principle the others reduce to. Whenever a design rule is under
scrutiny for *why* it is good, the answer traces back to one of two questions:

1. **Does this belong here?** — cohesion.
2. **Could I change this without touching other parts?** — coupling.

This same pair of questions repeats at every level of scale, just renamed:

| Level | Principle | Cohesion expression | Coupling expression |
|-------|-----------|----------------------|-----------------------|
| Function / method | Single Responsibility | One reason to change | Minimal side effects outward |
| Module | Deep modules | Complete, coherent problem domain | Narrow, simple interface |
| Architecture | Separation of Concerns | One layer per concern | Layers talk only through defined boundaries |
| Domain | Bounded Context | Consistent ubiquitous language within the context | Explicit context maps at the edges |
| Service | Microservices | Self-contained business capability | Loose coupling via defined APIs |

Classic anti-patterns are this law failing in a specific, recognizable shape —
treat them as symptoms to trace back to a cohesion and/or coupling root cause:

- **God Object** — high external coupling *and* low internal cohesion:
  unrelated responsibilities crammed into one place, and everything else ends
  up depending on it.
- **Shotgun Surgery** — a cohesion failure by distribution: one concern is
  scattered across many modules instead of held together in one, so a single
  change ripples everywhere.
- **Feature Envy** — a cohesion failure by wrong placement: a method cares
  more about another module's data than its own — it is living in the wrong
  home.

This framing complements, not replaces, the LCOM workflow above: LCOM is how
you make the cohesion half of the law measurable at the class/module level
(step 4). Use the two diagnostic questions as a fast first pass before
reaching for the metric, and reach for `analyze-coupling` when the question
in front of you is really about the second half of the law.
