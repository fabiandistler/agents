---
name: coupling-cohesion
category: architecture
environments: coding
description: Assess an existing codebase's coupling and cohesion — module cohesion and LCOM, codebase-wide coupling metrics and zones, or whether a single dependency is balanced (Khononov).
compatibility: The bundled scripts are stdlib-only Python 3.8+. LCOM analyzes Python (precise, via AST), R, and Bash (heuristic); the coupling and balance checks are language-agnostic. Dependency-graph extraction uses whatever tool fits the ecosystem (examples below for Python, JS/TS, Java, .NET, Go).
---

# Coupling & Cohesion

"High cohesion, low coupling" is the meta-principle most design rules reduce to.
This skill **measures existing code** along both axes and picks the right lens
for the question in front of you:

| Mode | The question | Jump to |
|---|---|---|
| **A. Cohesion** | Do this module/class/file's parts belong together — split, merge, or leave? | [Mode A](#mode-a--cohesion-of-a-module) |
| **B. Codebase coupling** | How coupled / brittle / over-abstracted is the codebase, by the numbers? | [Mode B](#mode-b--codebase-wide-coupling-metrics) |
| **C. Balanced coupling** | Is this *one specific* dependency the right kind of coupling for its boundary? | [Mode C](#mode-c--is-one-dependency-balanced) |

Modes B and C are complementary halves of a coupling audit: the metrics (B) find
the hotspots, the balance model (C) explains and fixes a specific relationship.
Mode A is the cohesion half of the same law. For *greenfield* decomposition of a
system that doesn't exist yet, use `logical-component-design` instead — this
skill measures what's already there.

## When to use

Whenever existing code is reviewed for whether its parts belong together or how
tangled it is — a god-class or `*Utils` grab-bag, "is this class doing too
much", "should I split this module", "analyze coupling", "which modules are too
coupled / brittle / tangled", "is this over-abstracted", "is it ok that these
two services share this model", knowledge leaks, distributed-monolith risk, or
any mention of LCOM, afferent/efferent coupling, instability, abstractness,
distance from the main sequence, the Zone of Pain / Uselessness, integration
strength, or Khononov — even without naming the metric or model. Applies to
object-oriented code *and* files or namespaces of plain functions (Python, R,
Bash, and others).

**Not for:** a single function's cyclomatic complexity, choosing an architecture
from scratch (use `architecture-pattern-advisor`), or greenfield component
decomposition (use `logical-component-design`).

---

# Mode A — Cohesion of a module

Cohesion is the degree to which a module's parts belong together. This mode
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
you need precision on a type or on the metric; this section is the workflow.

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

## Cohesion workflow

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
python3 skills/coupling-cohesion/scripts/lcom.py <path...> [--lang auto|python|r|bash]
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

## Cohesion output format

Lead with the verdict, then the evidence, then the recommendation:

```
Cohesion: <type> (<one-line why>)
Structure: LCOM=<n>, components=<n> — <what that means here>
Recommendation: <split / merge / leave> — <concrete next step>
```

Keep it proportional: a clean module needs a sentence, not a report.

## Cohesion — common mistakes

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

---

# Mode B — Codebase-wide coupling metrics

Judge how coupled — and therefore how brittle or over-abstracted — a codebase
is, using the component-coupling metrics from Richards & Ford's *Fundamentals
of Software Architecture* (ch. 3) and Robert C. Martin's package metrics:
afferent/efferent coupling, **Instability** (`I`), **Abstractness** (`A`), and
**Distance from the Main Sequence** (`D = |A + I − 1|`). Components far from the
Main Sequence fall into the **Zone of Pain** (concrete and depended-upon —
brittle) or the **Zone of Uselessness** (abstract and unused — over-built).

An unaided answer tends to eyeball imports and give a vibe. This mode makes
the analysis reproducible: build the dependency graph, compute the metrics with
a bundled script, classify each component, and recommend a concrete fix — while
respecting that the numbers are blunt and need interpretation.

Definitions, formulas, the zone map, the SDP/SAP principles behind the Main
Sequence, and a worked example live in
[references/metrics.md](references/metrics.md). Fixes per zone live in
[references/remediation.md](references/remediation.md).

## Coupling-metrics workflow

Follow these steps in order. The interpretation step is what separates a useful
report from a misleading one — do not skip it to hand back a ranked table.

### 1. Choose the unit of analysis

Pick **one** level — package/namespace, module, deployable service, or class —
and hold it constant. The metrics are only comparable within a single level.
State the level you chose in the report; it frames everything else.

### 2. Build the dependency graph

Extract directed edges where `A → B` means "A depends on B". Use the ecosystem's
own tool rather than hand-tracing:

| Ecosystem | Tools for the dependency graph |
|---|---|
| Python | `pydeps`, `import-linter`, `grimp` |
| JS / TS | `dependency-cruiser`, `madge` |
| Java / JVM | JDepend, ArchUnit, `jdeps` |
| .NET | NDepend, `dotnet` analyzers |
| Go | `go list -deps`, `goda` |

Normalize the output into the script's JSON input (see
`scripts/coupling_metrics.example.json`): a list of `components` and a list of
`edges`.

### 3. Gather abstractness data

For each component, count abstract artifacts (interfaces, abstract classes,
protocols, traits) vs concrete ones, and put the counts in each component as
`abstract` / `concrete`. This is what makes Abstractness and `D` computable. If
abstractness is impractical to gather for a component, omit the counts — the
script will report its instability only and mark `A`/`D` as not available.

### 4. Compute the metrics

Run the bundled script:

```bash
python3 scripts/coupling_metrics.py <your-input>.json
```

It prints a markdown table of `Cᵃ`, `Cᵉ`, `I`, `A`, `D` and a zone label per
component, sorted worst-`D` first, and flags everything past the threshold
(`--threshold`, default 0.5). Use `--json` to pipe the numbers elsewhere. See
[references/metrics.md](references/metrics.md) for how each number is derived.

### 5. Interpret — don't just rank

This is the step that makes the report honest. Per the book's *Limitations of
Metrics*: these are blunt instruments that **cannot distinguish essential from
accidental complexity**, so treat a high `D` as a prompt to look, not a verdict.

- For each flagged component, name its zone and explain *why* it landed there
  in terms of its actual edges (what depends on it, what it depends on).
- Separate real problems from earned stability: a finished, stable, concrete
  utility everyone imports can sit in the Pain corner and be perfectly fine.
- Sanity-check the graph itself — a surprising result is often a missing or
  spurious edge, not a real coupling problem.

### 6. Remediate

For each component that is genuinely off the Main Sequence, recommend a fix from
[references/remediation.md](references/remediation.md):

- **Zone of Pain** → introduce an interface/port over the depended-upon surface,
  apply Dependency Inversion, split God-modules. Raise abstraction where others
  depend (Stable Abstractions Principle).
- **Zone of Uselessness** → delete speculative abstraction, inline
  single-implementation interfaces, collapse pass-through layers.
- Move dependencies toward stability (Stable Dependencies Principle).

### 7. Record and go deeper

- For significant restructuring, capture the decision (and the metrics baseline
  that motivated it) with the `adr-workflow` skill.
- The durable cure for chronic coupling is deeper modules — see `codebase-design`.
  If the topology itself is wrong, escalate to `architecture-pattern-advisor`.
- Re-run the script after changes to confirm components moved toward the Main
  Sequence; the same input format makes it a repeatable baseline.

## Coupling metrics — common mistakes

- **Mixing levels.** Counting class edges and package edges in one graph makes
  the metrics meaningless. Pick one unit (step 1).
- **Reporting numbers as verdicts.** The metrics flag *where to look*; they
  can't tell essential from accidental complexity. Always interpret (step 5).
- **Condemning earned stability.** A stable, concrete, finished utility in the
  Pain corner may need no change. High `D` ≠ defect.
- **Fixing Uselessness by adding abstraction.** It's already too abstract —
  remove indirection, don't add it.
- **Trusting a bad graph.** Garbage edges in, garbage metrics out. Verify the
  extractor drew the dependencies you expect before believing the table.

---

# Mode C — Is one dependency balanced?

Judge an individual dependency by *weight*, not count: how much knowledge flows
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

This is the qualitative counterpart to Mode B: that mode counts and ranks
dependencies with Martin's graph metrics; this one weighs a specific
relationship and tells you whether it is the *kind* of coupling that belongs at
that boundary. Use both when auditing a whole codebase — the metrics find the
hotspots, this model explains and fixes them.

Dimension definitions, the strength levels with recognition cues, the distance
and volatility ladders, and the balance quadrants live in
[references/balanced-coupling-model.md](references/balanced-coupling-model.md).
Fixes per imbalance live in [references/rebalancing.md](references/rebalancing.md).

## Balanced-coupling workflow

The model is fractal: the same steps apply between methods, classes, packages,
services, or whole systems. Hold the level constant within one assessment.

### 1. List the dependencies to assess

Name the coupled pairs explicitly: *upstream* (owns the knowledge) and
*downstream* (depends on it). For a focused question this is one pair; for a
boundary review, enumerate every relationship that crosses the boundary in
question. Only cross-boundary relationships need assessing — coupling wholly
inside one component is that component's own business (Mode A territory).

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
first proxy — core subdomains churn, generic ones don't (classify with the `ddd`
skill if unclear) — then correct with evidence: commit history of the shared
surface, roadmap pressure, and whether the upstream is actively evolved or in
maintenance mode.

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

See `scripts/balance_check.example.json` for the format and
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

## Balanced coupling — common mistakes

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

---

# The zeroth law: cohesion and coupling as one meta-principle

"High cohesion, low coupling" is not a design principle alongside the others —
it is the principle the others reduce to. Whenever a design rule is under
scrutiny for *why* it is good, the answer traces back to one of two questions:

1. **Does this belong here?** — cohesion (Mode A).
2. **Could I change this without touching other parts?** — coupling (Modes B/C).

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

Use the two diagnostic questions as a fast first pass before reaching for any
metric: Mode A makes the cohesion half measurable (LCOM), Modes B and C make the
coupling half measurable (graph metrics) and judgeable (the balance model).

## Related skills

- **logical-component-design** — the generative front end: *creates* a
  decomposition for a new system; this skill *measures* one that already exists.
- **codebase-design** — the deep-module vocabulary; the durable cure for chronic
  coupling and low cohesion alike.
- **architecture-pattern-advisor** — when the topology itself is wrong, not just
  one module or dependency.
- **ddd** — subdomain classification feeds the volatility judgment in Mode C;
  aggregates are, among other things, a cohesion boundary.
- **adr-workflow** — record significant split/merge/rebalance decisions, and the
  metrics baseline that motivated them.
