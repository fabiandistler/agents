# Rebalancing reference

Read this after the balance rule (or `scripts/balance_check.py`) has flagged a
dependency as imbalanced. Every imbalance has exactly three exits — lower the
strength, lower the distance, or accept it while volatility stays low. Which
exit fits depends on *why* the strength is high and on whether the components
genuinely belong together.

## Knowledge leak: high strength × high distance (volatile)

The expensive quadrant — cascading changes across service, repo, or team
boundaries. Work down the strength ladder first; only pull components closer
when the shared knowledge is irreducible.

### If the strength is intrusive

Stop the intrusion before anything else — it is unbounded shared knowledge.

- Replace foreign-database reads/writes with an API or published events owned
  by the upstream.
- Replace internals imports with the upstream's public interface; if the
  public interface is missing something, add it upstream rather than
  reaching around it.
- Where the upstream cannot change (vendor, legacy), wrap it: one adapter
  owns the intrusion, everyone else couples to the adapter's contract.

### If the strength is functional

The components implement the same business rules from afar.

- Extract the shared rule into one owner and have the others call or subscribe
  to it — one source of truth instead of lockstep edits.
- If the rule must be evaluated in several places (e.g. frontend + backend
  validation), generate the duplicates from one specification (schema,
  rule table) so a change is one edit plus regeneration.
- If the functionality is genuinely one workflow smeared across services,
  that is a boundary drawn through the middle of a use case — consider the
  reduce-distance exit instead.

### If the strength is model

The upstream's domain model travels across the boundary.

- Introduce a real contract: an integration-specific schema owned by the
  boundary, translated at both ends (anti-corruption layer downstream,
  published language upstream). The contract must be a model *of* the model —
  if it mirrors internal entities field-for-field, nothing was gained.
- Slim the payload: share the fields consumers act on, not the entity.
- Version the contract and add consumer-driven contract tests so future model
  churn stops at the boundary instead of propagating.

## Reduce distance: when the knowledge is irreducible

If after honest effort the components still must change together — same core
business rule, same transaction, same use case — the coupling is telling you
they are one thing. Move them together instead of weakening the link:

- Merge the services, or move the code into one component/package under one
  deploy unit.
- Put both under one team (the socio-technical rung matters as much as the
  physical one).
- This is the "modular monolith over distributed monolith" move: high
  strength at low distance is cohesion, the balanced quadrant.

## Low cohesion: low strength × low distance

The mirror imbalance — unrelated things co-located, so every local change
wades through noise and the lifecycle is shared for no benefit (`utils`
grab-bags, "common" libraries that force lockstep releases of strangers).

- Split along the actual knowledge boundaries; give each part its own home.
- For a shared library of strangers, split it so consumers depend only on
  what they use — freeing them from each other's release cadence.
- This overlaps `analyze-cohesion` territory; use its scale to decide the
  split lines.

## Accept, eyes open: the NOT VOLATILITY exit

Legitimate when the shared knowledge is demonstrably stable: a frozen legacy
system, a finished generic subdomain, a standard that changes on a
years-long cycle.

- Record it — an ADR (`adr-workflow`) naming the imbalance, the stability
  evidence, and the **revisit condition**: the event that voids the
  acceptance (upstream back under active development, subdomain reclassified
  toward core, first cascading change actually observed).
- Do not spend rebalancing effort here while genuinely volatile leaks exist
  elsewhere; volatility is what ranks the backlog.

## Choosing the exit

| Situation | Exit |
|---|---|
| Intrusion into internals or a foreign database | Reduce strength: public interface / events, or wrap the legacy |
| Same business rule maintained in several places | Reduce strength: single owner or generate from one spec |
| Domain model crossing a service boundary | Reduce strength: contract + translation at both ends |
| Irreducibly shared use case split across services | Reduce distance: merge into one deploy unit / team |
| Strangers sharing a package or library lifecycle | Split them (low-cohesion imbalance) |
| Strong coupling to something that no longer changes | Accept via ADR with a revisit condition |

After rebalancing, re-run `scripts/balance_check.py` on the updated
assessments — and where the fix was structural, re-check the quantitative
picture with `analyze-coupling` to confirm the dependency graph moved too.
