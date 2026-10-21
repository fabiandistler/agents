---
name: improve-codebase
category: refactoring
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires git and a browser to view the HTML report. Writes only to the OS temp directory, plus the repo's GLOSSARY.md and ADRs when the user agrees.
description: Scan a codebase for deepening opportunities, present them as a visual HTML report with before/after diagrams, then interview the user round by round about the candidate they pick. Use when reviewing a repository's architecture.
metadata:
  version: "1.0"
---

# Improve Codebase

Surface architectural friction and propose **deepening opportunities**:
refactors that turn shallow modules into deep ones. The aim is testability and
navigability for both people and agents.

Forked from Matt Pocock's `improve-codebase-architecture` (mattpocock/skills at
commit `49dd158`, MIT; see `UPSTREAM-LICENSE`) and rewritten so it needs no
other skill installed.

## When to use

- The user asks for an architecture review of a repository, or for where
  deepening a module would pay off.
- The user names a subsystem or pain point and wants refactor candidates for
  it, with a decision on one of them.

Not for: measuring coupling or cohesion as numbers, choosing a system topology,
or a routine single-function refactor.

## Vocabulary

Read `references/design-vocabulary.md` before exploring. It defines the
architecture terms (**module**, **interface**, **implementation**, **depth**,
**seam**, **adapter**, **leverage**, **locality**) and the principles this
command applies: the deletion test, "the interface is the test surface", and
"one adapter means a hypothetical seam, two adapters mean a real one". Use those
terms exactly in every suggestion; do not drift into "component", "service",
"API", or "boundary".

The project's own domain language in `GLOSSARY.md` names the good seams, and
the ADRs in `docs/adr/` record decisions this command does not re-litigate.

## Process

### 1. Scope

Deepening a module pays off by making future changes to it easier, so put
extra weight on the parts of the codebase that change. Decide *where* to look
before looking:

- If the user named a direction (a module, a subsystem, a pain point), take it
  and skip the ranking below.
- Otherwise, follow the `refactoring` skill's workflow: rank files by git
  churn with its bundled script, restricted to the source directories (one
  `--include` per directory, for example `--include 'src/**'`), then list the
  co-changers of each top hit in the same window. Drop non-code paths from the
  co-change lists: changelogs (`NEWS.md`, `CHANGELOG*`), generated docs
  (`man/`), lock files, plan and PRD files. Treat each group of co-changing
  files as one candidate area, not several. Its "when the ranking lies" cases
  (young repo, bulk reformat, shallow clone) apply here too.
- If the ranking is flat, or the repo is younger than the window, rerun over
  the full history. If it is still flat, scope by file size and the user's
  direction instead.
- A bulk commit (a sweep touching many files) is noise for the ranking, but can
  be evidence for a candidate: the same mechanical edit repeated across many
  modules points at a rule with no single home.

Keep the churn and co-change counts: they become evidence on the cards.

Read `GLOSSARY.md` and any ADRs covering the area before going further.

### 2. Explore

Walk the codebase in the scoped area. Where the agent can start a subagent,
hand the walk to one with the scope and the vocabulary file, so the main
context receives findings rather than file dumps; otherwise walk it directly.
Do not follow rigid heuristics; explore and note where friction shows up:

- Where does understanding one concept require bouncing between many small
  modules?
- Where are modules **shallow**, with an interface nearly as complex as the
  implementation?
- Where have pure functions been extracted only for testability, while the real
  bugs hide in how they are called (no **locality**)?
- Where do tightly coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything suspected of being shallow: would
deleting it concentrate complexity, or just move it? "Concentrates" is the
signal to look for.

Back the two structural suspicions with `coupling-cohesion`, read via the
`architecture` router (`members/coupling-cohesion/SKILL.md`):

- **"This module is shallow" or "these parts are only colocated"**: Mode A
  (cohesion, LCOM) on that module, alongside the deletion test. Run it on the
  suspected modules only, not the whole tree.
- **"This leaks across the seam"**: Mode C (balanced coupling) on that one
  dependency, naming the module behind the seam and its caller.
- **Not Mode B.** Codebase-wide coupling metrics and zones answer "how
  brittle is the whole codebase", not "where does deepening pay off"; they
  would be noise in the report.

If the agent can start subagents, give Mode A to `cohesion-analyst` and
Mode C to `coupling-analyst`, telling the latter to assess the one named
dependency with Mode C and not to run its codebase-wide metrics. Each returns
its verdict and evidence lines, never file bodies. Without those subagents,
follow the member file's Mode A or C workflow directly and run its bundled
scripts (`scripts/lcom.py`, `scripts/balance_check.py`, relative to the
`coupling-cohesion` skill directory) inline, writing any input JSON to the OS
temp directory.

