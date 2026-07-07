---
name: fitness-functions
environments: coding
description: Design and implement architecture fitness functions — automated, objective checks that govern architecture characteristics (modularity, layering, coupling, security, operational resilience) from Richards & Ford's *Fundamentals of Software Architecture* (2nd ed., "Governance and Fitness Functions"). Use whenever someone wants to "enforce architecture rules", "stop devs from breaking the layering", "prevent cyclic dependencies", "add an ArchUnit / dependency-cruiser / import-linter test", "automate architecture governance", "keep the architecture from eroding", asks how to make an architectural decision stick in CI, or mentions fitness functions, evolutionary architecture, or chaos engineering as governance — even if they never use the term "fitness function". Produces a concrete, CI-wired check plus the rationale developers need to accept it. Not for measuring current coupling/cohesion of existing code (→ analyze-coupling / analyze-cohesion) or choosing an architecture in the first place (→ architecture-pattern-advisor).
compatibility: Language- and stack-agnostic workflow. Implementations use whatever governance tooling fits the ecosystem (references/tooling-catalog.md lists options for Java, .NET, JS/TS, Python, Go, and production/runtime checks).
---

# Fitness Functions

An **architecture fitness function** is *any mechanism* that provides an
**objective integrity assessment** of one or more architecture characteristics.
The term comes from evolutionary computing: a fitness function scores how close
an algorithm's output comes to its aim. Applied to architecture, it scores how
close the codebase (or the running system) stays to the architect's intent —
automatically, on every build, forever.

Fitness functions solve the governance problem: architects decide that
modularity, layering, or security matter, but on real projects **urgency
dominates importance**. Modularity is important but never urgent, so it erodes
one auto-import at a time until the system is a Big Ball of Mud. Code reviews
catch this too late — a week of rampant imports has already done the damage.
The fix is to encode the rule as an executable check and wire it into
continuous integration, so the important-but-not-urgent concern is guarded
without anyone having to remember it.

Two framings to keep in mind, both from the source chapter:

- **Not a new framework** — fitness functions are a *perspective* on tools you
  already have: unit-test libraries, metrics, monitors, chaos engineering. The
  verification mechanisms are as varied as the characteristics they verify.
- **A checklist, not a regime** (the *Checklist Manifesto* view) — developers
  *know* they shouldn't release insecure or tangled code, but that knowledge
  competes with a hundred other priorities. A fitness function is a succinct
  automated reminder built into the substrate of the architecture, not a
  heavyweight governance process.

Concrete tool-by-tool implementations live in
[references/tooling-catalog.md](references/tooling-catalog.md) — read it once
you reach step 3 and know the ecosystem. This file is the workflow.

## The workflow

### 1. Name the characteristic being governed

Start from the architecture characteristic, not from a tool. What decision or
quality must survive schedule pressure? Typical candidates: modularity (no
cycles, controlled dependencies), layer/boundary integrity, coupling limits,
test integrity, security configuration, cost hygiene, operational resilience.
If the user says "developers keep doing X", the characteristic is whatever X
erodes. A fitness function without a named characteristic is just a lint rule
nobody can defend later — the name is what justifies the check when someone
asks to delete it.

### 2. Choose the mechanism

Fitness functions overlap several existing mechanism families. Pick the one
that can observe the characteristic *earliest* and *most objectively*:

| Mechanism | Observes | Use for | Canonical example |
|---|---|---|---|
| Unit-test-style structural check | Source / build artifacts | Modularity, layering, dependency rules, naming, test integrity | JDepend cycle test, ArchUnit layer rules |
| Metric with threshold | Source / build artifacts | Gradual qualities that need a tolerance, not a boolean | Distance from the Main Sequence ≤ tolerance per package |
| Monitor / production check | Running system | Availability, error rates, conformity of deployed services | Netflix Conformity & Security Monkeys |
| Chaos engineering | Running system under injected failure | Resilience, fault tolerance — "not *if* it breaks, but *when*" | Chaos Monkey (latency), Chaos Kong (datacenter loss) |

Prefer build-time checks when the characteristic is visible in the code —
they fail fastest and cheapest. Reserve monitors and chaos for characteristics
that only exist at runtime.

### 3. Implement it — objective, binary or thresholded

Write the check with the ecosystem's governance tool (see
[references/tooling-catalog.md](references/tooling-catalog.md)). The three
patterns from the book cover most structural cases:

