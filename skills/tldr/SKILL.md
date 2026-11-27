---
name: tldr
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[file | PR | URL | topic — empty means the last message]"
description: Compressing something too long to read into the few facts needed to decide or act, read instead of the source — the last message and the work behind it, or a named file, PR, document, or thread.
metadata:
  version: "1.4"
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
**Your move.** [The decision waiting on them, or the next step. Bold, first line.]

**Why.** [One sentence: where things stand, so the move makes sense.]

- [Only if the decision turns on it: the options, a deadline, two positions]
```

**Lead with the decision.** The user usually opens a TL;DR to learn what they
have to decide or do; everything else is detail they can read in the source.
Put the move on the first line so it is visible without reading further.
When nothing waits on the user, lead with **Bottom line.** instead and write
"FYI — nothing to decide" in the second line.

**Budget: about 50 words.** The user asked for a TL;DR because the source was
too long; when they want detail, they read the source. The budget scales with
the number of open decisions, not with the length of the source: a 400-line
runbook with one next step gets zero bullets, not one bullet per section.
Default to zero bullets. Add one only when the user would decide wrongly
without it — the options to choose between, a deadline, a cost, or two
conflicting positions. Each bullet is one line.

Source (a 40-message thread, excerpt):

```markdown
Mara: gateway migration ships Friday, I own the rollout.
Luis: rate limiting is untested, keep it out of this PR.
Mara: agreed, rate limiting waits; `GATEWAY_JWT_KEY` must exist first.
```

Summary:

```markdown
**Your move.** Create `GATEWAY_JWT_KEY` in staging and prod before Friday.

**Why.** The gateway migration is mergeable once the secret exists; Mara ships
it Friday, rate limiting follows later.
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
  different sentences; write the true one, but only when the gap could change
  the decision. Mark inference with "(inferred)".

## Plain on first read

The user did not read the source. Make the summary understandable in one pass
without relying on premises from it:

- The "Why" line gives the one piece of context the move needs, in words a
  reader who skipped the source understands.
- Short sentences in the active voice, one thought each.
- One word, one meaning: name the same thing the same way every time.

Write the summary in the language of the conversation. Keep source identifiers,
error strings, and the terms from the repo's `GLOSSARY.md` verbatim. When
there are several glossaries, use `GLOSSARY-MAP.md` to find the right one.
Translating those, or inventing a cleaner label, makes the reader translate
back.

## Before sending

Run two passes over the draft:

1. **Cut.** For each bullet ask: would the user decide differently without it?
   If not, delete it. Delete bullets that restate the first two lines,
   setup steps the source spells out, background the user already
   knows from the session, and "also mentioned" items. Shorten what is left
   to one line.
2. **Source.** Point each remaining bullet at its source line or passage. A
   bullet with no source goes out or goes marked "(inferred)".

Send only the summary — no preamble ("Here is the TL;DR"), no closing offer
to expand. The user can ask for more.
