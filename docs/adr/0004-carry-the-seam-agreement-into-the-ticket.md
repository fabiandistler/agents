# ADR-0004: Carry the seam agreement into the ticket

## Status
Accepted (2026-09-13)

## Context

The `mattpocock-skills` build chain is `grill-with-docs → to-spec → to-tickets →
implement`. `implement` is the step that writes code, and its `SKILL.md` is six
lines long. One of them reads:

> Use /tdd where possible, at pre-agreed seams.

A **seam** is the public boundary a module is tested at. `tdd` refuses to write a
test at a seam that has not been agreed. Nothing inside `implement` agrees one —
the skill's own documentation names this as its weakest joint and predicts the
failure exactly: "If it happens nowhere, the precondition never fires and the run
quietly becomes 'just write the code'."

A measurement over 1125 local session transcripts confirms the prediction:

| Query | Hits |
| --- | --- |
| `/implement` invocations | 17, across 17 sessions |
| `/tdd` invocations, any spelling | **0** |
| Skill-tool invocations overall (validity probe) | 413 |

The validity probe matters: the same query shape finds 413 skill invocations
across the corpus, and sibling skills from the same plugin register normally, so
this is not a broken query or a newly installed plugin. By `implement`'s own
stated success criterion — "You can see an actual `/tdd` invocation in the trace"
— 0 of 17 runs met it.

The per-run detail locates the cause in the **handover**, not in the skill:

| Handover passed to `/implement` | Runs | Seam work observed |
| --- | --- | --- |
| Bare issue number (`15`, `142`, `18`, …) | 12 | none, in all twelve |
| `yes` / empty | 3 | none |
| A sentence referring to written issues | 2 | substantial |

Session size does not explain the split: three bare-number sessions of 1.1–1.3 MB
show no seam work, while the two prose runs that do are 1.8 MB and 2.3 MB.

The one run with genuine seam work (`e2730da8`, 59 test files touched, seams
argued explicitly in prose) invoked neither `to-spec` nor `to-tickets`. It read
GitHub issues whose bodies were `to-spec` specs, carrying the spec template's
`## Testing Decisions` section — and inside it, a seam definition in plain words:
"A test drives the public DSL against a fixture project on disk and asserts on
the returned `arch_result`. It never reaches into the parse output …".

That closes the chain. `to-spec` step 2 already agrees seams and confirms them
with the user. Its output is a **spec**. `to-tickets` then breaks the spec into
tickets, and neither of its two templates has a seam field:

- local: `What to build` / `Blocked by` / `Status` / acceptance criteria
- issue: `Parent` / `What to build` / `Acceptance criteria` / `Blocked by`

`implement` consumes tickets, not specs. The seam agreement is therefore made
upstream and dropped at the `to-tickets` boundary. Local usage matches the shape
of the leak: `to-spec` ran twice, `to-tickets` six times, `implement` seventeen
times.

## Decision

Treat the seam agreement as a **field that travels with the ticket**, not as a
precondition re-established inside each run.

1. `/to-spec` runs before implementation, and its seam confirmation is answered
   rather than waved through.
2. Tickets derived from a spec carry the seams they are tested at. A ticket
   without a seam field is not ready for `/implement`.
3. `/implement` is never invoked with a bare issue number. The handover names
   the work, so a planning pass is forced.
4. Each vertical slice ends with two or three lines stating which control-flow
   path changed and why in that order, recorded with the ticket.

Point 4 exists because nothing in the chain owns control flow. `to-spec` covers
architecture and seams; no step covers the order in which things happen, which is
the second thing a reader needs weeks later.

## Considered options

- **A new local command that negotiates seams and writes an artifact.** Rejected
  once the measurement showed the negotiating step already exists as `to-spec`.
  A second command would duplicate it and add another trigger that can fail to
  fire — the exact failure being fixed.
- **Editing the local copy of `implement`.** Rejected: the plugin cache path is
  versioned (`…/1.2.3/…`), so the edit dies at the next update.
- **A wrapper command interleaving grilling with implementation.** Rejected:
  a wrapper whose text asks a skill to invoke another skill is the same
  construction that produced 0 invocations in 17 runs.
- **Changing the commit behaviour of `implement` at the same time.** Deferred.
  It is a real second problem and belongs in its own change.

## Consequences

- Two upstream defects were filed against `mattpocock/skills`: the routing
  measurement for `implement`/`tdd`, and the seam field missing from the
  `to-tickets` templates. If either is fixed upstream, the corresponding local
  rule becomes redundant and should be removed rather than left to drift.
- The rules land in `instructions/55-seam-handover.md`, so they apply to every
  session rather than to whoever remembers them.
- The measurement is one user on one machine, 17 runs. The correlation between
  handover form and seam work is not a causal proof, and a later contradicting
  sample should reopen this decision rather than be explained away.