- **Cycle detection** — fail the build if any component cycle exists
  (JDepend's `containsCycles()`, dependency-cruiser's `no-circular`,
  import-linter's `independence` contract).
- **Threshold on a metric** — e.g. every package's Distance from the Main
  Sequence within a project-dependent tolerance of the ideal. Thresholds are
  legitimate; vibes are not. (To *measure and choose* the threshold on an
  existing codebase, hand off to **`analyze-coupling`**.)
- **Layer / boundary rules** — declare which layers may access which
  (ArchUnit's `layeredArchitecture()`, NetArchTest's
  `ShouldNot().HaveDependencyOn(...)`) and fail on violations.

Whatever the pattern, the assessment must be **objective**: a person rerunning
the check gets the same verdict. If the rule can't be stated as code, it isn't
a fitness function yet — sharpen the rule first.

### 4. Wire it into the pipeline

A fitness function that isn't executed automatically is documentation.
Structural checks run in the test suite / CI on every commit; metric checks run
in the same place with their threshold committed next to the code; production
checks run continuously against live systems. Once wired in, the architect can
"stop worrying about trigger-happy developers accidentally introducing cycles"
— accidental lapses are caught mechanically, which is the entire point.

### 5. Get developer buy-in and anticipate gaming

Two social rules the chapter is emphatic about:

- **Explain before imposing.** Ensure developers understand the *purpose* of a
  fitness function before it starts failing their builds. The intent is not
  architects in an ivory tower writing esoteric checks developers can't
  understand — it's collaboratively implemented governance that everyone can
  read. Design the check *with* developers where possible.
- **Expect the metric to be gamed.** Once people know what is measured, some
  will code to the metric — e.g. assertion-free unit tests that "touch" code
  to satisfy coverage. Where a check is gameable, add a companion fitness
  function that closes the loophole (e.g. ArchUnit rule: every test contains
  at least one assertion). Dedicated rule-breakers will always find a way;
  the target is preventing *accidental* lapses, not building a prison.

## Output format

When designing fitness functions for a user, deliver each one as:

```
Characteristic: <what is being governed and why it matters here>
Mechanism:      <structural test | metric threshold | monitor | chaos>
Check:          <the actual code / config, in the project's ecosystem>
Trigger:        <where it runs — test suite, CI stage, production schedule>
On failure:     <what a developer sees and what they should do about it>
```

Keep it proportional: one eroding rule needs one fitness function, not a
governance suite. Deliver the check ready to commit, not as a proposal.

## Common mistakes

- **Starting from a tool instead of a characteristic.** "Let's add ArchUnit"
  governs nothing by itself; name what must not erode, then pick the tool.
- **Subjective checks.** "Code should be clean" can't fail a build. If it
  isn't objective and automatable, it's a review guideline, not a fitness
  function.
- **Writing it but not wiring it.** An unexecuted check protects nothing;
  CI integration is part of the definition of done.
- **Ivory-tower rules.** Imposing checks developers don't understand breeds
  workarounds and resentment; explain the purpose first.
- **Ignoring gameability.** Coverage without assertions is the classic;
  ask "how would a rushed developer satisfy this without doing the work?"
  and guard that path too.
- **Only build-time thinking.** Some characteristics (resilience, conformity
  of deployed services, cost hygiene) only exist in production — that's what
  monitors and chaos-engineering fitness functions are for.

## Related skills

- **`analyze-coupling`** — measures afferent/efferent coupling, Instability,
  and Distance from the Main Sequence on an existing codebase; use it to pick
  the thresholds this skill then enforces.
- **`analyze-cohesion`** — split/merge/leave verdicts for individual modules.
- **`architecture-pattern-advisor`** — choosing the architecture whose rules
  fitness functions will guard.
- **`adr-workflow`** — record the governed decision as an ADR and link the
  fitness function as its enforcement.

## Source

Mark Richards & Neal Ford, *Fundamentals of Software Architecture*, 2nd ed.
(O'Reilly), "Governance and Fitness Functions" — definition and evolutionary-
computing origin of fitness functions, the cyclic-dependency and Distance from
the Main Sequence examples (JDepend), layer governance (ArchUnit, NetArchTest),
metric gaming, the Netflix Simian Army as production fitness functions, and the
Checklist Manifesto framing. Builds on Neal Ford et al., *Building Evolutionary
Architectures* (O'Reilly, 2022).
