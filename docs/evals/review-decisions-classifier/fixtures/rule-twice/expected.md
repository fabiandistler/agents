# Expected: rule-twice

Rule: when the change implements a rule that also lives elsewhere, read both
versions and queue a Behaviour decision if they differ. The comment in
`web/signup.js` says it mirrors `server/validate.py`, whose limit is 32; the
browser copy uses 30.

| Category | File | The card also |
| --- | --- | --- |
| Behaviour | `web/signup.js` | names both limits, 30 and 32 |

Forbidden: none.
