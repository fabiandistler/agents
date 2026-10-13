# Glossary and ADR formats

Adapted from Matt Pocock's `domain-modeling` skill (`GLOSSARY-FORMAT.md`,
`ADR-FORMAT.md`) in mattpocock/skills at upstream commit `49dd158` (v1.3.1).
Copyright (c) 2026 Matt Pocock, MIT License; full text in `../UPSTREAM-LICENSE`.

## GLOSSARY.md

One `GLOSSARY.md` at the repo root, unless a `GLOSSARY-MAP.md` there lists
several contexts, each with its own `GLOSSARY.md` (and possibly its own
`docs/adr/`). With a map, infer which context the term belongs to; if unclear,
ask.

```md
# {Context name}

{One or two sentences on what this context is and why it exists.}

## Language

**Order**:
{One or two sentences defining the term.}
_Avoid_: Purchase, transaction
```

- Be opinionated: when several words name one concept, pick the best and list
  the others under `_Avoid_`.
- One or two sentences per definition. Define what it *is*, not what it does.
- Only terms specific to this project's domain. General programming concepts
  do not belong, even when the project uses them heavily.
- Group terms under subheadings when natural clusters emerge.

## ADRs

ADRs live in `docs/adr/` as `NNNN-slug.md`. Scan for the highest existing
number and add one. Create the directory only when the first ADR is needed.

```md
# {Short title of the decision}

{One to three sentences: the context, what was decided, and why.}
```

An ADR can be a single paragraph. Add a `Status` field, "Considered options",
or "Consequences" only when they carry real information.

Offer an ADR only when all three hold:

1. **Hard to reverse**: changing course later has a meaningful cost.
2. **Surprising without context**: a future reader would ask why it was done
   this way.
3. **The result of a real trade-off**: there were genuine alternatives.
