# Mode B — Codebase-wide coupling metrics

Judge how coupled — and therefore how brittle or over-abstracted — a codebase
is, with five per-component numbers (plain language first, historical
abbreviation in brackets) and their Main Sequence zones.

## Contents

- [The numbers and zones](#the-numbers-and-zones)
- [Coupling-metrics workflow](#coupling-metrics-workflow)
- [Coupling-metrics output format](#coupling-metrics-output-format)
- [Coupling metrics — common mistakes](#coupling-metrics--common-mistakes)

## The numbers and zones

Name each number plain language first: incoming dependencies (Ca), outgoing
dependencies (Ce), instability (I), abstractness (A), distance from the ideal
(D). Their definitions and formulas are in
[metrics.md](metrics.md#the-five-metrics), the Zone of Pain and Zone of
Uselessness in [metrics.md](metrics.md#the-zone-map). The script adds two
labels of its own: near main sequence (balanced for its stability: leave
alone) and unknown (abstractness counts not gathered, see step 3: gather the
counts or judge by the edges).

An unaided answer tends to eyeball imports and give a vibe. This mode makes
the analysis reproducible: build the dependency graph, compute the metrics with
a bundled script, classify each component, and recommend a concrete fix — while
respecting that the numbers are blunt and need interpretation.

Definitions, formulas, the zone map, the SDP/SAP principles behind the Main
Sequence, and a worked example live in
[metrics.md](metrics.md). Fixes per zone live in
[remediation.md](remediation.md); read it together with
the limitations section of metrics.md, since a flagged zone is a prompt to
look, not a verdict.

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

If the tool emits incoming (Ca) / outgoing (Ce) / instability (I) counts, use
them; the script adds abstractness (A) / distance (D) and uniform output.

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

It prints one markdown bullet per component with its zone label, incoming
dependencies (Ca), outgoing dependencies (Ce), instability (I), abstractness
(A) and distance from the ideal (D), sorted worst-distance first, and flags
everything past the threshold (`--threshold`, default 0.5). Use `--json` to
pipe the numbers elsewhere. See
[metrics.md](metrics.md) for how each number is derived.

### 5. Interpret — don't just rank

Treat a high distance from the ideal (D) as a prompt to look, not a verdict.

- For each flagged component, name its zone and explain *why* it landed there
  in terms of its actual edges (what depends on it, what it depends on) —
  numbers never stand as verdicts on their own.
- Separate real pain from earned stability: a finished, stable, concrete
  utility everyone imports can sit in the Zone of Pain corner and be perfectly
  fine — leaving it is then the right call, with the reason stated.
- Sanity-check the graph itself — a surprising result is often a missing or
  spurious edge, not a real coupling problem.

### 6. Remediate

For each component that is genuinely off the Main Sequence, recommend a fix from
[remediation.md](remediation.md): raise abstraction in the
Zone of Pain, remove indirection in the Zone of Uselessness, and move
dependencies toward stability.

### 7. Record and go deeper

Record significant restructuring in an ADR (with the metrics
baseline); escalate topology problems to
`members/architecture-pattern-advisor/SKILL.md` (read via the `architecture`
router), and
re-run the script to confirm components moved toward the Main Sequence.

## Coupling-metrics output format

Follows the [output contract](../SKILL.md#output-contract-all-modes):

```
Verdict: <fix | leave | gather data> — <zone: Zone of Pain | Zone of Uselessness | near main sequence | unknown>
Evidence: <incoming (Ca)=<n>, outgoing (Ce)=<n>, instability (I)=<n>, abstractness (A)=<n>, distance (D)=<n>> — <what that means here, via the actual edges>
Next step: <fix with seam | reason to leave, e.g. earned stability | abstractness counts to gather> — <concrete action>
```

## Coupling metrics — common mistakes

- **Mixing levels.** Counting class edges and package edges in one graph makes
  the metrics meaningless. Pick one unit (step 1).
- **Reporting numbers as verdicts.** The metrics flag *where to look*; they
  can't tell essential from accidental complexity. Always interpret (step 5).
- **Condemning earned stability.** A stable, concrete, finished utility in the
  Zone of Pain corner may need no change. High distance from the ideal (D) ≠ defect.
- **Fixing Uselessness by adding abstraction.** It's already too abstract —
  remove indirection, don't add it.
- **Trusting a bad graph.** Garbage edges in, garbage metrics out. Verify the
  extractor drew the dependencies you expect before believing the table.
