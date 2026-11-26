# Mode A — Cohesion of a module

Cohesion is the degree to which a module's parts belong together. This mode
takes a class, module, file, or package and answers three things: **which kind
of cohesion does it have**, **is the cohesion weak enough to be a problem**, and
**what — if anything — should change**.

## Contents

- [The cohesion scale](#the-cohesion-scale)
- [Cohesion workflow](#cohesion-workflow)
- [Cohesion output format](#cohesion-output-format)
- [Cohesion — worked contrast](#cohesion--worked-contrast)

Assess classes and other units, including files of functions, using the same
cohesion questions. A reusable seam keeps the parts cohesive without merely
shifting their shared knowledge to a new dependency.

Full definitions, the source examples, and the LCOM equations live in
[cohesion-taxonomy.md](cohesion-taxonomy.md). Read it when
you need precision on a type or on the metric; this file is the workflow.

## The cohesion scale

Name the dominant relationship binding the parts, best to worst
(functional, sequential, communicational, procedural, temporal, logical,
coincidental); definitions and health judgments live in
[cohesion-taxonomy.md](cohesion-taxonomy.md#the-seven-types-best-to-worst).

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
20, with a summary line): **groups** (independent clusters over shared fields
or calls — 1 group hangs together regardless of score, 2+ groups is a split
candidate with a named seam; the raw lack-of-cohesion score appears only
bracketed as `[LCOM=<n>]`).

Use LCOM groups as structural evidence. A constructor or cache can mask a
seam, and a high score can point to pieces that would recouple. Apply steps
5–6 and the reference's "What LCOM cannot tell you." For tiny units or where
the script does not fit, rely on steps 2–3.

### 5. Apply the trade-off questions before recommending a split

A multi-group result is an *invitation* to split, not an order. Ask the
three trade-off questions from the source's Customer/Order Maintenance example
([reference](cohesion-taxonomy.md#worked-example-when-to-split-a-module)):

1. **Too small to stand alone?** If the group to extract is a couple of
   operations that will never grow, keep it where it is (or, for a module
   already extracted, merge it back into its fold-back target).
2. **Is the remaining module growing?** If it is heading toward a god-module,
   extract before it gets there.
3. **Would the pieces re-couple?** If the extracted group needs so much of the
   other's knowledge that the split creates heavy coupling, leave it.

### 6. Recommend: split, merge, or leave — with the refactor

When a split or merge is on the table (2+ groups, or an over-extracted module
that re-couples), answer the step-5 trade-off questions before giving the
outcome. When nothing is up for extraction, there is no trade-off to weigh:
leave with the reason. Give one concrete outcome:
- **Split with seam** — name the group to extract and the module it becomes;
  show the seam. (If this is a significant structural decision, record it in
  an ADR.)
- **Merge with fold-back target** — when an over-extracted module just
  re-couples; name what it folds back into.
- **Leave with reason** — when cohesion is fine or the split would cost more
  than it buys. Judge temporal grouping and legitimate logical grouping on
  their stability; a low placement on the scale alone need not warrant a split.

## Cohesion output format

Follows the [output contract](../SKILL.md#output-contract-all-modes):

```
Verdict: <split | merge | leave> — <cohesion type in one line, e.g. functional>
Evidence: <N> group(s) [LCOM=<n>] — <what that means here, e.g. 1 group hangs together despite a high score>
Trade-offs: <one line per step-5 question: too small? remaining module growing? would re-couple?>
Next step: <seam to extract | fold-back target | reason to leave> — <concrete action>
```

Include the `Trade-offs:` line only when a split or merge was on the table;
for a module with nothing to extract, drop it.

## Cohesion — worked contrast

Groups decide, scores only bracketed. Two file-level shapes recur:

- Cohesive despite a high score: a dozen functions, one group, a large LCOM
  — well connected. Nothing to extract, so no split question arises. Leave.
- Split candidate despite a low score: two functions, two groups, LCOM of 1
  — disjoint groups sharing no symbol. If each group is one small function
  over the same data (question 1), splitting buys a module and nothing else.
  Leave, with that reason — the groups flag *where* to ask, the questions
  decide.
