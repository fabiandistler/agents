# Mode C — Is one dependency balanced?

Judge an individual dependency by *weight*, not count: how much knowledge flows
across the boundary (**integration strength**), how far apart the coupled
components live (**distance**), and how likely that shared knowledge is to
change (**volatility**). The model is Vlad Khononov's Balanced Coupling, from
*Balancing Coupling in Software Design* (Addison-Wesley, 2024) and
[coupling.dev](https://coupling.dev). The author also publishes it as the
`balanced-coupling` skill in the
[vladikk/modularity](https://github.com/vladikk/modularity) plugin
(CC BY-NC-SA 4.0), with the same four strength levels and balance rule. Its core rule
in plain language: heavy sharing is fine up close; only light contract
knowledge across distance unless proven stable with a revisit condition. The
binary form lives in
[balanced-coupling-model.md](balanced-coupling-model.md).

## Contents

- [Balanced-coupling workflow](#balanced-coupling-workflow)
- [Balanced-coupling output format](#balanced-coupling-output-format)
- [Balanced coupling — common mistakes](#balanced-coupling--common-mistakes)

A dependency is balanced when strength and distance offset each other — heavy
knowledge-sharing is fine up close (cohesion), and only light, contract-level
knowledge should cross large distances (loose coupling). Strong coupling across
a large distance is a **knowledge leak** heading toward a distributed monolith;
it is tolerable only when the shared knowledge is stable (low volatility).

Dimension definitions, the strength levels with recognition cues, the distance
and volatility ladders, and the balance quadrants live in
[balanced-coupling-model.md](balanced-coupling-model.md).
Fixes per imbalance live in [rebalancing.md](rebalancing.md);
open it alongside the model page whenever you accept an imbalance as stable, since
it holds the revisit conditions.

## Balanced-coupling workflow

The model is fractal: the same steps apply between methods, objects, packages,
services, or whole systems. Hold the level constant within one assessment.

### 1. List the dependencies to assess

Name the coupled pairs explicitly as *upstream* (owns the knowledge) and
*downstream* (depends on it); assess only relationships crossing the boundary
in question.

### 2. Classify integration strength

Identify the *strongest* kind of knowledge the downstream consumes
(plain language first, established term in brackets):

| Sharing | The downstream depends on… |
|---|---|
| **deepest sharing (Intrusive)** | private implementation details — internals, another component's database, undocumented behavior; any upstream change can break the downstream |
| **lockstep rules (Functional coupling)** | the same business rules — duplicated or interleaved logic that must change in lockstep on both sides |
| **shared concepts (Model)** | the upstream's model of the domain — its entities and concepts, but not its logic; changes to the entity shape propagate |
| **surface only (Contract)** | an integration-specific contract that hides implementation, logic, and model — the only light kind that should cross distance |

Functional *coupling* is not Mode A's functional *cohesion*: here it is the
second-strongest level, a leak when it crosses distance, not the best grade.

### 3. Assess distance

Place the pair on the distance ladder (plain language first, established
term in brackets): within one method (method) → between objects in one
package (object) → across packages in one repo (package) → across services
(service) → across systems (system). Distance is socio-technical: a team
boundary adds distance even between services in one repo, and asynchronous
integration adds lifecycle slack. Greater distance makes each coordinated
change cost more — so only surface-only (Contract) knowledge should travel
far.

### 4. Assess volatility

How likely is the *shared* knowledge to change? Read plain language first,
established term in brackets: changes often (core) versus changes rarely
(supporting, generic, low). Use the subdomain type as the first proxy
(classify with `members/ddd/SKILL.md`, read via the `architecture` router, if unclear), then correct with evidence:
commit history of the shared surface, roadmap pressure, and whether the
upstream is actively evolved or in maintenance mode. A low-volatility
acceptance is a loan, not a gift — it needs a revisit condition.

### 5. Apply the balance rule

Reduce strength and distance to high/low for the pair and check the quadrant
in [balanced-coupling-model.md](balanced-coupling-model.md#the-balance-rule)
— or run the pair through `balance_check.py`, which applies the rule uniformly
and sorts the leaks first:

```bash
python3 scripts/balance_check.py <your-input>.json
```

See `scripts/balance_check.example.json` for the format and
[balanced-coupling-model.md](balanced-coupling-model.md)
for how levels reduce to high/low.

### 6. Rebalance what's flagged

An imbalance has exactly three exits — pick per pair from
[rebalancing.md](rebalancing.md): reduce the strength
crossing the boundary, reduce the distance, or accept on proven stability with
a revisit condition (an ADR).

### 7. Sanity-check the verdicts

Binary high/low is a deliberate simplification — recheck generous distance
guesses and optimistic stability claims against git history; low-volatility
acceptances are loans, not gifts, and need a revisit condition.

## Balanced-coupling output format

Follows the [output contract](../SKILL.md#output-contract-all-modes):

```
Verdict: <fix | leave> — <balance verdict: knowledge leak | low cohesion | stable leak | stable clutter | high cohesion | loose coupling>
Evidence: <sharing (strength)=<level>, distance=<level>, volatility=<level>> — <what that means here, e.g. shared domain entities across services that change often>
Next step: <fix with seam | reason to leave, e.g. stable with revisit condition> — <concrete action>
```

## Balanced coupling — common mistakes

- **Counting instead of weighing.** One intrusive dependency outweighs a
  hundred contract-coupled ones. Never report "N dependencies" as the finding.
- **Calling every strong coupling bad.** High strength at low distance is
  cohesion — the good kind. Only strength *across distance* leaks knowledge.
- **Ignoring volatility.** A stable big ball of mud may be a perfectly sound
  thing to leave alone; flagging it wastes the team's change budget.
- **Contract in name only.** An "API" that mirrors the upstream's internal
  entities field-for-field is model coupling wearing a contract's clothes.
  A contract must be a model *of* the model, owned by the boundary.
- **Mixing abstraction levels.** Method-level and service-level assessments
  don't compare. Fix the level in step 1 and stay there.
