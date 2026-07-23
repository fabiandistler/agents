# Full Technique Index (62 techniques)

One line per technique, grouped the way Fowler's catalog groups them. Named
inverse/paired techniques are cross-referenced with "↔". The twelve techniques
with full mechanics live in the main [SKILL.md](../SKILL.md); everything else
here is a pointer — go to the source note (or Fowler's book) for the mechanics
when you need to execute one of these.

## Composing functions

- **Extract Function** ↔ Inline Function — pull a code fragment into a well-named function; the most common refactoring. *(full mechanics in SKILL.md)*
- **Inline Function** ↔ Extract Function — collapse a function into its callers when the body is as clear as the name. *(full mechanics in SKILL.md)*
- **Extract Variable** ↔ Inline Variable — name a piece of a complex expression. *(full mechanics in SKILL.md)*
- **Inline Variable** ↔ Extract Variable — remove a variable that communicates no more than the expression it holds.
- **Rename Variable** — improve a variable's name; names are described as "the heart of clear programming."
- **Encapsulate Variable** — replace direct data access with functions, turning a hard data reorganization into an easier function reorganization. *(full mechanics in SKILL.md)*
- **Introduce Parameter Object** — replace a recurring group of parameters (a data clump) with one structured object. *(full mechanics in SKILL.md)*
- **Combine Functions into Class** ↔ (alt: Combine Functions into Transform) — group functions that operate on the same data into a class. *(full mechanics in SKILL.md)*
- **Split Phase** — split code that does two different things into sequential phases joined by an intermediate data structure. *(full mechanics in SKILL.md)*

## Encapsulation

- **Encapsulate Record** — turn a plain record structure into a class, replacing direct field access with controlled accessors.
- **Encapsulate Collection** — stop direct manipulation of a collection's contents; replace it with controlled add/remove methods.
- **Replace Primitive with Object** — turn a primitive that has grown domain behavior into a small value class. *(full mechanics in SKILL.md)*
- **Replace Temp with Query** — replace a temporary variable with a method call, making the value re-extractable elsewhere.
- **Extract Class** — split an overloaded class into focused, single-responsibility classes.
- **Inline Class** ↔ Extract Class — collapse a class that no longer earns its keep into another class.
- **Hide Delegate** ↔ Remove Middle Man — have a server object hide its delegate so clients call the server, not `client → server → delegate`.
- **Remove Middle Man** ↔ Hide Delegate — let the client call the delegate directly when the server has become pure, unhelpful forwarding.
- **Substitute Algorithm** — replace a complex algorithm with a clearer one that produces the same result.

## Moving features

- **Move Function** — move a function to the context (module/class) where it fits better.
- **Move Field** — move a data field between structures for better data organization.
- **Move Statements into Function** ↔ Move Statements to Callers — fold statements that are always repeated at call sites into the called function.
- **Move Statements to Callers** ↔ Move Statements into Function — push behavior that now varies by caller out of a function and into its callers.
- **Replace Inline Code with Function Call** — replace duplicated inline code with a call to an existing function.
- **Slide Statements** — move related code so it sits next to the other code it's related to.
- **Split Loop** — split a loop that does more than one thing into separate, single-purpose loops.
- **Replace Loop with Pipeline** — replace an imperative loop with a declarative collection pipeline.
- **Remove Dead Code** — delete code nothing calls anymore. *(full mechanics in SKILL.md)*

## Organizing data

- **Split Variable** — split a variable that is assigned more than one responsibility into separate variables.
- **Rename Field** — improve a field's name in a record structure or class.
- **Replace Derived Variable with Query** — replace a value that could be computed on demand with a query method instead of storing it.
- **Change Reference to Value** — turn a referenced (shared, mutable-by-reference) object into an immutable value object.
- **Replace Magic Literal** — replace an unexplained literal constant with a named constant.

## Simplifying conditional logic

- **Decompose Conditional** — extract a complex condition and its branches into named functions. *(full mechanics in SKILL.md)*
- **Consolidate Conditional Expression** ↔ Replace Nested Conditional with Guard Clauses — combine multiple conditionals that produce the same result into a single expression.
- **Replace Nested Conditional with Guard Clauses** ↔ Consolidate Conditional Expression — turn "unusual case" branches into early-return guard clauses. *(full mechanics in SKILL.md)*
- **Replace Conditional with Polymorphism** — replace type-code dispatch logic with polymorphic subclasses. *(full mechanics in SKILL.md)*
- **Introduce Special Case** — replace duplicated special-case checks with a Special Case object (e.g. a Null Object).
- **Introduce Assertion** — make an implicit assumption explicit as an assertion.
- **Replace Control Flag with Break** — replace a control-flag variable with `break`/`continue`/`return`.

## Refactoring APIs

- **Change Function Declaration** — rename a function or add/remove/reorder its parameters; the umbrella technique for changing a signature (subsumes Rename Function and Add/Remove Parameter).
- **Separate Query from Modifier** — split a function that both returns a value and has a side effect into one that queries and one that modifies.
- **Parameterize Function** ↔ (opposite direction of splitting similar functions) — merge near-identical functions that differ only by a literal value into one parameterized function.
- **Remove Flag Argument** — replace a boolean flag parameter with explicit functions for each flag value.
- **Preserve Whole Object** — pass a whole object to a function instead of pulling several values out of it first.
- **Replace Parameter with Query** ↔ Replace Query with Parameter — drop a parameter the callee can derive itself via a query.
- **Replace Query with Parameter** ↔ Replace Parameter with Query — move a query the function makes internally out into a parameter, reducing hidden dependencies (aiming for referential transparency).
- **Remove Setting Method** — remove a setter to make a field effectively immutable after construction.
- **Replace Constructor with Factory Function** — replace direct constructor calls with a factory function for more flexibility.
- **Replace Function with Command** ↔ Replace Command with Function — wrap a complex function in a Command object for more flexible decomposition.
- **Replace Command with Function** ↔ Replace Function with Command — simplify a Command object back into a plain function when the extra structure isn't earning its cost.
- **Replace Error Code with Exception** — replace a returned error code with a thrown exception.
- **Replace Exception with Precheck** — replace exception handling with an explicit condition check for cases that are actually expected.

## Dealing with inheritance

- **Pull Up Method** ↔ Push Down Method — move an identical method from subclasses up to the superclass.
- **Pull Up Field** ↔ Push Down Field — move an identical field from subclasses up to the superclass.
- **Pull Up Constructor Body** — move common constructor code from subclasses up to the superclass.
- **Push Down Method** ↔ Pull Up Method — move a method from the superclass down to only the subclasses that need it.
- **Push Down Field** ↔ Pull Up Field — move a field from the superclass down to only the subclasses that need it.
- **Extract Superclass** — extract features shared by similar classes into a new superclass.
- **Remove Subclass** — eliminate a subclass that adds too little value and replace it with a field on the parent.
- **Replace Type Code with Subclasses** — replace a type-code field with subclasses so the type gets real polymorphism and type-specific features.
- **Replace Superclass with Delegate** — replace inheritance with delegation to a separate object; addresses inheritance misuse and type/instance naming collisions.
- **Return Modified Value** — change a function that mutates a variable via side effect into one that returns the new value instead.

## Full inverse-pair reference

Pairs explicitly named as inverses (or as alternates addressing the same
concern from opposite directions) across the source notes:

| Technique | Inverse / counterpart |
|---|---|
| Extract Function | Inline Function |
| Extract Variable | Inline Variable |
| Extract Class | Inline Class |
| Hide Delegate | Remove Middle Man |
| Move Statements into Function | Move Statements to Callers |
| Pull Up Method / Field | Push Down Method / Field |
| Replace Function with Command | Replace Command with Function |
| Replace Parameter with Query | Replace Query with Parameter |
| Consolidate Conditional Expression | Replace Nested Conditional with Guard Clauses |
| Combine Functions into Class | Combine Functions into Transform (alternate, not a separate note here) |
