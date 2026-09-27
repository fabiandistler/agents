# Balanced Coupling model reference

The model below is Vlad Khononov's **Balanced Coupling**, from *Balancing
Coupling in Software Design* (Addison-Wesley, 2024) and the companion site
[coupling.dev](https://coupling.dev). It unifies the classic coupling
taxonomies — structured design's module coupling and connascence — into three
dimensions, and gives one rule for when a dependency helps modularity and when
it feeds complexity. This page is a distillation in this repo's own words;
consult the book for the full treatment, case studies, and the finer-grained
numeric scales.

## Premise: coupling is shared knowledge

Two components are coupled when they can make each other change. What
propagates the change is *knowledge* that crosses the boundary: knowledge of
implementation details, of business rules, of the domain model, or merely of
an agreed contract. Coupling is therefore not inherently bad — a system with
no coupling does nothing. Design does not eliminate coupling; it decides
**how much knowledge** may cross **which distances**, given **how often** that
knowledge changes.

## Dimension 1: Integration strength

Strength categorizes the kind (and thereby the amount) of knowledge the
downstream component consumes. Four levels, strongest to weakest:

### Intrusive coupling

Integration through private interfaces: reaching into another component's
internals, reading or writing its database, depending on undocumented
behavior, monkey-patching, reflection into private state. Assume *all* of the
upstream's implementation knowledge is shared — any internal change, made for
any reason, can cascade. Intrusive coupling is both the strongest and the most
implicit level: the upstream usually cannot even see who depends on what.

Cues: imports from `internal`/`_private` paths, direct foreign-database
queries, fixtures that replicate another component's schema, tests that break
on refactorings which changed no public behavior.

### Functional coupling

The components implement the same or interlocking business requirements, so a
requirement change forces coordinated edits — regardless of whether any code
artifact is shared. The textbook case is the same validation rule duplicated
in frontend and backend: change the spec, touch both, or the system behaves
inconsistently. Sequential workflows split across components (B must run after
A, B compensates A's failure) are functional coupling too.

Cues: "when we change X we always also change Y" in commit history, duplicate
business constants or rule tables, cross-component sagas and compensation
logic.

### Model coupling

The components share a model of the business domain — the same entities,
relationships, and concepts — but not the logic over it. When the team's
understanding of the domain shifts (an entity splits, a concept is renamed or
restructured), every component holding that model must adapt.

Cues: shared domain classes or a shared "common"/"domain" library, events or
messages that carry the producer's internal entities verbatim, several
services persisting the same entity shape.

### Contract coupling

The components share only an integration-specific contract: an API
specification, an event schema, a DTO. The contract is deliberately *a model
of the model* — one more abstraction level that hides implementation, business
logic, and the internal domain model behind a surface the boundary owns and
keeps stable. Internals, logic, and even the domain model can be rebuilt
without cascading; only changes to the contract itself propagate.

Cues: versioned API/event schemas distinct from internal types, explicit
translation at the boundary (anti-corruption layer), consumer-driven contract
tests.

### Relation to the classic scales

The four levels generalize the older taxonomies: structured design's module
coupling scale (content, common, external, control, stamp, data) grades
intrusive-to-contract knowledge for procedural code, and connascence grades
it for shared representations — static connascence (name, type, meaning,
algorithm, position) differentiates degrees of contract and model coupling,
dynamic connascence (execution order, timing, value, identity) differentiates
degrees of functional coupling. When you need to compare two dependencies
*within* one strength level, those scales are the tiebreakers.

Strength also tracks explicitness: contract coupling is the most explicit
(the shared knowledge is written down and versioned), intrusive the most
implicit (nobody agreed to share anything).

## Dimension 2: Distance

Distance is how far apart the coupled components live — and therefore what a
coordinated change costs. The ladder, near to far:

1. Same function/method
2. Same class or file
3. Same package/namespace
4. Same component/library
5. Same runtime, different service — or different deploy units
6. Different systems, different teams

Two forces move along it in opposite directions:

- **Cost of coordinated change** rises with distance: more files, repos,
  deployments, review cycles, and — the socio-technical part — more meetings.
  A team boundary adds distance even when the code sits in one repository;
  Conway's law is a distance statement.
- **Lifecycle coupling** falls with distance: components close together must
  be tested, versioned, and deployed together. Distance buys independent
  lifecycles — this is what "decoupling" meant in most monolith-to-services
  migrations. Asynchronous integration pushes lifecycle coupling down further
  at the same physical distance.

Distance is thus neither good nor bad; it is a cost structure. The question
the balance rule answers is whether the knowledge crossing that distance is
light enough to afford it.

## Dimension 3: Volatility

Volatility is the likelihood that the *shared* knowledge changes. Coupling to
a component that never changes costs nothing in practice, however strong the
dependency — which is why volatility can rescue an otherwise imbalanced
design.

Estimating it:

- **Subdomain type** (the DDD lens; classify with `ddd-advisor`): core
  subdomains are the business's competitive edge and churn continuously;
  supporting subdomains change occasionally; generic subdomains (auth,
  billing engines, email) are stable, often bought not built. Wardley
  evolution stages (genesis → commodity) give the same reading.
- **Evidence**: change frequency of the shared surface in version control,
  the upstream's roadmap, whether it is actively developed or in maintenance
  mode, upcoming regulatory or product pressure on the shared rules.

Judge the volatility of the shared knowledge, not the component overall: a
volatile service behind a frozen contract presents low volatility to contract
consumers — that is precisely what the contract is for.

## The balance rule

Reduce strength and distance to high/low (strength: intrusive, functional,
and model are high, contract is low; distance: rungs 1–3 are low, 4–6 are
high, shifted by team boundaries). The quadrants:

| | Low distance | High distance |
|---|---|---|
| **High strength** | **High cohesion** — must-change-together things kept together; cascades are cheap. Balanced. | **Tight coupling / knowledge leak** — expensive cascades across boundaries; the distributed-monolith pattern. Global complexity. |
| **Low strength** | **Low cohesion** — unrelated things co-located, adding noise to every local change. Local complexity. | **Loose coupling** — contract-level knowledge across a distance. Balanced. |

As binary expressions:

```
MODULARITY = STRENGTH XOR DISTANCE
COMPLEXITY = STRENGTH AND DISTANCE          -- the global, expensive kind
BALANCE    = (STRENGTH XOR DISTANCE) OR NOT VOLATILITY
```

Volatility is the pragmatism term: an imbalanced design over *stable*
knowledge is tolerable — a legacy system that no longer evolves may stay a
ball of mud. But stability is an assumption with a shelf life; every
`NOT VOLATILITY` acceptance should carry a revisit condition (see
[rebalancing.md](rebalancing.md)).

The book refines all three dimensions to numeric scales and a continuous
formula; the binary form above is the working approximation this skill (and
`scripts/balance_check.py`) applies. When a pair sits near a threshold —
model-vs-contract strength, library-vs-service distance — say so rather than
letting the binary hide the judgment call.

## Fractal modularity

The model is self-similar across abstraction levels: methods within a class,
classes within a package, packages within a service, services within a
system. High cohesion at one level *is* high strength at low distance one
level down; a bounded context is a low-strength, high-distance boundary; a DDD
aggregate is a cluster of maximal strength kept at minimal distance behind
one contract (its root). The same rule that shapes a function's parameter
list shapes a system's service boundaries — which is why the assessment
workflow never changes, only the level it is applied at.
