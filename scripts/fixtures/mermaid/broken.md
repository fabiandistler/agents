# Broken Mermaid fixture

The CI `mermaid` job must reject this file: the C4 macro name is misspelled
and its argument list is never closed.

```mermaid
C4Context
  Persn(user, "User"
```
