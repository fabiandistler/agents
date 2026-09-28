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
Mode A is the cohesion half of the same law. The per-scale expressions and the
classic failure shapes live in
[references/cohesion-taxonomy.md](references/cohesion-taxonomy.md#the-same-law-at-every-scale).
For *greenfield* decomposition of a system that doesn't exist yet, use
`logical-component-design` instead — this skill measures what's already there.

## When to use

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

Name the dominant relationship binding the parts, best to worst
(functional, sequential, communicational, procedural, temporal, logical,
coincidental); definitions and health judgments live in
[references/cohesion-taxonomy.md](references/cohesion-taxonomy.md#the-seven-types-best-to-worst).

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

Using the scale and definitions in the reference, name the strongest
relationship that holds the parts together. Be honest about the *dominant* one:
a class can have one functional core plus a coincidental straggler.

### 4. Structural check with LCOM (where it applies)

For anything with the structure of methods-and-fields or functions-and-shared-
state, get the structural signal from the bundled script:

```
python3 scripts/lcom.py <path...> [--lang auto|python|r|bash] [--top N] [--output FILE]
```

It reports, per class and per file, worst first (capped at `--top`, default
20, with a summary line): **clusters** (2+ means splittable — the actionable
number) and **LCOM** (higher means more pairs share nothing).

Read the result as evidence, not a verdict — see step 6 and the reference's
"What LCOM cannot tell you." Treat the script as optional: skip it for tiny
modules or where it doesn't fit, and rely on steps 2–3.

### 5. Apply the trade-off questions before recommending a split

A multi-cluster result is an *invitation* to split, not an order. Run the
three trade-off questions from the source's Customer/Order Maintenance example
([reference](references/cohesion-taxonomy.md#worked-example-when-to-split-a-module)).

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
Structure: LCOM=<n>, clusters=<n> — <what that means here>
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
is, with the Ca/Ce/I/A/D component-coupling metrics and their Main Sequence zones.

An unaided answer tends to eyeball imports and give a vibe. This mode makes
the analysis reproducible: build the dependency graph, compute the metrics with
a bundled script, classify each component, and recommend a concrete fix — while
respecting that the numbers are blunt and need interpretation.

Definitions, formulas, the zone map, the SDP/SAP principles behind the Main
Sequence, and a worked example live in
[references/metrics.md](references/metrics.md). Fixes per zone live in
[references/remediation.md](references/remediation.md).

## Coupling-metrics workflow

Follow these steps in order.

### 1. Choose the unit of analysis

Pick **one** level — package/namespace, module, deployable service, or class —
and hold it constant. The metrics are only comparable within a single level.
State the level you chose in the report; it frames everything else.

### 2. Build the dependency graph

Extract directed edges where `A → B` means "A depends on B". Use the ecosystem's
own tool rather than hand-tracing:

| Ecosystem | Tools for the dependency graph | Native metrics? |
|---|---|---|
| Python | `grimp`, `import-linter`, `tach`, `pydeps` | — |
| JS / TS | `dependency-cruiser --metrics`, `madge` | dependency-cruiser: Ca, Ce, I |
| Java / JVM | ArchUnit `ComponentDependencyMetrics`, `jdeps` | ArchUnit: Ca, Ce, I, A, D |
| .NET | NDepend | Ca, Ce, I, A, D |
| Go | `go list -deps`, `goda` | — |

If the tool emits Ca/Ce/I, use it; the script adds A/D and uniform output.

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

Treat a high `D` as a prompt to look, not a verdict.

- For each flagged component, name its zone and explain *why* it landed there
  in terms of its actual edges (what depends on it, what it depends on).
- Separate real problems from earned stability: a finished, stable, concrete
  utility everyone imports can sit in the Pain corner and be perfectly fine.
- Sanity-check the graph itself — a surprising result is often a missing or
  spurious edge, not a real coupling problem.

### 6. Remediate

For each component that is genuinely off the Main Sequence, recommend a fix from
[references/remediation.md](references/remediation.md): raise abstraction in the
Zone of Pain, remove indirection in the Zone of Uselessness, and move
dependencies toward stability.

### 7. Record and go deeper

Record significant restructuring with the `adr-workflow` skill (with the metrics
baseline); escalate topology problems to `architecture-pattern-advisor`, and
re-run the script to confirm components moved toward the Main Sequence.

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
[coupling.dev](https://coupling.dev). The author also publishes it as the
`balanced-coupling` skill in the
[vladikk/modularity](https://github.com/vladikk/modularity) plugin
(CC BY-NC-SA 4.0), with the same four strength levels and balance rule. Its core rule:

```
MODULARITY = STRENGTH XOR DISTANCE
BALANCE    = (STRENGTH XOR DISTANCE) OR NOT VOLATILITY
```

A dependency is balanced when strength and distance offset each other — heavy
knowledge-sharing is fine up close (cohesion), and only light, contract-level
knowledge should cross large distances (loose coupling). Strong coupling across
a large distance is a **knowledge leak** heading toward a distributed monolith;
it is tolerable only when the shared knowledge is stable (low volatility).

Dimension definitions, the strength levels with recognition cues, the distance
and volatility ladders, and the balance quadrants live in
[references/balanced-coupling-model.md](references/balanced-coupling-model.md).
Fixes per imbalance live in [references/rebalancing.md](references/rebalancing.md).

## Balanced-coupling workflow

The model is fractal: the same steps apply between methods, objects, packages,
services, or whole systems. Hold the level constant within one assessment.

### 1. List the dependencies to assess

Name the coupled pairs explicitly as *upstream* (owns the knowledge) and
*downstream* (depends on it); assess only relationships crossing the boundary
in question.

### 2. Classify integration strength

Identify the *strongest* kind of knowledge the downstream consumes:

| Level | The downstream depends on… |
|---|---|
| **Intrusive** | private implementation details — internals, another component's database, undocumented behavior |
| **Functional coupling** | the same business rules — duplicated or interleaved logic that must change in lockstep |
| **Model** | the upstream's model of the domain — its entities and concepts, but not its logic |
| **Contract** | an integration-specific contract that hides implementation, logic, and model |

Functional *coupling* is not Mode A's functional *cohesion*: here it is the
second-strongest level, a leak when it crosses distance, not the best grade.

### 3. Assess distance

Place the pair on the distance ladder: methods → objects → packages →
services → systems. Distance is socio-technical: a team boundary adds distance
even between services in one repo, and asynchronous integration adds lifecycle
slack. Greater distance makes each coordinated change cost more.

### 4. Assess volatility

How likely is the *shared* knowledge to change? Use the subdomain type as the
first proxy (classify with the `ddd` skill if unclear), then correct with
evidence: commit history of the shared surface, roadmap pressure, and whether
the upstream is actively evolved or in maintenance mode.

### 5. Apply the balance rule

Reduce strength and distance to high/low for the pair and check the quadrant
in [references/balanced-coupling-model.md](references/balanced-coupling-model.md#the-balance-rule)
— or run the pair through `balance_check.py`, which applies the rule uniformly
and sorts the leaks first:

```bash
python3 scripts/balance_check.py <your-input>.json
```

See `scripts/balance_check.example.json` for the format and
[references/balanced-coupling-model.md](references/balanced-coupling-model.md)
for how levels reduce to high/low.

### 6. Rebalance what's flagged

An imbalance has exactly three exits — pick per pair from
[references/rebalancing.md](references/rebalancing.md): reduce the strength
crossing the boundary, reduce the distance, or accept on proven stability with
a revisit condition (an ADR via `adr-workflow`).

### 7. Sanity-check the verdicts

Binary high/low is a deliberate simplification — recheck generous distance
guesses and optimistic stability claims against git history; low-volatility
acceptances are loans, not gifts, and need a revisit condition.

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

## Related skills

- **logical-component-design** — the generative front end: *creates* a
  decomposition for a new system; this skill *measures* one that already exists.
- **architecture-pattern-advisor** — when the topology itself is wrong, not just
  one module or dependency.
- **ddd** — subdomain classification feeds the volatility judgment in Mode C;
  aggregates are, among other things, a cohesion boundary.
- **adr-workflow** — record significant split/merge/rebalance decisions, and the
  metrics baseline that motivated them.
