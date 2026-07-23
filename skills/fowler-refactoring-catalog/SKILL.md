---
name: fowler-refactoring-catalog
category: refactoring
environments: coding
description: Look up Martin Fowler's refactoring catalog to name the exact technique for a code smell and get its atomic mechanics.
metadata:
  version: "1.0"
---

# Fowler Refactoring Catalog

Refactoring is restructuring code so its external behavior stays the same while its internal structure improves. This skill is a lookup tool: given a smell in the code, it names the specific technique that addresses it and lays out the technique's mechanics as an ordered checklist. It does not replace judgment about *whether* to refactor — it removes the guesswork about *which* named technique to reach for and *how* to execute it safely.

The full technique index (62 entries) lives in [references/CATALOG.md](references/CATALOG.md). This file covers the twelve highest-value techniques in enough depth to apply directly, plus the shared discipline that makes every technique in the catalog safe to run.

## When to use

Whenever code needs restructuring without changing observable behavior — a function is too long or hard to name, a conditional is deeply nested or duplicated, data travels as loose primitives or repeated parameter groups, a class exposes its internals or does too much — or the user names a Fowler technique directly (Extract Function, Replace Conditional with Polymorphism, Introduce Parameter Object, etc.) or asks "what refactoring is this called" / "how do I refactor this safely".

## Core principles (apply to every technique in the catalog)

