---
name: refactoring-checklist
environments: coding
description: Walk through a four-phase decision workflow for whether, when, and how to refactor code — deciding if a change is worth doing now, assessing the risk before touching anything, running the refactor safely in small steps, and confirming the result actually earned its keep — use it whenever a code smell is spotted and the question is not "how do I perform this refactoring" but "should I refactor this right now, and how do I do it safely." Covers prioritizing a backlog of smells, choosing between a normal refactor, the Mikado Method, Strangler Fig, or a rewrite, and running reversible steps under the Two-Hats rule. Includes a priority matrix (immediate / this week / next sprint / litter-pickup) with concrete code smells — among them an R-specific set (data.table chains, `<<-` misuse, growing objects in loops, `T`/`F` vs `TRUE`/`FALSE`, `1:length(x)` vs `seq_along()`, unclosed DBI connections) — a test-coverage and change-size risk gate, and quality gates to confirm the refactor helped.
compatibility: Works in any codebase and language; the priority matrix and general code smells apply broadly, with one smell set called out as R-specific. Complements the fowler-refactoring-catalog skill, which supplies the step-by-step mechanics for each named technique referenced here (Extract Function, Extract Class, Decompose Conditional, Introduce Parameter Object, and others).
metadata:
  version: "1.0"
---

# Refactoring Checklist

This skill governs the *decision*, not the *mechanics*. It answers: is this
smell worth fixing now, is it safe to touch, and how do you touch it without
breaking anything — not the step-by-step recipe for a specific technique
(that lives in the fowler-refactoring-catalog skill). Use the two together:
this skill decides whether/when/how, the catalog explains the move itself.

The workflow has four phases: decide, assess risk, implement in small steps,
validate against quality gates.

## Quick decision path

Walk this in order. Stop as soon as a step tells you to stop.

1. **Code smell detected?**
   No → no refactoring needed. Yes → continue.
2. **Test coverage > 80%?**
   No → write characterization tests first, capturing current behavior,
   before changing anything. Yes → continue.
3. **Determine priority** using the matrix below.
4. **Change-size check:**
   - < 2 weeks → normal refactoring, continue to step 5.
   - 2–8 weeks → use the Mikado Method or the Strangler Fig pattern instead
     of a single refactor.
   - \> 8 weeks → evaluate rewrite vs. refactor (see Phase 2).
5. **Two-Hats rule:** are you refactoring, or also building a feature?
   - Refactoring only → start the Small-Steps Protocol.
   - Both → stop. Finish the feature first, then refactor separately.

Don't jump straight to step 3 on the first duplicate you see — the Rule of
Three exists for a reason: one repetition is a coincidence, two is worth
watching, three (or crossing a size threshold below) is when it becomes a
smell worth the matrix.

## Priority matrix

Classify the smell, then act on the matching timeline.

| Priority | Timeline | What lands here |
|---|---|---|
| **Immediate** | System-critical — fix now | Crashes, security holes, dead code, complexity > 10 |
| **This week** | High impact | > 20 lines, complexity 5–10, duplication, coupling smells |
| **Next sprint** | Medium impact | Naming, structural/design smells |
| **Litter-pickup** | Opportunistic, low impact | Cosmetic issues |

### Immediate — production & security

- **Dead code** — a security risk and a source of confusion for developers.
- **Security vulnerabilities** — SQL injection, hardcoded passwords.
- **Memory leaks** — in R: unclosed connections, large objects never cleaned up.
- **Infinite loops** — cause system crashes.
- **Growing objects in loops** — `result <- c(result, new_value)`.
- **Unclosed DB connections** — `DBI::dbConnect()` without a matching `on.exit()`.
- **Global assignments** — the `<<-` operator misused.

### Immediate — performance killers

- **N+1 queries** — database performance.
- **Missing indexes** — slow queries.
- **Non-vectorized R code** — `for` loops instead of `apply`/data.table.

### This week — code understandability

| Smell | Threshold | Technique (see catalog) |
|---|---|---|
| Duplicate Code | > 30 lines, or repeated 3× | Extract Function |
| Long Method | > 20 lines | Extract Function |
| Large Class | > 500 lines | Extract Class |
| Complex Conditional | > 5 conditions | Decompose Conditional |
| Switch Statements | > 5 cases | Replace Conditional with Polymorphism |
| data.table chains | > 10 operations | Split into intermediate steps |
| Nested `apply()` | > 3 levels deep | Refactor into clear named functions |
| Copy-on-modify on large objects | — | Use data.table's `:=` |

