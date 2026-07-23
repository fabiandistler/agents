---
name: codebase-design
category: architecture
environments: coding
description: Shared vocabulary and workflow for designing deep modules. Use when designing or improving a module, API, or function interface, finding deepening opportunities, deciding where a seam goes, or making code more testable.
---

# Codebase Design

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface. Use this language and these principles wherever code is being designed or restructured. The aim is leverage for callers, locality for maintainers, and testability for everyone.

## Glossary

Use these terms exactly — don't substitute "component," "service," "API," or "boundary." Consistent language is the whole point.

**Module** — anything with an interface and an implementation. Deliberately scale-agnostic: a function, class, package, or tier-spanning slice. _Avoid_: unit, component, service.

**Interface** — everything a caller must know to use the module correctly: the type signature, but also invariants, ordering constraints, error modes, required configuration, and performance characteristics. _Avoid_: API, signature (too narrow — they refer only to the type-level surface).

**Implementation** — what's inside a module, its body of code. Distinct from **Adapter**: a thing can be a small adapter with a large implementation (a Postgres repo) or a large adapter with a small implementation (an in-memory fake). Reach for "adapter" when the seam is the topic; "implementation" otherwise.

**Depth** — leverage at the interface: the amount of behaviour a caller (or test) can exercise per unit of interface they have to learn. A module is **deep** when a large amount of behaviour sits behind a small interface, **shallow** when the interface is nearly as complex as the implementation.

**Seam** _(Michael Feathers)_ — a place where you can alter behaviour without editing in that place; the *location* at which a module's interface lives. Where to put the seam is its own design decision, distinct from what goes behind it. _Avoid_: boundary (overloaded with DDD's bounded context).

