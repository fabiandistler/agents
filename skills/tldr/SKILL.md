---
name: tldr
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[file | PR | URL | topic — empty means the last message]"
description: Compressing something too long to read into the few facts needed to decide or act, read instead of the source — the last message and the work behind it, or a named file, PR, document, or thread.
metadata:
  version: "1.3"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# TL;DR

## What to summarize

| Argument | Target |
|---|---|
| *(none)* | The last assistant message **and the work behind it** — the tool calls, files, and findings it was reporting on. |
| A path | That file or directory. |
| A PR, issue, branch, or diff | The change: what it does, what it breaks, what a reviewer must look at. |
| A URL or attached document | That document. |
| A topic in prose | The part of this session about that topic. |

Read the target in full first.

When the argument reads two ways — a word that is both a filename and a
topic — resolve it from what the user has been doing and name the reading you
picked in one clause. Answer rather than ask.

## The shape

```markdown
**Bottom line.** [One sentence. What survives if they read nothing else.]

**Your move.** [The decision waiting on them, the next step, or "nothing — FYI".]

- [Load-bearing fact]
- [Load-bearing fact]
- [3–5, ordered by what the decision turns on, not by source order]
```

Source:

```markdown
Mara: gateway migration ships Friday, I own the rollout.
Luis: rate limiting is untested, keep it out of this PR.
Mara: agreed, rate limiting waits; `GATEWAY_JWT_KEY` must exist first.
```

Summary:

```markdown
**Bottom line.** Mergeable once the secret exists; rate-limit timing is settled.

**Your move.** Create `GATEWAY_JWT_KEY`, then confirm Friday with Mara.

- Auth checks move to the gateway; Mara owns the Friday rollout.
- Deploy fails without `GATEWAY_JWT_KEY` in staging and prod.
- Rate limiting ships next week (inferred — agreed as follow-up, no date given).
```

## Load-bearing

A fact is **load-bearing** when removing it changes what the user does next.
Load-bearing detail survives verbatim: numbers, versions, paths, identifiers,
error strings, names, owners, deadlines, decisions taken. Adjectives,
transitions, restatements, and the order the source happened to use are what
compression eats.

Three things stay load-bearing however long the source is:

- **Claims, not topics.** "Covers auth, caching, and deploy" is a table of
  contents. Say what it *says*: "auth moves to the gateway, caching is
  unchanged, deploy needs a new secret."
- **The disagreement.** An unresolved thread or two conflicting sources stay two
  positions in the summary. Collapsing them into one confident answer is the most
  expensive error this skill can make.
- **The gaps.** "I could not read section 4" and "section 4 does not matter" are
  different sentences; write the true one. Mark inference as inference:
  "(inferred — the doc never says)".

## Plain on first read

The user did not read the source. Make the summary understandable in one pass
without relying on premises from it:

- Context first: the bottom line says where things stand and why it matters
  before it says what follows.
- Short sentences in the active voice, one thought each.
- One word, one meaning: name the same thing the same way every time.

Write the summary in the language of the conversation. Keep source identifiers,
error strings, and the terms from the repo's `GLOSSARY.md` verbatim. When
there are several glossaries, use `GLOSSARY-MAP.md` to find the right one.
Translating those, or inventing a cleaner label, makes the reader translate
back.

## Before sending

Point each bullet at its source line or passage. A bullet with no source
goes out or goes marked "(inferred)".
