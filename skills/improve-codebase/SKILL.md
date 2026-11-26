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
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Improve Codebase

Surface architectural friction and propose **deepening opportunities**:
refactors that turn shallow modules into deep ones. The aim is testability and
navigability for both people and agents.

## Vocabulary

Read `references/design-vocabulary.md` before exploring. It defines the
architecture terms (**module**, **interface**, **implementation**, **depth**,
**seam**, **adapter**, **leverage**, **locality**) and the principles this
command applies: the deletion test, "the interface is the test surface", and
"one adapter means a hypothetical seam, two adapters mean a real one". Use those
terms exactly in every suggestion; do not drift into "component", "service",
"API", or "boundary".

Use the project's `GLOSSARY.md` terms for the domain and the design vocabulary
above for the architecture. If the glossary defines "Order", write "the Order
intake module". Read applicable ADRs in `docs/adr/` before reopening a decision.

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
- Which modules are shallow under the definition in the vocabulary?
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

If subagents are available, give the scoped Mode A check to `cohesion-analyst`
and the scoped Mode C check to `coupling-analyst`. Each returns its verdict
and evidence lines without file bodies. Without those subagents,
follow the member file's Mode A or C workflow directly and run its bundled
scripts (`scripts/lcom.py`, `scripts/balance_check.py`, relative to the
`coupling-cohesion` skill directory) inline, writing any input JSON to the OS
temp directory.

Mode A's LCOM for R is a heuristic: one-line functions, long signatures,
handler closures and package-global state defined in another file skew it.
Read the code before a group count from it supports a split or shallow claim.

Before writing the report or interview, use `references/evidence-translation.md`
to express measurements in the design vocabulary while keeping metric values
verbatim. A "leave" verdict drops the finding unless other evidence carries it.

Record evidence for every finding as `path:line` or a metric value (churn
count, group count, sharing level), so the user can verify it. A finding with
neither does not go in the report.

### 3. Present candidates as an HTML report

Write one self-contained HTML file to the OS temp directory as
`<tmpdir>/architecture-review-<timestamp>.html` and open it for the user; in a
headless session, print the absolute path instead.

Before writing, read `references/html-report.md` for the scaffold, diagram and
style guidance. Render each card to its Candidate card specification, including
fields, badge and diagram placement.

End the report with a **Top recommendation** section: the one candidate to
tackle first, and why.

**ADR conflicts**: surface a candidate that contradicts an existing ADR only
when the friction is real enough to warrant reopening it. Mark it in the card
(for example, "contradicts ADR-0007, but worth reopening because ..."). Do not
list every theoretical refactor an ADR forbids.

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

1. The **frontier** contains exactly the decisions whose prerequisites are
   settled. Ask the whole frontier in one round. Number each question and give
   a recommended answer that "yes" accepts.
2. Wait for the answers, recompute the frontier and ask the next round.
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