**Adapter** — a concrete thing that satisfies an interface at a seam. Describes *role* (what slot it fills), not substance (what's inside).

**Leverage** — what callers get from depth: more capability per unit of interface they learn. One implementation pays back across N call sites and M tests.

**Locality** — what maintainers get from depth: change, bugs, knowledge, and verification concentrate in one place rather than spreading across callers. Fix once, fixed everywhere.

## Deep vs shallow

**Deep module** = small interface + lots of implementation:

```
┌─────────────────────┐
│   Small Interface   │  ← Few methods, simple params
├─────────────────────┤
│                     │
│  Deep Implementation│  ← Complex logic hidden
│                     │
└─────────────────────┘
```

**Shallow module** = large interface + little implementation (avoid):

```
┌─────────────────────────────────┐
│       Large Interface           │  ← Many methods, complex params
├─────────────────────────────────┤
│  Thin Implementation            │  ← Just passes through
└─────────────────────────────────┘
```

When designing an interface, ask:

- Can I reduce the number of methods?
- Can I simplify the parameters?
- Can I hide more complexity inside?

## Principles

- **Depth is a property of the interface, not the implementation.** A deep module can be internally composed of small, mockable, swappable parts — they just aren't part of the interface. A module can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a seam unless something actually varies across it.

## Designing for testability

Good interfaces make testing natural:

1. **Accept dependencies, don't create them.**

   ```typescript
   // Testable
   function processOrder(order, paymentGateway) {}

   // Hard to test
   function processOrder(order) {
     const gateway = new StripeGateway();
   }
   ```

2. **Return results, don't produce side effects.**

   ```typescript
   // Testable
   function calculateDiscount(cart): Discount {}

   // Hard to test
   function applyDiscount(cart): void {
     cart.total -= discount;
   }
   ```

3. **Small surface area.** Fewer methods = fewer tests needed. Fewer params = simpler test setup.

## Relationships

- A **Module** has exactly one **Interface** (the surface it presents to callers and tests).
- **Depth** is a property of a **Module**, measured against its **Interface**.
- A **Seam** is where a **Module**'s **Interface** lives.
- An **Adapter** sits at a **Seam** and satisfies the **Interface**.
- **Depth** produces **Leverage** for callers and **Locality** for maintainers.

## Rejected framings

- **Depth as ratio of implementation-lines to interface-lines** (Ousterhout): rewards padding the implementation. We use depth-as-leverage instead.
- **"Interface" as the TypeScript `interface` keyword or a class's public methods**: too narrow — interface here includes every fact a caller must know.
- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or **interface**.

## Going deeper

- **Deepening a cluster given its dependencies** — see [DEEPENING.md](DEEPENING.md): dependency categories, seam discipline, and replace-don't-layer testing.
- **Exploring alternative interfaces** — see [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md): spin up parallel sub-agents to design the interface several radically different ways, then compare on depth, locality, and seam placement.

## Interface design workflow

Apply this when designing or refactoring any function, API, or module surface.

### 1. Design the interface first (minimize complexity)

- Cover the most frequent use case with minimal parameters; push extras behind `...` or an options object.
- Keep the interface general; archetypes like `fun(mapping, data, ...)` or `DT[i, j, by]` encourage breadth with simplicity.
- Provide intelligent defaults so 80% of calls need no extra parameters.

**Parameter decision tree:**

| Arity | Verdict |
|-------|---------|
| 0–1 params | OK — ensure monadic form is clearly a query, transformation, or event |
| 2 params | Acceptable — look for opportunities to reduce (reorder, curry, bundle) |
| 3 params | Scrutinize — can any be grouped into a cohesive argument object? |
| >3 params | Refactor — create an argument object; re-evaluate responsibilities |
| Boolean flags | Split into separate functions per intent, or use a Strategy object |
| Parameter clumps (always together) | Encapsulate into a record or class |

### 2. Build implementation depth

- Hide complexity behind the simple interface; keep specialised optimisations internal.
- Make the common path trivial; expose extension points (`...` hooks) for edge cases.
- Preserve internal flexibility so you can swap algorithms without touching the interface.

### 3. Structured design process

- Is the function both "doing" and "answering"? Apply **Command–Query Separation**: split into a command (side effect, returns nothing useful) and a query (no side effect, returns a value).
- **Law of Demeter**: call methods only on `this`, its fields, parameters, and freshly created objects — don't chain into "strangers."
- Choose OO vs. procedural based on the axis of change: OO excels at adding new data types, procedural at adding new operations.

### 4. Validate depth

- **Mental execution**: can a caller "run it in their head" from the interface alone?
- **Interface tests**: focus on behaviour through the public surface (functionality and edge cases).
- **Performance**: benchmark the 80% case; track time/memory trends.

Anti-patterns to catch:

- Boolean flags or "mode" parameters → split function per intent or Strategy object
- Output parameters → return the value; if mutating state, make the owning object do it
- Triads and beyond → argument object; reassess responsibilities
- "Do and answer" functions → separate into command and query

### 5. Document and extend

- Document parameters, return values, and examples on the public surface; point to extension points.
- Keep families consistent across modules to aid discoverability and composability.

## Refactoring toolkit

Use as-needed when deepening existing code:

- **Extract Function** — separate intent from implementation; expose variation points.
- **Move Statements to Callers** — allow call-site customisation without flags.
- **Combine Functions into Class** — when multiple functions share data, class membership drops repeated parameters.
- **Move Field** — co-locate data with behaviour; removes parameter clumps.

## Checklist

- [ ] Name expresses *what* (intent), not *how*
- [ ] 0–3 parameters, no flags; clumps grouped
- [ ] Clear Command–Query Separation where applicable
- [ ] Interactions respect Law of Demeter
- [ ] Tests cover each intent path and options combination

## R patterns

For R package and function design, prefer these idioms to prevent interface sprawl:

- **Options Objects** — bundle many optional parameters into a single list/environment; callers set only what they need.
- **Progressive Interface Disclosure** — keep the base interface minimal; expose advanced parameters only when the user opts in (e.g., via a `control` argument or a secondary `*_advanced()` variant).
- **Strategy Objects** — replace boolean flags or `method =` string arguments with a function or S3 object that encapsulates the varying behaviour.

### More interface idioms

- **Enum default for closed choices** — when a parameter has a handful of valid string values, default it to the full vector and resolve with `match.arg()` (or `rlang::arg_match()`, preferred for clearer error messages). The first element is the default; the signature becomes self-documenting.

  ```r
  my_function <- function(method = c("average", "first", "last")) {
    method <- rlang::arg_match(method)
  }
  ```

  Use this when the options share the same parameters; once they need different parameters each, escalate to Strategy Objects above.

- **`invisible()` for pipe-composable side effects** — a function called for its side effect should still return a useful value (often its first argument), just invisibly, so it doesn't clutter the console but keeps working inside a pipe.

  ```r
  write_log <- function(data, message) {
    cat(message, "\n", file = "log.txt", append = TRUE)
    invisible(data)  # not NULL — keeps `data %>% write_log(...) %>% next_fn()` working
  }
  ```

- **`I()` for a second, explicit mode** — wrap an argument in `I()` to mark it as "AsIs" (checkable via `inherits(x, "AsIs")`) and let the function skip its usual processing for that input. Reach for this when a function has two natural modes: transform the input, or pass it through untouched.

  ```r
  create_url <- function(base, params) {
    # already-escaped values arrive wrapped in I(); everything else gets escaped here
    if (inherits(params$query, "AsIs")) params$query else curl::curl_escape(params$query)
  }
  ```

- **`lifecycle::deprecated()` to retrofit an Options Object** — when widening an existing signature into the Options Objects form above, keep the old parameters as `deprecated()` defaults, fold them into the options object with a warning, and remove them in a later major version.

  ```r
  my_function <- function(x, options = my_function_options(), opt1 = deprecated()) {
    if (lifecycle::is_present(opt1)) {
      lifecycle::deprecate_warn("1.0.0", "my_function(opt1)", "my_function_options(opt1)")
      options$opt1 <- opt1
    }
  }
  ```
