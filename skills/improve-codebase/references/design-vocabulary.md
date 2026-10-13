# Design vocabulary: deep modules

Adapted from Matt Pocock's `codebase-design` skill (files `SKILL.md`,
`DEEPENING.md`, `DESIGN-IT-TWICE.md`) in mattpocock/skills at upstream commit
`49dd158` (v1.3.1). Copyright (c) 2026 Matt Pocock, MIT License; the full
license text is in `../UPSTREAM-LICENSE`. Drift against upstream is expected;
compare with that commit before syncing.

## Contents

- [Glossary](#glossary)
- [Deep vs shallow](#deep-vs-shallow)
- [Principles](#principles)
- [Designing for testability](#designing-for-testability)
- [Relationships and rejected framings](#relationships-and-rejected-framings)
- [Dependency categories](#dependency-categories)
- [Seam discipline and testing strategy](#seam-discipline-and-testing-strategy)
- [Design it twice](#design-it-twice)

Design **deep modules**: a lot of behaviour behind a small interface, placed at
a clean seam, testable through that interface. The aim is leverage for callers,
locality for maintainers, and testability for everyone.

## Glossary

Use these terms exactly. Do not substitute "component", "service", "API", or
"boundary": consistent language is the whole point.

**Module**: anything with an interface and an implementation. Deliberately
scale-agnostic: a function, class, package, or tier-spanning slice.
_Avoid_: unit, component, service.

**Interface**: everything a caller must know to use the module correctly: the
type signature, but also invariants, ordering constraints, error modes,
required configuration, and performance characteristics.
_Avoid_: API, signature (too narrow, they cover only the type-level surface).

**Implementation**: what is inside a module, its body of code. Distinct from
**adapter**: a thing can be a small adapter with a large implementation (a
Postgres repository) or a large adapter with a small implementation (an
in-memory fake). Say "adapter" when the seam is the topic, "implementation"
otherwise.

**Depth**: leverage at the interface. The amount of behaviour a caller (or
test) can exercise per unit of interface it has to learn. A module is **deep**
when a large amount of behaviour sits behind a small interface, **shallow**
when the interface is nearly as complex as the implementation.

**Seam** (Michael Feathers): a place where behaviour can be altered without
editing in that place; the *location* at which a module's interface lives.
Where to put the seam is its own design decision, distinct from what goes
behind it. _Avoid_: boundary (overloaded with DDD's bounded context).

**Adapter**: a concrete thing that satisfies an interface at a seam. Describes
*role* (which slot it fills), not substance (what is inside).

**Leverage**: what callers get from depth. More capability per unit of
interface learned. One implementation pays back across N call sites and M
tests.

**Locality**: what maintainers get from depth. Change, bugs, knowledge, and
verification concentrate in one place instead of spreading across callers.
Fix once, fixed everywhere.

## Deep vs shallow

**Deep module** = small interface + lots of implementation:

```text
┌─────────────────────┐
│   Small Interface   │  <- few methods, simple params
├─────────────────────┤
│                     │
│  Deep Implementation│  <- complex logic hidden
│                     │
└─────────────────────┘
```

**Shallow module** = large interface + little implementation (avoid):

```text
┌─────────────────────────────────┐
│       Large Interface           │  <- many methods, complex params
├─────────────────────────────────┤
│  Thin Implementation            │  <- just passes through
└─────────────────────────────────┘
```

When designing an interface, ask: can the number of methods shrink? Can the
parameters get simpler? Can more complexity hide inside?

## Principles

- **Depth is a property of the interface, not the implementation.** A deep
  module can be built from small, mockable, swappable parts; they are just not
  part of the interface. A module can have **internal seams** (private to its
  implementation, used by its own tests) as well as the **external seam** at
  its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes,
  it was a pass-through. If complexity reappears across N callers, it was
  earning its keep.
- **The interface is the test surface.** Callers and tests cross the same
  seam. A test that has to reach *past* the interface means the module is
  probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters mean a real one.** Do
  not introduce a seam unless something actually varies across it.

## Designing for testability

1. **Accept dependencies, do not create them.**

   ```typescript
   // Testable
   function processOrder(order, paymentGateway) {}

   // Hard to test
   function processOrder(order) {
     const gateway = new StripeGateway();
   }
   ```

2. **Return results, do not produce side effects.**

   ```typescript
   // Testable
   function calculateDiscount(cart): Discount {}

   // Hard to test
   function applyDiscount(cart): void {
     cart.total -= discount;
   }
   ```

3. **Small surface area.** Fewer methods mean fewer tests; fewer parameters
   mean simpler test setup.

## Relationships and rejected framings

- A **module** has exactly one **interface**: the surface it presents to
  callers and tests.
- **Depth** is a property of a module, measured against its interface.
- A **seam** is where a module's interface lives.
- An **adapter** sits at a seam and satisfies the interface.
- Depth produces **leverage** for callers and **locality** for maintainers.

Rejected:

- **Depth as the ratio of implementation lines to interface lines**
  (Ousterhout): rewards padding the implementation. Depth here means leverage.
- **"Interface" as a language keyword or a class's public methods**: too
  narrow; the interface includes every fact a caller must know.
- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or
  **interface**.

## Dependency categories

When assessing a candidate for deepening, classify its dependencies. The
category decides how the deepened module is tested across its seam, and is the
dependency tag on the report card.

1. **In-process**: pure computation, in-memory state, no I/O. Always
   deepenable: merge the modules and test through the new interface directly.
   No adapter needed.
2. **Local-substitutable**: dependencies with a local test stand-in (PGLite for
   Postgres, an in-memory filesystem). Deepenable if the stand-in exists; the
   test suite runs against it. The seam is internal; no port at the module's
   external interface.
3. **Remote but owned (ports & adapters)**: your own services across a network.
   Define a **port** at the seam; the deep module owns the logic and the
   transport is injected as an adapter. Tests use an in-memory adapter,
   production an HTTP, gRPC, or queue adapter.
4. **True external (mock)**: third-party services you do not control. The
   deepened module takes the dependency as an injected port; tests provide a
   mock adapter.

## Seam discipline and testing strategy

- Do not introduce a port unless at least two adapters are justified (typically
  production and test). A single-adapter seam is just indirection.
- Do not expose internal seams through the interface just because tests use
  them.
- **Replace, do not layer.** Once tests at the deepened module's interface
  exist, the old unit tests on the shallow modules are waste; delete them.
- Tests assert on observable outcomes through the interface, not on internal
  state. A test that has to change when the implementation changes is testing
  past the interface.

## Design it twice

Use this when the user wants to compare alternative interfaces for a chosen
candidate. Based on Ousterhout's "design it twice": the first idea is unlikely
to be the best.

1. **Frame the problem space** for the user: the constraints any new interface
   must satisfy, the dependencies and their categories, and a rough code sketch
   that makes the constraints concrete (a grounding aid, not a proposal).
2. **Produce three or more radically different designs**, in parallel
   subagents where the agent can start them, otherwise one after another. Give
   each a separate technical brief (file paths, coupling details, dependency
   category, what sits behind the seam, this vocabulary, and the project's
   `GLOSSARY.md` terms) and a different constraint:
   - minimise the interface: one to three entry points, maximum leverage each;
   - maximise flexibility: many use cases and extension;
   - optimise for the most common caller: make the default case trivial;
   - (if applicable) design around ports and adapters for cross-seam
     dependencies.

   Each design states its interface (types, methods, parameters, invariants,
   ordering, error modes), a usage example, what the implementation hides,
   its dependency strategy and adapters, and where leverage is high or thin.
3. **Present and compare.** Show the designs one at a time, then compare them by
   depth, locality, and seam placement. Close with an opinionated
   recommendation, proposing a hybrid if elements combine well.
