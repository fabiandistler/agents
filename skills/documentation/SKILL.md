---
name: documentation
category: communication
environments: coding, chat
description: Producing technical documentation for a named reader — README, API reference, runbook, architecture doc, or onboarding guide. Covers per-type skeletons, audience targeting, and keeping docs current instead of stale.
---

# Technical Documentation

Documentation fails for one of two reasons: it was written for nobody in
particular, or it was true once. This skill fixes both — name the reader before
drafting, and say out loud where the doc will rot.

## When to use

- "Write docs for X", "document this", "create a README", "write a runbook",
  "onboarding guide", "document the API".
- A module, service, or endpoint exists and has no prose entry point.
- Existing docs are being revised, split, or merged.
- A postmortem action item is "write the runbook".

Do **not** use for:

- **Decision records** — a doc whose subject is *why we chose X over Y* is an
  ADR. Use `adr-workflow`.
- **Architecture diagrams** — for the notation itself (context/container/
  component views) use `c4-modeling`; this skill only says where a diagram goes
  in the surrounding document.
- **Rules files for coding agents** (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) —
  those are distilled constraints, not documentation, and out of scope here.
- **The shape of an explanatory passage** — when a section has to explain a
  concept, `problem-first-explanation` governs its structure (problem before
  solution). It composes with this skill rather than replacing it.

## Workflow

### 1. Name the reader and the job

Write one sentence before anything else:

> **[Who]** opens this to **[accomplish what]**, already knowing **[what]**.

Examples: *"A backend engineer new to the team opens this to get the service
running locally, already knowing Docker but nothing about our auth setup."* —
*"An on-call engineer at 3am opens this to restart a wedged consumer, knowing
production access but not this service."*

If the sentence cannot be written from what you know, ask the user. Do not
guess: nearly every documentation failure downstream is this sentence being
skipped. The reader's prior knowledge sets what you may assume; the job sets
what you may leave out.

### 2. Pick the document type

| The reader's job | Type | Reference page |
|---|---|---|
| Decide whether to use this, then get it running | README | `references/readme.md` |
| Call this service correctly from their own code | API reference | `references/api-reference.md` |
| Execute a known operational procedure under pressure | Runbook | `references/runbook.md` |
| Understand how the system fits together before changing it | Architecture doc | `references/architecture-doc.md` |
| Become productive in an unfamiliar codebase or team | Onboarding guide | `references/onboarding-guide.md` |

One document, one job. If two rows apply, write two documents and link them —
a README that also tries to be an architecture doc serves neither reader.

### 3. Draft from the skeleton

Open the one reference page for the chosen type and follow its section
skeleton. While drafting:

- **Read the code, don't paraphrase it.** Ports, env var names, endpoint
  paths, flag names, and default values get copied out of the source, not
  recalled. Cite the file you took them from when it isn't obvious.
- **No placeholders where a real value exists.** `<your-api-key>` is fine;
  `<your-service-name>` in a repo with exactly one service is laziness.
- **Every command must be runnable as written**, in order, from a stated
  starting state. Run them if you can.
- **Cut every section you have nothing real to put in.** An empty
  "Troubleshooting" heading is a promise the doc breaks.

### 4. Currency check

Before finishing, state in one short block — to the user, or as a comment in
the doc's source where the project's conventions allow — what will make this
doc wrong, and what would catch it:

- Which values will drift (versions, endpoints, env vars, owners, screenshots).
- What keeps them honest: a doctest, a CI check that greps the README's
  commands, a link to the generated reference instead of a hand-copied table.
- Who owns the doc, if the project tracks that.

A doc with no rot story is a doc that will silently become misinformation.

## Principles

Upstream's five, each with the tell that you violated it:

1. **Write for the reader.** *Tell:* you cannot say who would be annoyed if a
   section were deleted.
2. **Start with the most useful information.** *Tell:* the first thing the
   reader needs is below the fold, under history, badges, or motivation.
3. **Show, don't tell.** *Tell:* a paragraph describes what a three-line code
   block would have shown exactly.
4. **Keep it current.** *Tell:* you copied a value that lives somewhere else in
   the repo and nothing will notice when the two diverge.
5. **Link, don't duplicate.** *Tell:* the same instructions now exist in two
   files, and only one of them will get updated.

## Reference pages

Open only the page for the type you are writing.

- `references/readme.md` — what/why, five-minute quick start, configuration,
  usage, contributing.
- `references/api-reference.md` — endpoints, auth, errors, pagination, rate
  limits, SDK examples.
- `references/runbook.md` — trigger, prerequisites, procedure, verification,
  rollback, escalation.
- `references/architecture-doc.md` — context and goals, design, trade-offs,
  data flow, integration points.
- `references/onboarding-guide.md` — setup, system map, first tasks, who to ask.