Mode A's LCOM for R is a heuristic: one-line functions, long signatures,
handler closures and package-global state defined in another file skew it.
Read the code before a group count from it supports a split or shallow claim.

Translate the result before it reaches a card: `coupling-cohesion` speaks of
boundaries, integration strength and distance; the report speaks only the
vocabulary file's terms. `references/evidence-translation.md` maps one to the
other. A "leave" verdict drops the finding unless other evidence carries it.

Record evidence for every finding as `path:line` or a metric value (churn
count, group count, sharing level), so the user can verify it. A finding with
neither does not go in the report.

### 3. Present candidates as an HTML report

Write one self-contained HTML file to the OS temp directory, so nothing lands
in the repo. Resolve the temp directory from `$TMPDIR`, falling back to `/tmp`
(`%TEMP%` on Windows), and write
`<tmpdir>/architecture-review-<timestamp>.html` so each run gets a fresh file.
Open it for the user (`xdg-open` on Linux, `open` on macOS, `start` on
Windows) and give the absolute path. Without a browser or opener (a headless
session), print the path instead.

For each candidate, render a card with:

- **Files**: the files and modules involved.
- **Evidence**: one line per finding, each with `path:line` or a metric value
  as the instrument printed it.
- **Problem**: why the current shape causes friction.
- **Solution**: in plain English, what would change.
- **Benefits**: in terms of locality and leverage, and how tests would improve.
- **Before / after diagram**: side by side, showing the shallowness and the
  deepening.
- **Recommendation strength**: `Strong`, `Worth exploring`, or `Speculative`,
  as a badge.

End the report with a **Top recommendation** section: the one candidate to
tackle first, and why.

Use `GLOSSARY.md` terms for the domain and the vocabulary file's terms for the
architecture. If the glossary defines "Order", write "the Order intake module",
not "the FooBarHandler" and not "the Order service".

**ADR conflicts**: surface a candidate that contradicts an existing ADR only
when the friction is real enough to warrant reopening it. Mark it in the card
(for example, "contradicts ADR-0007, but worth reopening because ..."). Do not
list every theoretical refactor an ADR forbids.

`references/html-report.md` has the scaffold, the diagram patterns, and the
style and tone rules. Read it before writing the file.

Do not propose interfaces yet. Once the file is written, ask the user which
candidate they want to explore.

### 4. Interview on the chosen candidate

Once the user picks a candidate, interview them until both sides share one
understanding of the deepened module. Treat the open questions as a **design
tree**: every decision branches into the decisions that depend on it. The
branches to cover are the constraints, the dependencies (classified by the
categories in the vocabulary file), the shape of the deepened module, what sits
behind the seam, and which tests survive.

Work in **rounds**:

1. The **frontier** is every decision whose prerequisites are already settled.
   Ask the whole frontier in one round. Number each question and give a
   recommended answer, worded so that "yes" accepts it.
2. Wait for the answers. Settled decisions push the frontier outward; recompute
   it and ask the next round. A question that depends on another question still
   open in the same round belongs to a later round.
3. Facts are the agent's job, decisions are the user's. Look up anything the
   code, history, or tools can answer instead of asking. A lookup still running
   blocks only the questions downstream of it; ask the rest of the frontier now.
4. The interview ends when the frontier is empty: every branch visited, nothing
   silently assumed. Do not act on the result until the user confirms the shared
   understanding.

If the user wants to compare alternative interfaces for the deepened module,
use the "design it twice" procedure in the vocabulary file.

### 5. Keep the glossary and ADRs current

Write these side effects as decisions crystallise during the interview, not in
a batch at the end. Create files lazily, only when there is something to write.

- **A deepened module named after a concept missing from `GLOSSARY.md`**: add
  the term once the user agrees. Create the file if it does not exist.
- **A fuzzy term sharpened in the conversation**: update `GLOSSARY.md` as
  soon as the user confirms the sharpened meaning. When the user uses a term that conflicts with the glossary, say so
  immediately and ask which meaning holds.
- **The user rejects the candidate with a load-bearing reason**: offer an ADR,
  framed as "Record this as an ADR so future architecture reviews do not
  re-suggest it?" Offer only when a future reviewer would need the reason to
  avoid re-suggesting the same thing; skip ephemeral ("not worth it right now")
  and self-evident reasons.

`GLOSSARY.md` holds domain terms only, never implementation details. Offer an
ADR only when the decision is hard to reverse, surprising without context, and
the result of a real trade-off. `references/glossary-and-adr.md` has both
formats and the numbering rule.

### 6. Lock the seam into CI

Once the user confirms the deepened module's shape, point at locking its seam
so it does not erode back: `fitness-functions`, read via the `architecture`
router (`members/fitness-functions/SKILL.md`), designs a CI check for it, for
example an import rule that lets callers reach the module only through its
interface. Offer it; do not write the check unless the user asks.
