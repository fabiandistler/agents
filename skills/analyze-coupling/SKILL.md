---
name: analyze-coupling
category: architecture
environments: coding
description: Measure or judge how coupled or brittle a codebase is. Computes afferent and efferent coupling, Instability, Abstractness, and Distance from the Main Sequence, and finds components in the Zone of Pain or Zone of Uselessness.
compatibility: Works on any codebase. The bundled script is stdlib-only Python 3.8+. Dependency-graph extraction uses whatever tool fits the ecosystem (examples below for Python, JS/TS, Java, .NET, Go).
---

# Analyze Coupling

## When to use

Whenever the user asks to "analyze coupling", "which modules are too coupled /
brittle / tangled", "is this codebase over-abstracted", "dependency metrics
for this repo", or mentions afferent/efferent coupling, instability vs
abstractness, or the main sequence — even without naming the metrics. Goes
beyond eyeballing imports: build the dependency graph, compute Martin's
component metrics with the bundled script, classify into zones, and recommend
concrete remediation.

## Overview

Judge how coupled — and therefore how brittle or over-abstracted — a codebase
is, using the component-coupling metrics from Richards & Ford's *Fundamentals
of Software Architecture* (ch. 3) and Robert C. Martin's package metrics:
afferent/efferent coupling, **Instability** (`I`), **Abstractness** (`A`), and
**Distance from the Main Sequence** (`D = |A + I − 1|`). Components far from the
Main Sequence fall into the **Zone of Pain** (concrete and depended-upon —
brittle) or the **Zone of Uselessness** (abstract and unused — over-built).

An unaided answer tends to eyeball imports and give a vibe. This skill makes
the analysis reproducible: build the dependency graph, compute the metrics with
a bundled script, classify each component, and recommend a concrete fix — while
respecting that the numbers are blunt and need interpretation.

Definitions, formulas, the zone map, the SDP/SAP principles behind the Main
Sequence, and a worked example live in
[references/metrics.md](references/metrics.md). Fixes per zone live in
[references/remediation.md](references/remediation.md).

## When to use

- "Analyze the coupling in this repo" / "how tangled is this codebase?"
- "Which modules are too coupled / brittle / hard to change?"
- "Is this over-abstracted?" / "are we over-engineering?"
- Any mention of afferent/efferent coupling, instability, abstractness,
  distance from the main sequence, or the Zone of Pain / Uselessness.
- Getting familiar with an unfamiliar codebase, preparing for a migration, or
  assessing technical debt.

**Not for:** a single function's complexity (that's cyclomatic complexity, a
different metric), choosing an architecture from scratch (use
`architecture-pattern-advisor`), or judging whether one *specific* dependency
is acceptable at its boundary — these metrics count edges; to weigh a
relationship qualitatively (integration strength × distance × volatility),
use `balanced-coupling`.

## Workflow

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
`scripts/example_input.json`): a list of `components` and a list of `edges`.

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
- The durable cure for chronic coupling is deeper modules — **optional
  sub-skill** `codebase-design`. If the topology itself is wrong, escalate to
  `architecture-pattern-advisor`.
- Re-run the script after changes to confirm components moved toward the Main
  Sequence; the same input format makes it a repeatable baseline.

## Quick reference

| Step | Output |
|------|--------|
| 1. Unit | The one level analyzed (package / module / service / class) |
| 2. Graph | Directed `A → B` edges, normalized to the script's JSON |
| 3. Abstractness | Per-component abstract vs concrete artifact counts |
| 4. Compute | `coupling_metrics.py` table: Cᵃ, Cᵉ, I, A, D + zone |
| 5. Interpret | Per-flag explanation; real problems vs earned stability |
| 6. Remediate | Per-zone fix from `references/remediation.md` |
| 7. Record | ADR for big moves; `codebase-design` for the deeper fix |

## Common mistakes

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
