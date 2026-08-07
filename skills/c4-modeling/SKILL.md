---
name: c4-modeling
category: architecture
environments: coding, chat
description: Draft a C4 model of a software system with the user and render it as Mermaid diagrams. Covers Context, Container, Component, Landscape, Dynamic, and Deployment views (not Code / level 4), all derived from one element/relationship table.
compatibility: No dependencies — Mermaid renders natively on GitHub, GitLab, VS Code, and most Markdown tools. Optionally C4-PlantUML for publication-grade output when PlantUML (Java) or a Kroki server is available.
---

# C4 Modeling

The C4 model (Simon Brown, c4model.com) describes a software system at four
zoom levels — **Context, Containers, Components, Code** — using just four
abstractions: **Person**, **Software System**, **Container** (a separately
runnable/deployable unit: an app or a data store — *not* a Docker container),
and **Component** (a cohesive grouping of functionality inside a container,
not separately deployable). This skill drafts that model *with* the user in a
short interview, then renders the agreed diagrams as Mermaid so they display
directly in the repository and in chat.

The one habit that makes C4 diagrams stay consistent: **model first, diagrams
second.** All diagrams are projections of one element/relationship table; you
never edit a diagram directly, you edit the table and re-derive.

## When to use

When someone asks to "draw the architecture", "create a C4 diagram", "make a
context / container / component diagram", "visualize the system (landscape /
deployment)", or wants architecture documentation with diagrams. The model is
elicited interview-style (one question at a time) and reviewed against the
c4model.com notation checklist. Not for inventing the component decomposition
itself (→ logical-component-design) or choosing topology / code organization
(→ architecture-pattern-advisor).

Reference pages:

- [references/c4-best-practices.md](references/c4-best-practices.md) — the
  four abstractions, all six diagram types with audience guidance, notation
  rules, and the full review checklist.
- [references/mermaid-c4-guide.md](references/mermaid-c4-guide.md) — complete
  Mermaid C4 syntax, layout control, known limitations, and the styled
  flowchart fallback.
- [references/c4-plantuml-guide.md](references/c4-plantuml-guide.md) —
  optional C4-PlantUML alternative for publication-grade rendering.
- [assets/context-container-template.md](assets/context-container-template.md)
  — a worked example (model table + Context + Container diagram) to copy from.

## Workflow

Run the five steps in order. Enter wherever the user already is — someone who
arrives with a finished element list only needs steps 3–5.

### 1. Clarify scope and audience

Two questions decide everything downstream, so ask them first (one at a time,
with a recommendation, as in a design interview):

- **What is the system in scope?** One software system per C4 model. If the
  user describes several cooperating systems, that is a System Landscape
  diagram *plus* one model per system they own.
- **Who will read the diagrams?** Non-technical stakeholders → Context (and
  maybe Landscape) only. The team and adjacent teams → add Container. Deep
  onboarding or a gnarly subsystem → add a Component diagram *for that
  container only*. Ops/infra discussions → Deployment. A workflow to explain →
  Dynamic.

Rule of thumb: **Context always, Container almost always, everything else on
demand.** Most systems are well served by two diagrams; do not produce all six
because they exist.

### 2. Elicit the model (interactive)

Interview in model order, one question at a time, offering a best guess the
user can correct — never a questionnaire dump. If the answer is discoverable
from the codebase (deps, deployment configs, README), look it up instead of
asking.

1. **People and external systems** — who uses it, what does it talk to
   (identity provider, payment gateway, email service, upstream/downstream
   systems)?
2. **The system itself** — one-sentence purpose statement.
3. **Containers** — the separately deployable/runnable pieces: web app, SPA,
   mobile app, API, background worker, database, message broker, file store.
   Push back on containers that are really components (not deployable alone).
4. **Components** — only for containers picked in step 1; the major structural
   building blocks behind interfaces. If the user is *designing* this
   decomposition rather than describing an existing one, hand off to
   `logical-component-design` and resume here with its component table.
