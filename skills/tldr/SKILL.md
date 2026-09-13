---
name: tldr
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[file | PR | URL | topic — empty means the last message]"
description: Hand back the cliffs of something too long to read now — the few facts needed to decide or act, plus what was cut.
metadata:
  version: "1.0"
---

# TL;DR

Something got too long to hold. Hand back the **cliffs**: the few facts that let
the user decide or act, and an honest line about what those facts leave out.

Cliffs, not a **telegram**. A telegram is shorter and just as unusable — it
drops the premises, so only someone who already read the source can parse it.
The cliffs let someone who read nothing hold their own in the conversation.

## What to summarize

| Argument | Target |
|---|---|
| *(none)* | The last assistant message **and the work behind it** — the tool calls, files, and findings it was reporting on. |
| A path | That file or directory. |
| A PR, issue, branch, or diff | The change: what it does, what it breaks, what a reviewer must look at. |
| A URL or attached document | That document. |
| A topic in prose | The part of this session about that topic. |

Read the target in full first. Cliffs assembled from a diff stat, a file
listing, or a page title are a guess wearing a summary's clothes.

When the argument reads two ways — a word that is both a filename and a
topic — resolve it from what the user has been doing and name the reading you
picked in one clause. Answer rather than ask.

## The shape

```markdown
**Bottom line.** [One sentence. What survives if they read nothing else.]

- [Load-bearing fact]
- [Load-bearing fact]
- [3–5, ordered by what the decision turns on, not by source order]

**Your move.** [The decision waiting on them, the next step, or "nothing — FYI".]

**Left out:** [What was cut that could still matter, or "nothing that changes the above".]
```

The shape is the length budget; there is no word count to hit.

## Load-bearing

A fact is **load-bearing** when removing it changes what the user does next.
Load-bearing detail survives verbatim: numbers, versions, paths, identifiers,
error strings, names. Adjectives, transitions, restatements, and the order the
source happened to use are what compression eats.

Three things stay load-bearing however long the source is:

- **Claims, not topics.** "Covers auth, caching, and deploy" is a table of
  contents. Say what it *says*: "auth moves to the gateway, caching is
  unchanged, deploy needs a new secret."
- **The disagreement.** An unresolved thread or two conflicting sources stay two
  positions in the cliffs. Collapsing them into one confident answer is the most
  expensive error this skill can make.
- **The gaps.** "I could not read section 4" and "section 4 does not matter" are
  different sentences; write the true one. Mark inference as inference:
  "(inferred — the doc never says)".

Prose follows the conversation, terms follow the source. The cliffs are written
in the language the chat is in — an English PR summarised into a German thread
comes back German. What stays in the source's own words are the terms
themselves: identifiers, error strings, and a repo's `CONTEXT.md` ubiquitous
language. Translating those, or inventing a cleaner label, makes the reader
translate back.

## When it is a different ask

- **Short, and it still did not land.** The gap is missing premises. Back up and
  re-explain with them.
- **The reasoning is the point** — a trade-off, a review call. Give the shape of
  the argument: both positions and what each turns on.
- **Already short, no core, or a summary just written.** Say that in one line;
  a thinner copy helps nobody.

## Done when

The user could act on the cliffs without opening the source, every bullet
changes what they would do, and every number, path, and name in them was copied
rather than remembered.