### This week — maintainability

- **Shotgun Surgery** — one change forces edits across many classes.
- **Divergent Change** — one class changes for many unrelated reasons.
- **Feature Envy** — a method mostly uses another class's data.

### Next sprint — design problems

- **Long Parameter List** (> 4 parameters) → Introduce Parameter Object.
- **Data Clumps** — the same group of parameters shows up everywhere.
- **Primitive Obsession** — primitives used where a small object belongs.
- **Message Chains** — `a.getB().getC().getD()`.
- **`stringsAsFactors` legacy** — set explicitly rather than relying on defaults.
- **`T`/`F` instead of `TRUE`/`FALSE`** — `T`/`F` are ordinary variables and can be reassigned.
- **`1:length(x)` on a possibly-empty `x`** — use `seq_along(x)` instead.

### Next sprint — naming

- **Mysterious Names** — unclear variables or functions.
- **Inconsistent Naming** — different names for the same concept.

### Litter-pickup — cosmetic

- **Comments** — superfluous or stale.
- **Formatting** — inconsistent indentation.
- **Unused Imports** — libraries loaded but not used.
- **Magic Numbers** — hardcoded values without named constants.

## Phase 2 — risk assessment & preparation

Before touching code, validate:

**Test coverage**
- [ ] Minimum standard: 80%+ test coverage in place?
- [ ] Critical path: is the core functionality fully tested?
- [ ] Characterization tests: is current behavior documented in tests?
- [ ] Code understanding: is the function of this code fully understood?
- [ ] Test quality: no test smells (fragile, obscure, slow tests)?

**Change size**
- [ ] Small change (< 2 weeks): direct refactoring.
- [ ] Medium change (2–8 weeks): Mikado Method (incremental, with dependency
      mapping) or Strangler Fig (replace the old code incrementally).
- [ ] Large change (> 8 weeks): evaluate rewrite vs. refactor (below).

**Rewrite vs. refactor decision**

```
IF (fundamental architectural problems OR technology obsolescence)
  → REWRITE
ELSE IF (core functionality sound AND team has domain knowledge)
  → REFACTOR
ELSE
  → HYBRID APPROACH (Strangler Fig pattern)
```

## Phase 3 — implementation workflow

**Golden rules (never violate these):**
- [ ] **Two-Hats principle** — never refactor and add features at the same time.
- [ ] **Behavior preservation** — external interfaces stay identical; all tests stay green.

**Small-Steps Protocol** — one cycle is 15–30 minutes:

```
LOOP until quality gates are met:
  1. Tests green?          Yes → continue | No → STOP
  2. One atomic step (max 30 min)
  3. Tests still green?    Yes → commit  | No → rollback
  4. Step took > 30 min?   → split it into smaller steps
```

Time rule: any refactoring step that runs longer than 30 minutes gets split
into smaller steps — don't push through.

**Tool integration**
- [ ] Prefer automated IDE refactorings over hand edits.
- [ ] Respect static-analysis warnings (e.g. SonarQube/CheckStyle-class tools).
- [ ] If an AI assistant proposes a refactor, validate it manually before accepting.
- [ ] Use a feature branch for larger refactorings.

## Phase 4 — quality gates & validation

A refactor isn't done when the steps stop; it's done when these hold:

**Code quality metrics**
- [ ] Cyclomatic complexity reduced (target: < 10)?
- [ ] No remaining duplication?
- [ ] Method/class length under reasonable limits (methods < 20 lines)?
- [ ] Coupling (dependency metrics) reduced?

**Development velocity**
- [ ] Feature delivery speed the same or better?
- [ ] Bugs resolved faster?
- [ ] Code review cycles shorter?

**Business value**
- [ ] No performance regression.
- [ ] Changes are genuinely easier to make now?
- [ ] Development team more confident in the code?

## Test adaptation during refactoring

- **Interface changed?** → adjust the tests.
- **Only internal structure changed?** → tests stay the same.
- **Tests failing?** → check whether behavior actually changed, or roll back.
- **New methods added?** → write new tests for them.
- **Check test quality** → don't introduce new test smells while adapting tests.

## When something goes wrong

| Symptom | Response |
|---|---|
| Tests turn red | Roll back and use smaller steps |
| Behavior changed | Restore the original behavior |
| Interface changed | Adjust the tests to match |
| Turns out more complex than expected | Split the work further, or switch strategy (Mikado / Strangler Fig / rewrite) |


