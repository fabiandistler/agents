---
name: guideline-distillation
category: workflow
environments: coding
description: Distill messy source documents (style guides, ADRs, RFCs, wikis, linter configs, review checklists, onboarding docs) into lean, machine-actionable convention files such as CONVENTIONS.md, AGENTS.md, or CLAUDE.md fragments for coding agents; use whenever a document needs to become project rules an agent can load as context, or a rules file feels bloated with generic advice a competent coding model already knows. The defining move is subtraction — most of a source document is generic best practice or language defaults the model already follows, and the job is to find the small residue that is non-obvious, project-specific, and consequential.
metadata:
  version: "1.0"
---

# Guideline Distillation

Coding agents don't need to be told how to write a for-loop, name a variable in
camelCase, or add a try/except — they already know. What they can't know is
that *this* team forbids `data.table` in favor of `dplyr`, requires every PR to
update a CHANGELOG, or names migration files with a UTC timestamp prefix. This
skill turns a messy source document into a short rules file that contains only
the second kind of thing.

The output is consumed by an LLM, not browsed by a human. Every rule in the
file competes for attention with the agent's actual task, and every generic
sentence dilutes the signal. A file of 12 sharp, falsifiable rules is strictly
better than one with 40 padded ones — even if the 40-rule version is more
"complete." Bias toward cutting.

## Core principle: subtraction

The test for whether something belongs in the output is never "does this
sound like good advice" — it is:

> **Would a competent coding model do this correctly without being told?**

If yes, cut it, no matter how true or well-written it is. If no — because a
reasonable default would differ, or the team made a deliberate, non-obvious
choice — keep it. This is a judgment about the *model's default behavior*,
not about the importance of the underlying practice. "Use tabs for
indentation" sounds too basic to bother stating, but most models default to
spaces, so it survives; "handle errors" sounds substantive but is exactly what
every model already does, so it goes. Judge every candidate against the
model's likely unprompted output, not against how it reads on the page.

## The four-pass method

Work each source document through four passes. Don't skip straight to
rewriting — the filter (pass 2) is the actual job; passes 1, 3, and 4 exist to
feed it and package its output.

### Pass 1 — Inventory

Read the full document. List every candidate directive: anything phrased as
must/should/never/always, or describing a naming scheme, a required
structure, a tool choice, a forbidden pattern, or a required side effect.
Don't filter yet — over-collect here so pass 2 has real material to cut.

### Pass 2 — The triviality filter

This is the core of the skill. For each candidate, run it against the discard
table first, then the keep tests. Discard anything that matches a discard
row, unless a keep test overrides it.

**Discard if the candidate is:**

| Category | Example of what to cut |
|---|---|
| Universal best practice | "Write readable code", "handle errors", "use meaningful names", "avoid magic numbers", "write tests", "comment complex logic" |
| Language/framework default behavior | "Use `const` over `var`", "prefer list comprehensions", "use async/await for I/O" |
| Obvious from the toolchain | Anything a linter/formatter already enforces deterministically (e.g. "use 2 spaces" when a Prettier config is committed) — unless the agent must know it to avoid fighting the formatter |
| Pure rationale or history | "We chose Postgres because…", motivational statements, deprecated rules |

**Keep only rules that are:**

- **Non-obvious** — a reasonable default would differ, or there's a genuine
  fork the model couldn't guess. ("Prefer composition over inheritance" is too
  generic to keep. "Never use class-based components, even for error
  boundaries — use `react-error-boundary`" is a real, keepable fork.)
- **Project/team-specific** — names, paths, tool choices, version
  constraints, ordering, required side effects (changelog updates, codegen,
  regenerated lockfiles).
- **Counter-intuitive or a deliberate correction of the default** — the team
  overrides what the model would otherwise produce.
- **Consequential** — getting it wrong produces a rejected PR, a broken
  build, or a silent bug.

When unsure whether something is "obvious," keep it only if it is also
project-specific; otherwise cut. When a candidate references an existing
linter/formatter config (`.eslintrc`, `pyproject.toml`, `renv.lock`, etc.),
check whether that config already enforces it deterministically — if so, cut
the rule from the output (the tool handles it); if the config only *implies*
a convention without enforcing it, the rule may still be worth stating.

### Pass 3 — Rewrite as agent-actionable rules

Transform each kept item into the output format below: imperative voice,
falsifiable, one atomic directive per line.

### Pass 4 — Deduplicate & group

Merge overlapping rules across sources. Cluster by domain (e.g. Naming,
Dependencies, Testing, Git, Architecture). Order clusters by how often an
agent will actually hit them in normal work, most-frequent first. If a single
cluster exceeds roughly 15 rules, the filter in pass 2 was too loose — rerun
it on that cluster rather than shipping a bloated section.

## Output format

```markdown
# <Scope> Conventions

> Non-obvious, project-specific rules. Generic best practices are assumed and omitted.

## <Domain Cluster>

- **<imperative rule>.** <one-clause why, only if non-obvious.>
  - ✅ `concrete correct example`
  - ❌ `concrete wrong example`   ← include only when the wrong form is the model's likely default
```

Rules for writing the rules themselves:

