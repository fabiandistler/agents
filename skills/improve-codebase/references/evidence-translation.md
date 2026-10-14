# Evidence translation: coupling-cohesion terms into the report vocabulary

`coupling-cohesion` reports in its own terms (boundary, integration strength,
distance, volatility, groups, LCOM). The report and the interview use only the
terms in `design-vocabulary.md`. Translate at the hand-off: keep the measured
value as evidence, replace the term around it. No term from the left column
appears in a card except inside a quoted metric value.

## Contents

- [Mode A: cohesion](#mode-a-cohesion)
- [Mode C: one dependency](#mode-c-one-dependency)
- [Churn and co-change](#churn-and-co-change)
- [Writing the evidence line](#writing-the-evidence-line)

## Mode A: cohesion

| coupling-cohesion says | Write in the report |
|---|---|
| unit (class, file, package) | module |
| 1 group | the module's parts share state; it hangs together. A shallow verdict must then come from the deletion test, not from cohesion |
| 2+ groups, "split with seam" | two modules colocated behind one interface; name the seam between the groups |
| "merge with fold-back target" | shallow module; deleting it concentrates complexity in the fold-back target, which deepens |
| "leave with reason" | no candidate; drop the finding unless other evidence carries it |
| coincidental or logical cohesion | parts colocated, not related: no depth, no locality |
| functional or sequential cohesion | one concept behind one interface: locality holds |

## Mode C: one dependency

| coupling-cohesion says | Write in the report |
|---|---|
| boundary | seam |
| upstream / downstream | the module behind the seam / its caller |
| deepest sharing (Intrusive) | the caller reaches past the interface into the implementation: leaks across the seam |
| lockstep rules (Functional coupling) | one rule implemented on both sides of the seam: no locality |
| shared concepts (Model) | the interface exposes the module's internal model, so it is nearly as wide as the implementation |
| surface only (Contract) | narrow interface; the seam holds |
| distance (object, package, service) | how far apart the two modules live; the farther, the more a leak costs |
| volatility (changes often / rarely) | how often the leaked knowledge changes; back it with the churn count |
| knowledge leak | leaks across the seam (the headline finding) |
| low cohesion (low strength, low distance) | shallow modules side by side that share nothing; candidates to merge |
| high cohesion (strength without distance) | the two sides belong inside one deep module. Already behind one interface: not a finding. Living in separate modules: supports merging them behind one interface, which is the deepening finding |
| loose coupling | a healthy seam; not a finding |
| contract in name only | interface mirrors the implementation: shallow |
| exit: reduce strength | shrink the interface |
| exit: reduce distance | pull both sides behind one seam: deepen |
| exit: accept on stability | leave, with the revisit condition as an ADR candidate |

"Balanced" is not "leave". Inside one package distance is low everywhere, so
Mode C tends to report every dependency as balanced (high cohesion). That
verdict neither confirms nor kills a finding that `path:line` evidence
carries: quote it on the card, do not let it decide.

## Churn and co-change

| refactoring says | Write in the report |
|---|---|
| hotspot (high churn x size) | a module that changes often, so deepening it pays off repeatedly |
| co-changers | modules that change together: one concept spread across seams, no locality |

## Writing the evidence line

Every finding carries at least one of:

- `path:line` for a claim about code (the leaking call, the duplicated rule,
  the pass-through method).
- A metric value quoted as the instrument printed it: `groups=2 [LCOM=7]`,
  `sharing=intrusive, distance=package, volatility=often`, `commits=41 in 12
  months`, `co-changed 9x with src/pricing.py`.

The prose around the value is in report vocabulary; the value itself stays
verbatim so the user can rerun the instrument and compare.
