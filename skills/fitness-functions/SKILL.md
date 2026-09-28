---
name: fitness-functions
category: architecture
environments: coding
description: Automate a CI check that governs an architecture characteristic — modularity, layering, coupling, security, resilience — and fails the build when it erodes. These are architecture fitness functions; covers designing and implementing them.
---

# Fitness Functions

## When to use

Whenever someone wants to "enforce architecture rules", "stop devs from
breaking the layering", "prevent cyclic dependencies", "add an ArchUnit /
dependency-cruiser / import-linter test", "automate architecture governance",
or "keep the architecture from eroding", asks how to make an architectural
decision stick in CI, or mentions fitness functions, evolutionary
architecture, or chaos engineering as governance — even without the term
"fitness function". Not for measuring the current coupling/cohesion of
existing code (→ coupling-cohesion) or choosing an
architecture in the first place (→ architecture-pattern-advisor).

An **architecture fitness function** is any automated check that scores how close the codebase or running system stays to the architect's intent — a perspective on tools you already have (tests, metrics, monitors, chaos), wired into CI so important-but-never-urgent concerns like modularity don't erode one import at a time.

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
  import-linter's `acyclic_siblings` contract).
- **Threshold on a metric** — e.g. every package's Distance from the Main
  Sequence within a project-dependent tolerance of the ideal. Thresholds are
  legitimate; vibes are not. (To *measure and choose* the threshold on an
  existing codebase, hand off to **`coupling-cohesion`** — its
  `scripts/coupling_metrics.py --threshold --json` reports the per-component
  numbers to gate on; fail the build when its flagged set is non-empty.)
- **Layer / boundary rules** — declare which layers may access which
  (ArchUnit's `layeredArchitecture()`, NetArchTest's
  `ShouldNot().HaveDependencyOn(...)`) and fail on violations.

Whatever the pattern, the assessment must be **objective**: a person rerunning
the check gets the same verdict. Prove the check can fail: introduce a
deliberate violation without committing, watch the check go red, then revert.
If the rule can't be stated as code, it isn't
a fitness function yet — sharpen the rule first.

#### Baseline first on an existing codebase

A new rule on legacy code fails on day one, and a check that is red on day
one gets disabled. Start from the current metric value instead of an ideal
threshold: freeze the existing violations, fail only on new ones, and track
the baseline size as a metric that must not grow. Ratchet the baseline
tighter as violations are fixed; never impose a big-bang threshold the
codebase cannot meet yet. Per-ecosystem baseline mechanics are listed in
[references/tooling-catalog.md](references/tooling-catalog.md).

### 4. Wire it into the pipeline

A fitness function that isn't executed automatically is documentation.
Structural checks run in the test suite / CI on every commit; metric checks run
in the same place with their threshold committed next to the code; production
checks run continuously against live systems. Once wired in, the architect can
"stop worrying about trigger-happy developers accidentally introducing cycles"
— accidental lapses are caught mechanically, which is the entire point.

When a coding agent works in the repo, the checks double as its deterministic
feedback loop: run them in pre-commit and in the test command the agent
invokes, so violations surface before the agent declares the task done.
Failure messages must name the rule, the violating edge, and the allowed
alternative, so the agent can fix the violation without asking. Reference the
rule and its fix command from the repo's agent instruction file.

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
On failure:     <the message naming the rule, the violating edge, the allowed alternative, and how to fix it>
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
- **Rules that can pass vacuously.** A contract whose selector matches
  nothing — a typo in a glob, a package renamed since the rule was written,
  a layer that moved — reports green forever and protects nothing. Prefer a
  tool that fails on empty matches; where it doesn't, assert separately that
  the selector matched at least one module.

## Related skills

- **`coupling-cohesion`** — measures afferent/efferent coupling, Instability,
  and Distance from the Main Sequence on an existing codebase (use it to pick
  the thresholds this skill then enforces), plus split/merge/leave cohesion
  verdicts for individual modules.
- **`architecture-pattern-advisor`** — choosing the architecture whose rules
  fitness functions will guard.
- **`adr-workflow`** — record the governed decision as an ADR and link the
  fitness function as its enforcement.

## Source

Mark Richards & Neal Ford, *Fundamentals of Software Architecture*, 2nd ed.
(O'Reilly), "Measuring and Governing Architecture Characteristics" — definition and evolutionary-
computing origin of fitness functions, the cyclic-dependency and Distance from
the Main Sequence examples (JDepend), layer governance (ArchUnit, NetArchTest),
metric gaming, the Netflix Simian Army as production fitness functions, and the
Checklist Manifesto framing. Builds on Neal Ford et al., *Building Evolutionary
Architectures* (O'Reilly, 2022).
