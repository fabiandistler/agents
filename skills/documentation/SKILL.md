---
name: documentation
category: communication
environments: coding, chat
description: Writing or fixing technical docs for a named reader — README, tutorial, how-to, API reference, docstrings, runbook, or package docs. Covers per-type skeletons, audience targeting, and keeping docs current instead of stale.
---

# Technical Documentation

Documentation fails for one of two reasons: it was written for nobody in
particular, or it was true once. This skill fixes both — name the reader before
drafting, and say out loud where the doc will rot.

## When to use

- "Write docs for X", "document this", "create a README", "write a runbook",
  "onboarding guide", "document the API", "add roxygen docs to this package",
  "document these docstrings".
- A module, service, or endpoint exists and has no prose entry point.
- Existing docs are being revised, split, or merged.
- A postmortem action item is "write the runbook".

Do **not** use for:

- **Decision records** — a doc whose subject is *why we chose X over Y* is an
  ADR. Use the `architecture` skill (`adr-workflow`).
- **Architecture diagrams** — for the notation itself (context/container/
  component views) use the `architecture` skill (`c4-modeling`); this skill only says where a diagram goes
  in the surrounding document.
- **Rules files for coding agents** (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) —
  those are distilled constraints kept short in the repo root; no skill governs
  them, and they stay out of scope here.
- **The shape of an explanatory passage** — when a section has to explain a
  concept, `problem-first-explanation` governs its structure (problem before
  solution). It composes with this skill rather than replacing it.
- **Status updates for outside readers** — a weekly status, launch
  announcement, or escalation is `stakeholder-update`, not a document.
- **Self-contained HTML deliverables** — a comparison, timeline, or
  interactive page the reader keeps or shares is `html-artifacts`.

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

| The reader's job | Type | Diátaxis | Reference page |
|---|---|---|---|
| Decide whether to use this, then get it running | README | Reference | `references/readme.md` |
| Call this service correctly from their own code | HTTP API reference | Reference | `references/api-reference.md` |
| Call this library's functions from their own code | Package reference | Reference | `references/package-docs.md` |
| Execute a known operational procedure under pressure | Runbook | How-to | `references/runbook.md` |
| Learn by doing, step by step | Tutorial | Tutorial | Inline in step 4 |
| Solve one specific task | How-to guide | How-to | Inline in step 4 |
| Understand how the system fits together before changing it | Architecture doc | Explanation | `references/architecture-doc.md` |
| Become productive in an unfamiliar codebase or team | Onboarding guide | Tutorial | `references/onboarding-guide.md` |

One document, one job. If two rows apply, write two documents and link them —
a README that also tries to be an architecture doc serves neither reader.

### 3. Revise what exists before drafting

When revising rather than starting fresh: audit each section against the
reader sentence from step 1, split by job when two table rows apply, and
replace copied values with links to their source of truth.

### 4. Draft from the skeleton

Open the one reference page for the chosen type and follow its section
skeleton. Tutorials and how-to guides use no reference page: a tutorial is
prerequisites, ordered steps with a visible check after each, and what to do
next; a how-to is the problem, the solution steps, and the variants.
While drafting:

- **Read the code, don't paraphrase it.** Ports, env var names, endpoint
  paths, flag names, and default values get copied out of the source, not
  recalled. Cite the file you took them from when it isn't obvious.
- **No placeholders where a real value exists.** `<your-api-key>` is fine;
  `<your-service-name>` in a repo with exactly one service is laziness.
- **Every command must be runnable as written**, in order, from a stated
  starting state. Run them if you can.
- **Cut every section you have nothing real to put in.** An empty
  "Troubleshooting" heading is a promise the doc breaks.

### 5. Currency check

Before finishing, state in one short block — to the user, or as a comment in
the doc's source where the project's conventions allow — what will make this
doc wrong, and what would catch it:

- Which values will drift (versions, endpoints, env vars, owners, screenshots).
- What keeps them honest: a doctest, a CI check that greps the README's
  commands, a link to the generated reference instead of a hand-copied table.
  Default checks: lychee for links, Vale with the Google package for prose,
  doctests or R CMD check for runnable examples, Sphinx linkcheck for built sites.
- Who owns the doc, if the project tracks that.

A doc with no rot story is a doc that will silently become misinformation.

### 6. Cold-reader test

Run this when the draft is for readers outside the current session. You have
the whole conversation in your head, and the reader does not. So test the doc
on a reader who has only the doc.

If you can start subagents, write 5–10 questions the named reader from step 1
would bring. Give a fresh subagent only the doc and one question, with no
conversation context. Then do one pass over the answers: what was ambiguous,
what prior knowledge the doc assumed, and what contradicts itself. Fix the doc
and run the test again until it turns up no new gap. If you cannot start
subagents, give the user the questions to try with the doc in a fresh chat.

## When agents read your docs

Keep the Markdown source plain with stable headings, generate the `llms.txt`
index with the site tool rather than hand-writing one, and never put content
only in images. If a site generator is chosen, prefer Zensical — Material for
MkDocs reaches end of life in November 2026.

## Principles

Five checks, each with the tell that you violated it:

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
- `references/api-reference.md` — HTTP endpoints, auth, errors, pagination,
  rate limits, SDK examples.
- `references/package-docs.md` — exported functions, parameters, return
  values, reference index, runnable examples.
- `references/runbook.md` — trigger, prerequisites, procedure, verification,
  rollback, escalation.
- `references/architecture-doc.md` — context and goals, design, trade-offs,
  data flow, integration points.
- `references/onboarding-guide.md` — setup, system map, first tasks, who to ask.
