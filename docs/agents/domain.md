# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase. This repo is **single-context**: one `GLOSSARY.md` and
one `docs/adr/` at the root.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root. It holds the vocabulary this repo uses for
  its own machinery — skill, router, member, plugin, install surface, check —
  and says which words are not synonyms.
- **`docs/adr/README.md`** is the index. Read the ADRs that touch the area you
  are about to work in; each record carries its status, so a superseded one is
  visible before you rely on it.

If a file you expect does not exist, **proceed silently**. Don't flag its
absence and don't suggest creating it upfront.

## Add to the glossary or an ADR

Claude Code sessions in this repo also carry the vendored `domain-modeling`
skill (`.claude/skills/domain-modeling/`). It is not a catalogue skill and no
catalogue skill depends on it; it is a tool the maintainer may use to write a
glossary entry or an ADR. `improve-codebase` carries the glossary/ADR guidance
it needs in its own reference files.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal,
a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't
drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either
you're inventing language the project doesn't use (reconsider) or there's a
real gap worth recording.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than
silently overriding:

> _Contradicts ADR-0010 (Claude gets plugins from the marketplace only) — but
> worth reopening because…_