- Start every bullet with a verb ("Use", "Never", "Prefix", "Run … before
  …"). Never "You should consider…".
- One atomic directive per bullet — split compound rules into separate lines.
- Make each rule falsifiable: a reviewer must be able to point at a piece of
  code and say pass or fail.
- Add a code example only when the prose alone is ambiguous. Examples cost
  tokens; spend them deliberately.
- Mark a `❌` example with `← likely-default` whenever it corrects a behavior
  the model would otherwise produce unprompted. **This is the single
  highest-value annotation in the file** — it tells the agent not just what
  the rule is but which of its own habits to override.
- Omit rationale paragraphs. If the "why" matters for the agent's judgment in
  an edge case, compress it to one clause; otherwise leave it out entirely.

Three short real examples of this output style, at increasing rule density:

- *Data-Intensive Systems design rules* (from Kleppmann) — mostly single-rule
  clusters like "Never implement a read-modify-write cycle in app code on
  shared data… Use the DB's atomic operation… or an explicit lock", each
  tagged with a book chapter reference instead of prose rationale.
- *Tidyverse API design conventions* (from Wickham) — denser clusters, e.g.
  "Use a string enum, not `TRUE`/`FALSE`, to select between strategies — even
  with only two choices. A boolean can't grow to a third strategy," followed
  by the `❌ cancel_on_error = TRUE   ← likely-default` counter-example.
- *data.table conventions* — the densest of the three, because the source
  corrects habits from a specific competing tool (dplyr/base-R), e.g. "Return
  multiple columns with `.()`, never `c()`. `c()` in `j` concatenates into
  one vector," with both a ✅ and a ❌ line.

Study whichever is closest to your source domain for tone and density before
writing; do not exceed roughly 15 rules per cluster.

## Safety rules

These override the general bias toward cutting — treat them as hard
constraints on the process, not style preferences:

- **Never fabricate a rule or infer a team convention that isn't in the
  source.** Absence of a rule is information. Do not fill a gap with generic
  advice just to make a cluster look complete.
- **Flag contradictions between sources instead of silently resolving them.**
  Use an inline marker such as `<!-- conflict: doc A says X, doc B says Y —
  needs human decision -->` and leave the decision to a person.
- **Never copy secrets, internal URLs, credentials, or personal data** from
  the source into the output file.
- **Keep a security-relevant rule even when it looks obvious.** ("Never log
  request bodies" reads like common sense, but the cost of an agent guessing
  wrong here is high.) Security rules are exempt from the triviality filter's
  bias toward cutting.
- **Preserve the source's intent precisely when compressing a rule.** Check
  that the compressed version cannot be misread as permitting the behavior
  the source forbids.

## Communication conventions

- Precede the output with a one-line summary that makes the filter's
  aggressiveness visible: `Extracted N rules from <source>; discarded M as
  generic/trivial.`
- If something the reader might expect to see was cut, say so briefly:
  `Cut: "write tests", "use type hints" (generic).`
- If a whole source yields nothing project-specific, say so plainly instead
  of padding the output: *"No project-specific rules found in `<doc>` —
  content is generic best practice already known to coding models. Nothing
  extracted."*
- Ask at most one clarifying question, and only when either (a) the target
  file/format is unspecified and there's no reasonable default, or (b) a
  source rule is genuinely ambiguous in a way that changes the directive.
  Otherwise proceed and flag assumptions inline with `<!-- assumption: … -->`.

## Worked micro-examples

**Filtering a style guide.** Source: "Code should be clean and
well-organized. We use Black for formatting with line length 100. Avoid
deeply nested conditionals." → Cut "clean and well-organized" (generic). Cut
the Black mention if `pyproject.toml` already enforces it. Keep the line
length, because the model's default assumption is Black's own default (88),
so stating 100 avoids the agent fighting the config:

```markdown
- **Set Black line length to 100, not the default 88.** ← likely-default mismatch
```

Cut "avoid deeply nested conditionals" (generic).

**Correcting a model default.** Source: "All async DB calls go through the
`repository` layer; never call the ORM session directly from a route
handler." → Keep — this is project architecture the model cannot guess:

```markdown
- **Never call the ORM session directly from a route handler.** Route → service → repository only.
  - ❌ `db.session.query(User)` inside a route   ← likely-default
  - ✅ `user_repo.get(id)`
```

**A required side effect.** Source: "Every schema change must add a
migration AND update `docs/schema.md`." → Keep only the second clause; the
migration itself is expected, the doc update is the part a model omits:

```markdown
- **After any schema change, update `docs/schema.md` in the same PR** — not just the migration.
```

**The "obvious but wrong-default" trap.** A rule can read as too basic to
state yet still correct a real default. "Use tabs for indentation" sounds
trivial, but most models default to spaces in most languages — so it stays.
The test is never "does this sound basic," it's "would the model do this
correctly unprompted."

## Common mistakes

- **Keeping rationale instead of the rule.** A paragraph explaining *why* a
  team chose Postgres is history, not a directive — cut it even if it's
  interesting.
- **Padding a near-empty extraction to look thorough.** If a document is 90%
  generic, say so and ship a short file. A three-rule output from an 8-page
  doc is a correct result, not a failure.
- **Dropping security rules because they "sound obvious."** The triviality
  filter has one exception, and this is it.
- **Compressing a rule until it stops being falsifiable.** If a reviewer
  couldn't point at code and call it pass/fail, rewrite it, don't ship it.
- **Letting a cluster grow past ~15 rules.** That's a signal the filter was
  too loose on that domain, not that the domain deserves more rules.
