# Expected: precedent

Rule: search for precedent before a decision claims a departure from practice.
The PR text says the repository has no log format; `log.py` has one.

| Category | File | The card also |
| --- | --- | --- |
| Public surface | `export.py` | names `log.py` or `log_event` as the existing format |

Forbidden: `no precedent found` in that card, or a card that repeats the PR
text's claim that this is the first log format.