5. **Relationships** — for every line: who calls whom, *why* (purpose, not
   "uses"), and over what technology (JSON/HTTPS, gRPC, SQL, AMQP…).

Capture the result as the **model table** — the single source of truth every
diagram is derived from:

```
| ID | Element | Type | Technology | Description |
|----|---------|------|------------|-------------|
| customer | Customer | Person | — | Buys products via the web shop |
| shop | Web Shop | Software System (in scope) | — | Lets customers browse and order |
| spa | Storefront | Container | React | Browsing and checkout UI |
| ... |

| From | To | Purpose | Technology |
|------|----|---------|------------|
| customer | spa | Browses catalog, places orders | HTTPS |
| ... |
```

Show the table, get agreement, *then* draw. Renames and additions happen in
the table first and propagate to every diagram.

### 3. Derive the diagrams (Mermaid)

For each level agreed in step 1, write a Mermaid diagram from the model table
— syntax and templates in
[references/mermaid-c4-guide.md](references/mermaid-c4-guide.md):

- Prefer the dedicated C4 syntax (`C4Context`, `C4Container`, `C4Component`,
  `C4Dynamic`, `C4Deployment`) — it enforces C4 notation for free.
- When it fights you (it is experimental: coarse layout, weak nesting), fall
  back to a styled `flowchart` using the C4 color/shape conventions from the
  reference. A clean flowchart beats a mangled C4 layout.
- Filter, don't dump: a diagram shows the elements *of its level* plus their
  direct neighbors. More than ~20 boxes means the level is overloaded — split
  the diagram (e.g. one Component diagram per container) rather than shrink
  the font.

Show each diagram to the user and iterate; the table is updated with whatever
the iteration changes.

### 4. Embed the result

Put the diagrams where they will be read and kept current — typically
`docs/architecture/` as Markdown with the model table at the top and the
Mermaid blocks below (GitHub renders them inline). Add a line telling future
editors to change the table first. If the user needs publication-grade visuals
(slides, print, wiki without Mermaid), map the same model to C4-PlantUML via
[references/c4-plantuml-guide.md](references/c4-plantuml-guide.md) — the model
table makes this a mechanical translation.

If architectural decisions surfaced during drafting ("why is search its own
container?"), suggest recording them with `adr-workflow` rather than burying
the rationale in a diagram caption.

### 5. Review against the checklist

Before calling it done, run the notation review (full checklist in
[references/c4-best-practices.md](references/c4-best-practices.md)). Minimum
bar for every diagram:

- **Title** stating diagram type and scope ("System Context diagram — Web Shop").
- Every **element**: name + type + one-line description. No naked boxes.
- Every **relationship**: labeled with its purpose, single-headed arrow in the
  primary direction. No unlabeled or double-headed lines.
- **Technology** stated on containers, components, and non-obvious relationships.
- **No unexplained acronyms**; the diagram must stand alone without a narrator.
- **Consistency** across diagrams: same element ⇒ same name, same color/shape.

## Common mistakes

- **Container ≠ Docker container.** A C4 container is anything separately
  runnable/deployable — a database is a container, a "UserService class" is not.
- **Drawing before modeling.** Diagrams edited directly drift apart on the
  first rename; keep the table authoritative.
- **One mega-diagram.** Mixing levels (people next to classes) or exceeding
  ~20 elements; zoom is the point of C4 — split by level and by container.
- **"Uses" arrows.** Unlabeled or purpose-free relationships carry no
  information; say *what for* and *how*.
- **Drawing level 4 (Code).** Class diagrams go stale immediately; if truly
  needed, generate them from code on demand instead of hand-drawing.
- **Producing all six diagram types reflexively.** Match diagrams to audience;
  two good diagrams beat six unmaintained ones.

## Source

Simon Brown, the C4 model — [c4model.com](https://c4model.com): abstractions,
diagram types, notation recommendations, and the diagram review checklist.
