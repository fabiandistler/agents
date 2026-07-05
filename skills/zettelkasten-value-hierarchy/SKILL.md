---
name: zettelkasten-value-hierarchy
environments: chat
description: Classify personal knowledge-base notes on an 8-level value hierarchy (Principle > System > Workflow > Automated Tool > Template > Checklist > Tool > Snippet) and run bottom-up or top-down value-generation passes that consolidate low-value notes into higher-value ones. Use whenever a note collection is reviewed for what it is "worth", when deciding whether a note should be promoted or merged, or when the user asks to find synthesis opportunities, generate value, or build a system/workflow/principle note out of existing snippets, tools, or checklists.
compatibility: Tool-agnostic. Assumes a note collection with typed notes and a linking mechanism (wiki-links, tags, or backlinks); adapt the mechanics to whatever note system is in use.
metadata:
  version: "1.0"
---

# Zettelkasten Value Hierarchy

A zettelkasten is not just a store of notes — it can function as a value chain.
Ideas captured as small, low-effort notes can be iteratively combined and
refined into higher-value notes. This skill encodes that value hierarchy and
two workflows for climbing it: **bottom-up** (start from existing low-value
notes and look for what they add up to) and **top-down** (start from a target
high-value note and gather the material to support it).

This originates from one person's personal zettelkasten convention, not a
universal standard. Treat the hierarchy and workflows as a lens to offer, not
a rule to enforce — apply them loosely, and defer to the collection's own
existing conventions where they differ.

## The value hierarchy

Every note can be placed on this ladder, from most to least valuable:

| # | Level | What it is | Why it ranks there |
|---|-------|------------|---------------------|
| 1 | **Principle** | A fundamental way of thinking, universally transferable | Highest transfer; the basis new systems get built on |
| 2 | **System** | A coherent method or framework (e.g. GTD) | Potential to become a product or service |
| 3 | **Workflow** | Concrete steps for a recurring task | Turns a system into something repeatable |
| 4 | **Automated Tool** | Code that replaces a checklist (e.g. a linter) | Removes the need for manual discipline |
| 5 | **Template** | A starting point for a recurring task | Saves setup time, still requires manual work |
| 6 | **Checklist** | Items to tick off | Encodes judgment as steps, but still manual |
| 7 | **Tool** | Helper programs (e.g. `uv`) that speed up work | General-purpose leverage, not specific to one task |
| 8 | **Snippet / Script** | Reusable code fragments, shell aliases | Smallest reusable unit |

Read the table top to bottom as "more general and more transferable" and
bottom to top as "more concrete and more disposable." A principle can spawn
many systems; a snippet is usually a one-off fragment with no further
structure to unpack.

### Using the hierarchy to classify a note

Ask, in order:

1. Is this a way of thinking that would apply even in an unrelated domain? →
   **Principle**.
2. Is this a named, coherent method with multiple interlocking parts? →
   **System**.
3. Is this a fixed sequence of steps for one recurring task? → **Workflow**.
4. Does this run without a human checking boxes (a script, a lint rule, a CI
   check)? → **Automated Tool**.
5. Is this a fill-in-the-blank starting point? → **Template**.
6. Is this a list of things to verify or tick off by hand? → **Checklist**.
7. Is this a general-purpose helper program, not specific to one task? →
   **Tool**.
8. Otherwise: is it a reusable code fragment or alias? → **Snippet/Script**.

## Value generation: two directions

Both workflows share the same goal — synthesize new value at levels 1–3
(Principle, System, Workflow) by drawing on levels 4–8 (Automated Tool,
Template, Checklist, Tool, Snippet) — but they start from opposite ends.

```
Principle ──────┐
System          ├─ target: higher-value notes to create or strengthen
Workflow ───────┘
Automated Tool ─┐
Template        │
Checklist       ├─ source: lower-value notes to consolidate or upgrade
Tool            │
Snippet ────────┘
```

### Bottom-up: from existing low-value notes upward

Start when the note collection has accumulated Automated Tool, Template, or
Checklist notes (or lower) and the question is "what do these add up to?"

1. Survey the low-value notes already in the collection — Automated Tool,
   Template, Checklist, Tool, Snippet.
2. Look for higher-value notes (Principle, System, Workflow) that these
   low-value notes could support or reinforce — either notes that already
   exist and are under-supported, or a plausible new one that several
   low-value notes are secretly circling.
3. Be critical: only propose a synthesis if it genuinely adds value beyond
   restating what the low-value notes already say individually. Not every
   pile of scripts implies a system.
4. Select at most 3–5 of the most promising synthesis opportunities.
5. For each: propose what would be synthesized and confirm before creating
   it.
6. Link the new synthesis note to every contributing note, using link types
   that reflect the relationship (e.g. "supports", "instance of", "derived
   from") rather than a generic link.
7. Update or create structure/hub notes so the new synthesis is discoverable
   from the collection's existing map of notes, not just reachable by luck.

### Top-down: from a target high-value note downward

Start when there's already a candidate Principle, System, or Workflow in mind
(explicit or half-formed) and the question is "what supports this, and what's
missing?"

1. Identify the intended synthesis: the working title and level (Principle,
   System, or Workflow) of the note to build or strengthen.
2. Search the collection for lower-value notes — Snippet, Tool, Checklist
   (and Automated Tool, Template) — that could be combined or upgraded to
   back it.
3. Be critical here too: don't force-fit unrelated snippets into the target
   just to look thorough. A thin but honest synthesis beats a padded one.
4. Cap the pass at 3–5 synthesis opportunities so the work stays reviewable.
5. Propose the synthesis and confirm before creating it.
6. Link the new note to its contributing notes with appropriate link types.
7. Update or create structure/hub notes as needed.

### Shared guardrails

- Propose, then confirm — value generation creates new notes or restructures
  existing ones; don't do this silently.
- Cap each pass at 3–5 synthesis opportunities. This is a curation exercise,
  not a bulk migration.
- A synthesis note without links back to its sources loses the reason it
  exists — always wire the contributing notes to the new note, and the new
  note into the collection's structure/hub layer.
- "No good synthesis found this pass" is a legitimate outcome. Not every
  batch of low-value notes is ready to become a system.

## Why this matters beyond tidiness

The hierarchy gives a note collection a second use besides "reference for
recall": it becomes a value chain where small captured fragments compound
into transferable principles and reusable systems — the kind of asset that
can, in the collection owner's own framing, eventually become a product or
service (this is explicit at the System level, e.g. GTD). Treating notes as
sitting on a ladder rather than a flat pile is what makes that compounding
visible and intentional.

## Related ideas

The originating notes tie this hierarchy to the broader idea that the
zettelkasten method (per Sönke Ahrens) is not limited to academic writing —
it applies to any goal that benefits from developing complex, evolving
strands of thought, such as software design, processes, or systems in
general. The value hierarchy is one concrete way that benefit shows up.
