# Decision Drivers

The diagnostic questions for step 2, plus how answers map to candidate patterns. Ask only the few questions that actually discriminate for the project at hand. Heuristics are *hints* to justify a recommendation, not a rigid score.

## Diagnostic questions

| # | Question | Short answer scale |
|---|----------|--------------------|
| 1 | Project type & main language | Library / CLI / web service / data pipeline / desktop · Python / R / other |
| 2 | Team size & contributors | Solo · small (2–5) · multiple teams |
| 3 | Domain complexity | CRUD-thin · moderate rules · rich domain logic |
| 4 | Scaling needs | Single process is fine · one hotspot needs independent scaling · many independent load profiles |
| 5 | Independent deployability | One release train · some modules need separate release cadence · strict per-team autonomy |
| 6 | Data consistency | Strong/transactional · mostly strong · eventual is acceptable |
| 7 | Testability & external integrations | Few/stable · several swappable (DB, payment, 3rd-party APIs) · must mock heavily |
| 8 | Expected lifetime & change rate | Throwaway/short · long-lived, steady · long-lived, fast-evolving |
| 9 | Operational maturity | No CI/CD or on-call · CI/CD in place · full observability + on-call |

## For an existing repo: what to inspect (read-only)

- Top-level layout: split by technical layer (`controllers/`, `models/`, `services/`) or by feature/domain?
- Module boundaries: clear public surfaces, or modules reaching into each other's internals/tables?
- Dependency direction: does business logic depend on frameworks/DB, or are those at the edges?
- Smells: God-modules, circular imports, business logic inside transport (HTTP) or ORM models, a single `utils` dumping ground, one schema shared by unrelated features.

## Heuristics — driver → favored / disfavored

### Topology axis

| Signal | Favors | Disfavors |
|--------|--------|-----------|
| Solo / small team, low ops maturity | Monolith / modular monolith | Microservices |
| Single process handles load | Monolith / modular monolith | Microservices, serverless |
| One component has a distinct scaling/load profile | Modular monolith now, extract that one later; or microservices | — |
| Multiple teams needing release autonomy | Microservices | Monolith |
| Strong cross-entity transactional consistency | Monolith / modular monolith | Microservices (distributed transactions) |
| Spiky/event-triggered, stateless work | Serverless / functions, event-driven | Always-on monolith for that part |
| Mature CI/CD, observability, on-call | Microservices viable | — |
| Library / CLI / single R package | (no topology choice — skip axis) | — |

Default when unsure: **modular monolith** — monolith simplicity with seams to extract later.

### Code-organization axis

| Signal | Favors | Disfavors |
|--------|--------|-----------|
| Thin CRUD, small app | Layered (by technical layer) | Hexagonal (overhead) |
| Rich domain logic, long-lived | By-domain / package-by-feature, Clean/Onion | Flat technical layering |
| Many swappable external integrations; heavy mocking | Ports & Adapters (Hexagonal) | Direct framework/DB coupling |
| Multiple teams owning distinct features | By-domain / package-by-feature | Shared technical layers (merge contention) |
| Framework-centric, conventions matter (e.g. Django, Shiny) | Layered following framework convention | Fighting the framework with heavy hexagonal layers |
| Need strict dependency-inversion / testable core | Clean / Onion, Hexagonal | Layered with logic in controllers |

Common sweet spot for a long-lived service: **by-domain modules with hexagonal boundaries**, inside a modular monolith.
