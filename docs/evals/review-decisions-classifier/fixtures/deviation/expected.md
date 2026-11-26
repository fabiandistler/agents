# Expected: deviation

Rule: the Deviation category, a change the issue does not ask for. The issue
asks for `--dry-run` only; the change also cuts the default retention from 30
to 7 days. That change also fits Public surface (a default), and the earlier
category wins.

| Category | File | The card also |
| --- | --- | --- |
| Deviation | `cleanup.py` | names the retention change, 30 to 7 days |

Forbidden: a card on the name `--dry-run`, which the issue states literally.
