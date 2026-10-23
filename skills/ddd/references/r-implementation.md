# R Implementation Conventions

These language-specific conventions supplement [`implementation-conventions.md`](implementation-conventions.md). Read this page when implementing a Domain Model in R.

## Aggregates

- Represent an R aggregate as an R6 class with private fields; expose access and state changes through methods on the aggregate root.
- Call `private$validateInvariants()` with `checkmate` after every state change.

## Value objects

- Represent R value objects as immutable R6 classes. Mutating methods return a new instance. Follow the generic value-object rules in `implementation-conventions.md` for equality and identity.

## Package boundary

- Map one R package to one bounded context. A bounded context may contain several subdomains; see `implementation-conventions.md` for the distinction.
