---
name: tldr
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
argument-hint: "[file | PR | URL | topic — empty means the last message]"
description: Compress something long into the few facts the reader needs to decide or act, plus what was cut — the last message and the work behind it by default, or a named file, PR, document, or thread.
metadata:
  version: "1.0"
---

# TL;DR

The user typed this because something got too long to hold. They are **not**
asking for fewer words — they are asking for the few facts that let them decide
or act, and an honest note about what those facts leave out.

Name the state, not the word count: *"I lost the thread of this, hand me the
cliffs."* An agent that hears "be brief" writes telegrams. A telegram is a
shorter text that is just as unusable.

## When to use

The source is long and the user needs its substance now — a wall of tool output,
a thirty-message thread, a PR they did not follow, a spec, a paper, a file they
are about to touch.

Not this skill when:

- **It was short but did not land.** Then the problem is missing premises, not
  length. Back up and re-explain with the context the user was missing; do not
  compress further.
- **The user needs the reasoning itself.** A verdict without the argument is
  useless when the argument is the point (a design trade-off, a review call).
  Summarize the *shape* of the argument instead of deleting it.
- **Nothing was read yet.** Read the source in full first. A summary assembled
  from a file listing, a diff stat, or a page title is a guess wearing a
  summary's clothes.

## What to summarize

| Argument | Target |
|---|---|
| *(none)* | The last assistant message **and the work behind it** — the tool calls, files, and findings it was reporting on. |
| A path | That file or directory, read in full. |
| A PR, issue, branch, or diff | The change: what it does, what it breaks, what a reviewer must look at. |
| A URL or attached document | That document. |
| A topic in prose | Only the part of this session that is about that topic. |

If the argument is ambiguous — say a word that is both a filename and a topic —
pick the reading that fits what the user has been doing and say which one you
picked in one clause. Do not stop to ask.

## The cliffs

Fixed shape. Fill every part; do not add parts.

```markdown
**Bottom line.** [One sentence. What survives if they read nothing else.]

- [Load-bearing fact]
- [Load-bearing fact]
- [3–5 max, ordered by what matters to the decision, not by source order]

**Your move.** [The decision waiting on them, the next step, or "nothing — FYI".]

**Left out:** [What was cut that could still matter, or "nothing that changes the above".]
```

Default ceiling: about 150 words. If the source genuinely will not compress that
far without dropping a fact the decision turns on, say in one clause what forces
the extra length, then go over. The ceiling serves the decision, not the reverse.

## Rules

- **Keep what carries the decision.** A shorter summary that hides the one number
  the decision turns on is a failed summary. Compress adjectives, transitions,
  and restatements — never numbers, names, paths, error strings, versions, or
  identifiers.
- **Claims, not topics.** "Covers auth, caching, and deploy" is a table of
  contents. Say what the source *says*: "auth moves to the gateway; caching is
  unchanged; deploy needs a new secret."
- **Add nothing.** No inference presented as content, no filled-in gaps. If you
  inferred something, mark it: "(inferred — the doc never says)".
- **Separate uncertainty from compression.** "I could not read section 4" is not
  the same as "section 4 does not matter". Say which one it is.
- **Keep their vocabulary.** Reuse the terms the source and the user already use
  — a repo's `CONTEXT.md` ubiquitous language if there is one. Inventing a
  cleaner label forces a translation step onto the reader.
- **Preserve disagreement.** If a thread ended unresolved or two sources
  conflict, the summary says so. Collapsing it into one confident position is
  the most expensive error this skill can make.
- **Refuse gracefully.** If the source is already short, has no core, or is a
  summary you just wrote, say that in one line instead of producing a thinner
  copy.

## Failure modes

| ✗ | Why it fails |
|---|---|
| Telegram | Shorter, but only parseable by someone who already read the source. |
| Table of contents | Lists what is discussed, not what is true. |
| Buried verdict | Bottom line arrives last, after the reader has already given up. |
| Laundered uncertainty | Hedges dropped, so a maybe reads as a fact. |
| Flattened conflict | Two positions become one; the open question disappears. |
| Lost identifiers | "the failing test" instead of its name — the reader cannot act. |

## Self-check

Before sending, one pass:

- [ ] Could the user act on this without opening the source?
- [ ] Does every bullet change what they would do?
- [ ] Is every number, path, and name in it copied, not remembered?
- [ ] Is "Left out" honest — would they be annoyed to discover what is in it?

If the answer to the first is no, the summary is too short, not too long.
