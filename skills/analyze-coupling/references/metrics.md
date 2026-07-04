# Coupling metrics reference

The metrics below come from Robert C. Martin's *Structured Design* lineage,
popularized for architects in Richards & Ford, *Fundamentals of Software
Architecture* (ch. 3, "Modularity"). They are computed over a directed
**dependency graph**: nodes are components at one chosen level
(package / module / service / class) and an edge `A → B` means "A depends
on B" — a call, import, or reference that forms part of the call graph.

## The five metrics

### Afferent coupling — Cᵃ (incoming)

The number of distinct components that depend **on** this one. High Cᵃ means
many things will break if this component's surface changes — it is
*depended-upon*, so it should be stable.

### Efferent coupling — Cᵉ (outgoing)

The number of distinct components this one depends **on**. High Cᵉ means this
component breaks easily when any of its many collaborators changes.

### Abstractness — A

```
A = mᵃ / (mᵃ + mᶜ)
```

where `mᵃ` is the count of abstract artifacts in the component (interfaces,
abstract classes, protocols, traits) and `mᶜ` the count of concrete ones
(implementations). `A = 0` is all implementation; `A = 1` is all abstraction.
The book's image: 5,000 lines of code in one `main()` has abstractness ≈ 0;
5,000 lines that are all interface declarations has abstractness ≈ 1.

### Instability — I

```
I = Cᵉ / (Cᵉ + Cᵃ)
```

Instability measures **volatility**. `I = 0` (only incoming edges) is maximally
stable: nothing it depends on can force it to change. `I = 1` (only outgoing
edges) is maximally unstable: it is at the mercy of everything it calls. A
class that delegates to many others is fragile — any of those changing can
break it.

### Distance from the Main Sequence — D

```
D = |A + I − 1|
```

The one holistic number. `A + I = 1` is the **Main Sequence** — the ideal
diagonal where a component is *as abstract as it is stable*. `D` is the
perpendicular distance from it; `0` is perfectly balanced, `1` is as far off
as possible. Both A and I are fractions in `[0, 1]`, so D is too.

## The zone map

Plot every component with Instability on the x-axis and Abstractness on the
y-axis. The Main Sequence runs corner to corner; the two far corners are
where pain lives.

```
 A  1 ┤■ ideal: abstract & stable        ╲   Zone of
 b    │   (e.g. a pure contracts pkg)      ╲  Uselessness
 s    │                                     ╲  (abstract, but
 t    │              ╲  Main Sequence        ╲  nobody uses it —
 r    │               ╲  A + I = 1            ╲  speculative
 a    │                ╲                       ╲ abstraction)
 c    │   Zone of        ╲                      ╲
 t    │   Pain            ╲                      ╲
 n    │  (concrete &       ╲                      ╲
 e    │   depended-on —     ╲                      ╲
 s    │   brittle, hard      ╲                      ■ ideal:
 s  0 ┤   to change)          ╲                       concrete & unstable
      └──────────────────────────────────────────────  (e.g. a leaf UI
       0           Instability (I)                 1     handler)
```

- **Zone of Pain** (low A, low I): concrete code that many things depend on and
  that itself rarely changes. Brittle — a change ripples widely, but the lack
  of abstraction means there is no seam to change behind. The classic example
  is a sprawling, concrete utility/`core` module everyone imports.
- **Zone of Uselessness** (high A, high I): abstraction that nobody depends on.
  Layers of interfaces, factories, and indirection that earn their keep
  nowhere. Maximally over-engineered. The `AbstractSingletonProxyFactoryBean`
  feeling.

## Stable Dependencies & Stable Abstractions Principles

These two principles (Robert C. Martin) explain *why* the Main Sequence is the
target — they are the "should" behind the "is":

- **Stable Dependencies Principle (SDP):** depend in the direction of
  stability. A component should only depend on components more stable than
  itself (lower I). Dependencies pointing toward instability are what make
  changes cascade.
- **Stable Abstractions Principle (SAP):** a component should be as abstract as
  it is stable. Stable components (many depend on them, low I) must be abstract
  so they can be extended without modification; unstable components can be
  concrete. SAP + SDP together *are* the Main Sequence: `A + I ≈ 1`.

So a healthy depended-upon component is **abstract and stable** (top-left); a
healthy leaf is **concrete and unstable** (bottom-right). The two zones are
exactly the two ways to violate this.

## Worked example

`scripts/example_input.json` models five components. Running
`python3 scripts/coupling_metrics.py scripts/example_input.json` from the
skill root yields:

| Component | Ca | Ce | I | A | D | Zone |
|---|---|---|---|---|---|---|
| experimental | 0 | 2 | 1.00 | 1.00 | 1.00 | Zone of Uselessness |
| core | 3 | 1 | 0.25 | 0.00 | 0.75 | Zone of Pain |
| billing | 2 | 2 | 0.50 | 0.10 | 0.40 | near main sequence |
| contracts | 3 | 0 | 0.00 | 1.00 | 0.00 | near main sequence |
| web | 0 | 3 | 1.00 | 0.00 | 0.00 | near main sequence |

Read it as a story:

- **core** is concrete (`A = 0`) and depended on by three components while
  itself depending on only one, so it is fairly stable (`I = 0.25`).
  Concrete + depended-upon + stable = `D = 0.75`, deep in the **Zone of Pain**.
  Changing it is risky and there is no abstraction to change behind.
- **experimental** is all interfaces (`A = 1`) but depends on two components
  and *nothing* depends on it (`I = 1`). Abstract + unused = `D = 1`, the
  **Zone of Uselessness**.
- **contracts** (abstract, only incoming edges) and **web** (concrete, only
  outgoing edges) both sit on the Main Sequence — `D = 0`. They are the two
  healthy archetypes.

Verify any row by hand: e.g. for `core`, `I = Cᵉ/(Cᵉ+Cᵃ) = 1/(1+3) = 0.25`,
`A = 0/20 = 0`, `D = |0 + 0.25 − 1| = 0.75`.

## The limitations of these metrics

The book is emphatic, and this caveat belongs in every analysis you produce:
these are **blunt instruments compared to the analysis tools of other
engineering disciplines, and they require interpretation.** Specifically:

- A metric cannot tell **essential** complexity (the problem is genuinely
  hard) from **accidental** complexity (the code is more complex than the
  problem demands). A high score flags *where to look*, never *what is wrong*.
- A stable, concrete component is not automatically a defect. A mature
  date/money/units utility that everyone depends on and that almost never
  changes can sit in the "Pain" corner and be completely fine — its stability
  is earned, not a smell.
- The numbers depend entirely on the **unit of analysis** and on how cleanly
  the dependency extractor drew the graph. Garbage edges in, garbage metrics
  out.

Use the metrics to **establish a baseline and direct attention**, then apply
human judgment. Never report a number as a verdict.
