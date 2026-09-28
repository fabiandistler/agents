# Architecture Doc

The reader is about to change this system and needs to know what they will
break. Not a tour of every class — the shape, the seams, and the reasoning that
is invisible in the code.

## Skeleton

```markdown
# <System> Architecture

## Context and goals
## High-level design
## Key decisions and trade-offs
## Data flow
## Integration points
## Known weaknesses
```

## Section notes

**Context and goals.** What the system is for, the constraints it was built
under (scale, latency, compliance, team size), and explicitly what is out of
scope. Constraints are what make the rest of the design legible.

**High-level design.** The components and their responsibilities, with a
diagram. Keep prose and diagram consistent — every box named in one appears in
the other. For the diagram notation itself (context, container, and component
views, and when to draw which), use the `c4-modeling` skill; this document just
holds the result. One diagram per level of zoom; a single diagram trying to show
everything shows nothing.

**Key decisions and trade-offs.** The alternatives that were rejected and why —
the highest-value and most-often-missing section, because it is the only part
that cannot be recovered by reading the code. Two or three lines each:

> **Outbox table instead of dual writes to Kafka.** Dual writes lose events on
> partial failure; the outbox costs one extra table and a relay process, and
> adds ~200ms of publish latency. Accepted because at-least-once delivery is a
> hard requirement for billing events.

If a decision is significant, contested, or likely to be revisited, it deserves
its own record — use `adr-workflow` and link to it from here rather than
inlining a full ADR.

**Data flow.** Follow one or two representative requests end to end, naming
each hop and what it does. Include the failure path, not only the happy one:
where retries happen, where things are queued, where data can be lost.

**Integration points.** Every external dependency: what it provides, what
happens when it is unavailable, the protocol and contract, and who owns it.
This is the section that decides how bad an incident gets.

**Known weaknesses.** Where the design strains and what would have to change to
fix it. Writing this down keeps the doc credible and gives the next engineer a
starting point instead of a discovery project.

## Failure modes

- **Reads like generated code documentation.** Class-by-class detail with no
  rationale; the code already said that, and better.
- **No rejected alternatives.** The reader cannot tell whether a design is a
  deliberate choice or an accident, so they either fear or ignore it.
- **Diagram and prose disagree** after a refactor — usually because the diagram
  is an image nobody can edit. Prefer text-source diagrams (Mermaid, PlantUML)
  that live in the repo.
- **Failure paths omitted.** Only the happy path is drawn, which is exactly the
  path nobody needed documentation for.