- **Small steps, test after each one.** Every technique below is written as a sequence of tiny, independently-verifiable moves, not one big leap. Commit or checkpoint after each green step so a bad step is easy to revert.
- **Behavior must not change.** A refactoring that alters what the program does is not a refactoring — it is a rewrite wearing a refactoring's name.
- **Name after intent, not implementation.** Extracted functions, variables, and classes are named for *what* they represent, not *how* they compute it.
- **Prefer the reversible move.** Most techniques in the catalog have a named inverse (Extract Function / Inline Function, Extract Variable / Inline Variable, Extract Class / Inline Class …). If a technique made things worse, its inverse undoes it cleanly.
- **Function size is not the goal — clarity is.** Fowler explicitly does not chase short functions for their own sake; a function that needs effort to understand is the trigger, not a line count. (Six lines is the point where Fowler's notes say functions "start to smell," not a hard limit.)

## Smell → technique quick map

Use this table to jump straight to a technique from a symptom. Full mechanics for the linked techniques are in the next section.

| Smell / trigger | Technique | One-line fix |
|---|---|---|
| A comment explains what a code block does; understanding it takes effort | **Extract Function** | Pull the block into a well-named function |
| The same code (or near-identical code) appears more than once | **Extract Function** / Replace Inline Code with Function Call | Extract once, call from every site |
| A complex expression is hard to read at a glance | **Extract Variable** | Give each sub-expression a name |
| Every function just delegates to another with no added clarity | **Inline Function** | Collapse the wrapper into its caller(s) |
| The same group of parameters (a "data clump") keeps showing up together across function signatures | **Introduce Parameter Object** | Bundle the group into one structured object |
| A primitive (string/number) has grown domain-specific behavior duplicated at each call site | **Replace Primitive with Object** | Turn it into a small value class |
| Code reads or writes a variable (especially global/shared state) directly everywhere | **Encapsulate Variable** | Route all access through get/set functions |
| One function mixes two different concerns, or takes input that doesn't match what the core logic needs | **Split Phase** | Split into sequential phases joined by an intermediate data structure |
| A `switch`/`if` chain dispatches on a type code, and the same dispatch is duplicated across several functions | **Replace Conditional with Polymorphism** | Move each branch into a subclass method |
| Unreachable or unused code sits in the file "just in case" | **Remove Dead Code** | Delete it; version control remembers it |
| A conditional is long/nested enough that the *why* is buried in the *what* | **Decompose Conditional** | Extract the condition and each branch into named functions |
| Several functions repeatedly take the same data and repeat parameters to pass it around | **Combine Functions into Class** | Group the functions and their shared data into a class |
| Deeply nested `if/else` where one branch is the normal case and the rest are edge cases | **Replace Nested Conditional with Guard Clauses** | Turn the unusual-condition branches into early returns |

If a smell isn't in this table, scan [references/CATALOG.md](references/CATALOG.md) — it indexes all 61 techniques by name with a one-line description each.

## The twelve techniques in depth

Each entry: **when to reach for it**, then **mechanics** as an ordered checklist.

### Extract Function
*Inverse: Inline Function.*

**When:** a comment explains a block of code; the same code is duplicated; a function needs effort to understand; a function has grown past the point where its name alone communicates what it does.

**Mechanics:**
1. Create a new function; name it after *intent* (the "what"), not the "how". If it must stay nested for now, extract it as a nested function and consider Move Function later.
2. Copy the target code into the new function.
3. Scan the copied code for variables that go out of scope:
   - Read-only locals used inside → pass them in as parameters.
   - A variable assigned only inside the extracted code → move its declaration into the new function.
   - A variable assigned inside but used afterward → have the new function return it (if more than one such variable, prefer separate extractions, or return a small record, or apply Split Variable / Replace Temp with Query first).
4. Replace the original code with a call to the new function; compile/run and test.
5. Look for duplicates of the code just extracted and replace them with calls too.

### Extract Variable
*Inverse: Inline Variable.*

**When:** an expression is complex enough that naming its parts would make it easier to read, debug, or step through; the naming only matters inside the current function (if the name would be useful more broadly, prefer Extract Function or a class method instead).

**Mechanics:**
1. Confirm the expression has no side effects worth preserving separately.
2. Declare an immutable variable, set it to the expression (or a piece of it).
3. Replace the original expression with the new variable.
4. Test.
5. Repeat for other parts of the expression, and replace any duplicate occurrences of the same sub-expression.

### Inline Function
*Inverse: Extract Function.*

**When:** a function's body is exactly as clear as its name, so the function is pure indirection; a chain of delegation has gotten so deep that following it costs more than it saves; or as a deliberate "flatten everything, then re-extract with a better structure" move when a whole area is badly factored. Do **not** inline: polymorphic/overridden methods, recursive functions, functions with multiple return points, or cross-object calls without proper accessors.

**Mechanics:**
1. Check the function isn't overridden anywhere (polymorphism blocks this refactoring).
2. Find every call site.
3. Replace each call, one at a time, with the function's body (adjusting parameter names as needed).
4. Test after each replacement.
5. Remove the now-unused function definition.
- If the body is complex, fall back to smaller steps: move one statement at a time to the caller (Move Statements to Callers) instead of inlining in one shot; revert to green and take smaller steps if a test fails.

### Introduce Parameter Object
**When:** the same group of parameters (a "data clump") recurs across multiple function signatures.

**Mechanics:**
1. Create a structure (a value object, where practical) for the grouped data.
2. Add it as a new parameter to the function(s) (this itself is a Change Function Declaration step).
3. Adjust callers to construct and pass the new structure.
4. Step by step, replace the old individual parameters with reads from the new structure, testing as you go.
- Payoff beyond the shorter signature: the object becomes a place to migrate related behavior, and spotting one data clump often reveals more of them elsewhere in the codebase.

### Replace Primitive with Object
*Requires Encapsulate Variable first; enables Change Reference to Value/Reference.*

**When:** a primitive value (a plain string or number) has picked up domain-specific behavior — formatting, validation, comparison — that is duplicated wherever the primitive is used.

**Mechanics:**
1. If not already done, Encapsulate Variable on the primitive field.
2. Create a simple value class with a constructor and a getter for the raw value.
3. Update the setter: construct a new instance of the value class instead of storing the primitive directly.
4. Update the getter: return the result of the value class's own accessor (or the object itself once callers are migrated).
5. Rename the function/field if the new semantics call for a better name.
6. Decide value vs. reference semantics for the new class (apply Change Reference to Value, or its inverse, accordingly).

### Encapsulate Variable
*Enables Encapsulate Record; historically named Self-Encapsulate Field.*

**When:** code reads or writes a variable directly, especially data with wide scope (module-level, global, or shared package state) — data is harder to reorganize than functions because there is no way to "forward" a data access the way a function call can be redirected.

**Mechanics:**
1. Create accessor functions (getter and setter) for the variable.
2. Replace every direct reference with a call to the appropriate accessor, one at a time.
3. Restrict the variable's visibility once all access goes through the accessors.
4. Test after each replacement.
- Choose the protection level deliberately: reference-only (controls reassignment), copy-on-get (prevents shared mutation), or an immutable wrapper (enforces immutability) — pick the lightest one that fits the risk.
- Immutable data needs this less (no mutation to guard against); heavy self-encapsulation *inside* a single class is usually a sign the class itself is too large.

### Split Phase
**When:** one function mixes two different concerns, or the shape of its input doesn't match what the core logic actually needs — sequential steps that operate on genuinely different data sets belong in different phases.

**Mechanics:**
1. Extract the second phase into its own function.
2. Identify (or design) an intermediate data structure that phase one will hand to phase two, and make it a parameter of the phase-two function.
3. Move any parameters that are actually produced by phase one out of phase two's signature and into the intermediate structure.
4. Extract the first phase into its own function that builds and returns that intermediate structure.
- Two valid shapes for phase one's output: a plain data structure (fields consumed by phase two), or a small transformer/behavior-rich object with methods phase two calls.

### Replace Conditional with Polymorphism
*Resolves the case where Replace Nested Conditional with Guard Clauses doesn't apply; uses Combine Functions into Class and Extract Function.*

**When:** a set of types needs to handle the same operation differently, especially when the same `switch`/`if` chain on a type code is duplicated across more than one function — not for a single simple `if/else`, which should stay as-is.

**Mechanics:**
1. Create a class (with a factory function to construct the right one) for each branch/variant.
2. Move the conditional function itself up to the shared superclass/base case.
3. If the branch logic isn't already self-contained, Extract Function first.
4. Override the method in each subclass with just that branch's logic, one variant at a time, testing between each.
5. Leave a sensible default in the superclass, or make the base method abstract if there is no sensible default.

### Remove Dead Code
**When:** code exists that nothing calls anymore. Unused code doesn't slow the system down, but it burdens every reader who has to figure out whether it matters — and version control already remembers it, so there is no reason to keep it "just in case" (including no reason to comment it out instead of deleting it).

**Mechanics:**
1. If the code could be called from outside the current scope, search for callers first.
2. Delete the dead code.
3. Test.

### Decompose Conditional
*Uses Extract Function; resolves Replace Magic Literal along the way.*

**When:** a conditional is complex enough (through length, nesting, or non-obvious logic) that the code shows *what* happens but hides *why* — this is one of the highest-value places to apply Extract Function.

**Mechanics:**
1. Extract Function on the condition itself, and on each branch (the "then" and the "else"), giving each a name that explains its purpose.

### Combine Functions into Class
*Requires Encapsulate Record; alternative: Combine Functions into Transform (prefer that when the data should stay immutable / a functional style is preferred).*

**When:** a group of functions all operate on the same set of data, repeatedly passing the same parameters around, and the related calculations are scattered rather than organized together.

**Mechanics:**
1. Encapsulate Record — wrap the shared data in a record/class.
2. Move Function — move each of the scattered functions into the new class as methods.
3. Remove the now-redundant parameters from each method's signature (the data is available as class members).
4. Extract and move any further related logic into the class as additional methods.
- Prefer a class over a functional transform when the data may be mutated and derived values must stay consistent with it; prefer a transform for a single immutable-data pipeline.

### Replace Nested Conditional with Guard Clauses
*Resolves/uses Consolidate Conditional Expression.*

**When:** nested `if/else` treats every branch as equally important, but really one branch is the normal path and the others are unusual, early-exit conditions — Fowler frames the two conditional styles as "if-then-else gives equal weight to both branches" vs. "a guard clause says: this case isn't the main point of the function, handle it and get out."

**Mechanics:**
1. Pick the outermost condition that represents an unusual/edge case and rewrite it as a guard clause (an early return).
2. Test.
3. Repeat inward for the next unusual condition.
4. If several guard clauses end up returning the same result, consolidate them into a single condition (Consolidate Conditional Expression).

## Workflow for using this catalog

1. **Name the smell.** Describe the code's problem in plain language before reaching for a technique — "this function does two unrelated things" is more actionable than "this feels messy."
2. **Match it in the quick map** above, or scan [references/CATALOG.md](references/CATALOG.md) if it isn't one of the twelve.
3. **Follow the mechanics as an ordered checklist**, one small step at a time, testing after each step. If a step is hard to take safely, look for a smaller intermediate technique (the notes above call this out explicitly for Inline Function and Introduce Parameter Object).
4. **Check for the technique's inverse** if the direction of the move turns out to be wrong, or if it was applied where it doesn't fit — most techniques in the catalog are one half of a named pair (see the CATALOG for the full inverse list).
5. **Stop and reassess if the diff stops looking behavior-preserving.** A technique that changes what the program does has stopped being a refactoring.

## Common pitfalls to avoid

- Chasing short functions as a goal in themselves — the trigger is "needs effort to understand," not line count.
- Inlining or extracting in one big leap instead of the small, tested steps the mechanics describe.
- Applying Replace Conditional with Polymorphism to a single, simple `if/else` that isn't duplicated elsewhere — most conditionals should stay conditionals.
- Forgetting that Encapsulate Variable applied *inside* a single class to its own fields is usually overkill and a sign the class should be split instead.
- Treating a Split Phase intermediate data structure as optional — without it, the two phases stay coupled and the split buys nothing.
- Deleting code without checking for external callers first when it might be part of a public API.

## Related skills

- **refactoring-checklist** — decides *whether/when/how-safely* to refactor a spotted smell (priority matrix, risk gate, small-steps protocol); this catalog supplies the mechanics once that skill says go. Use the two together.
- **stepdown-rule** — decomposition inside a single function once its parts have the right names; complements Extract Function.
- **analyze-cohesion** — decide *whether* a class or module should split at all before reaching for Extract Class / Combine Functions into Class.
- **codebase-design** — the deep-module vocabulary for judging whether an Extract Function/Class result is actually a better seam, not just a smaller one.
- **tdd** — the test discipline that makes "test after each step" possible in the first place.
