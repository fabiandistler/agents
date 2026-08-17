# Remediation reference

Read this after `coupling_metrics.py` has flagged components off the Main
Sequence (`D` above the threshold). First confirm the finding is real — see
the "limitations" section in [metrics.md](metrics.md): a high `D` is a prompt
to look, not a verdict. A stable, concrete, genuinely-finished utility can sit
in the Pain corner and need no change at all.

When a fix *is* warranted, the move depends on which corner the component is
in. The two zones fail in opposite ways and want opposite treatments.

## Zone of Pain — low A, low I (concrete + depended-upon + stable)

The component is brittle: many things depend on it, so changes ripple widely,
but it is all implementation, so there is no seam to change behind. The goal is
to introduce abstraction at the points others depend on — raise A — so the
component can change behind a stable interface (move it toward the Stable
Abstractions Principle).

- **Extract an interface / port for the depended-upon surface.** Define the
  contract its consumers actually use, have them depend on that, and let the
  concrete implementation vary behind it. This is the single highest-leverage
  move — it converts afferent coupling on *implementation* into afferent
  coupling on *abstraction*.
- **Apply Dependency Inversion.** Both the consumers and the implementation
  should depend on the abstraction, not on each other. The abstraction belongs
  with the consumer's needs, not the implementation's convenience.
- **Split a God-module.** A `core`/`utils`/`common` grab-bag earns a high Cᵃ
  for accidental reasons — everything imports it for unrelated things. Break it
  along real responsibilities so each piece is depended on for one coherent
  reason, and the wide blast radius shrinks.
- **Stabilize the public surface.** If consumers reach into internals, the
  whole module is the contract. Narrow what is exported so the stable part is
  small and deliberate.
- **When it's fine:** a small, truly stable leaf (date math, money, a units
  table) with no pending change pressure. Leave it. Stability that is earned is
  a feature, not debt.

## Zone of Uselessness — high A, high I (abstract + unused)

The component is over-built: layers of abstraction that nothing depends on. The
goal is to **remove indirection**, not add more.

- **Delete speculative abstraction.** Interfaces, factories, and base classes
  added "for future flexibility" that never arrived. If `Cᵃ = 0`, nobody is
  using the abstraction — delete it.
- **Inline single-implementation interfaces.** An interface with exactly one
  implementer and one caller is pure ceremony. Collapse it into the concrete
  type until a second implementation actually forces the seam.
- **Collapse pass-through layers.** Adapters/wrappers that only forward calls
  add efferent coupling (raising I) and abstraction (raising A) while adding no
  behavior — exactly the two axes that define this corner. Remove them.
- **Re-anchor genuinely useful abstraction.** If an abstraction *should* be used
  but isn't, the fix may be to route consumers through it (raising Cᵃ, lowering
  I) rather than to delete it — confirm which case you are in before cutting.

## The deeper fix

Recurrent, system-wide high coupling is rarely cured one outlier at a time —
it usually reflects shallow modules with wide interfaces. The durable remedy is
**deeper modules**: more functionality behind smaller interfaces, so there are
simply fewer edges to couple on. If the coupling is structural — the wrong
components exist at all, or the topology is wrong — escalate to
`architecture-pattern-advisor`. And record any significant restructuring
decision with `adr-workflow` so the rationale (and the metrics baseline that
motivated it) survives.
