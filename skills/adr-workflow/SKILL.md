---
name: adr-workflow
category: architecture
environments: coding
description: Establish, draft, supersede, and maintain Architecture Decision Records (ADRs) in software repositories.
---

# ADR Workflow

Use this skill when a repository needs a durable record of important architectural choices.

## When to use

Whenever the user mentions ADRs, architecture decisions, decision logs, technical choices with long-term impact, or wants to set up a repo workflow for documenting why important decisions were made — even if they don't explicitly say "ADR".

## Core principles

- Keep ADRs close to the code, usually under `docs/adr/`, unless the repository already uses a better convention.
- Prefer one ADR per decision.
- Treat accepted ADRs as immutable history. If the decision changes, write a new ADR that supersedes the old one; never renumber old ADRs after the fact.
- Write for future readers who were not in the room: record the decision and its consequences, not a meeting transcript.
- Capture the trade-offs honestly, including the downsides of the chosen option and the alternatives considered.
- Keep an index or README over the records instead of letting unindexed ADRs accumulate.

## What to check first

Before proposing a new ADR setup or drafting a record, inspect the repository for:

- Existing docs folders and naming patterns
- Any current decision-record convention such as `adr/`, `decisions/`, or `docs/architecture/decisions/`
- Tool markers such as `.adr-dir` (adr-tools) or `.log4brains.yml` (log4brains); when present, keep that tool's layout and numbering
- Markdown style and tone used elsewhere in the repo
- Existing ADRs that should be indexed instead of duplicated

If the repo already has a convention, follow it unless there is a strong reason to change it.

## Recommended repo setup

If the repository does not already have a decision-record home, propose this default structure:

- `docs/adr/`
- `docs/adr/README.md` or `docs/adr/index.md` as the entry point
- `docs/adr/template.md` as a starter template (no sequence number — the template is not a decision record)
- `docs/adr/0001-short-title.md` for individual records

Use zero-padded numbers so records stay sortable as the list grows.

## When an ADR is worth writing

Write an ADR if the choice is hard to reverse, has cross-team impact, or is likely to be re-litigated; otherwise a commit message or PR description is enough.

## ADR template

Default to this MADR-aligned minimal template when drafting a new record:

```markdown
# NNNN Title

Status: Proposed | Accepted | Rejected | Deprecated | Superseded by NNNN

Date:

Deciders:

## Context and problem
What problem are we solving? What constraints matter?

## Decision drivers
- Why these factors mattered
- What trade-offs shaped the choice

## Considered options
- Option A
- Option B
- Option C

## Decision outcome
Chosen: X, because ...

## Consequences
- Good outcomes
- Bad trade-offs
- Revisit when ...
```

If the repo already uses Nygard (Status/Context/Decision/Consequences) or full MADR, match it instead.

If the team wants a lighter format, keep the same essentials: title, status, context, decision outcome, and consequences.

## Workflow for adopting ADRs in a repo

1. Identify the decision-record location and naming convention that best matches the repository.
2. Add a short README or index that explains what ADRs are and when to use them.
3. Add a template file so new ADRs start from the same structure.
4. Define the review flow: work in a dedicated branch, open a PR, and discuss the trade-offs. Include the ADR in the same PR as the change for small or agent-driven repos; open a separate ADR PR first when the decision needs wider review.
5. Link older ADRs from the index instead of creating duplicate records.
6. Backfill only the 3-5 decisions people keep re-asking about, as Accepted with their original date.
7. Add one line to the agent instruction file: read the relevant ADRs in `docs/adr/` before architectural changes.

## Workflow for drafting a new ADR

When the user wants a specific decision recorded, draft the ADR in repo-appropriate language and structure it like this:

1. State the decision in plain language.
2. Capture the context, constraints, and decision drivers.
3. List realistic alternatives, not strawmen.
4. Record the chosen option and why it won.
5. Document the consequences honestly, including the drawbacks.
6. Assign the next sequential number only after the ADR is ready to commit. If another open PR took the same number, renumber the later-merging ADR before merge, never after.
7. Open a PR for review before merging.

## Workflow for changing a decision

- Create a new ADR that references the earlier one and mark the old ADR as `Superseded` or `Deprecated`.
- Explain what changed in the environment or understanding that justified the new decision.

## Keeping ADRs useful to agents

Before changing code in an area, list `docs/adr/` and read the Accepted ADRs whose title or scope matches the change.

- If the change contradicts an Accepted ADR, stop and propose a superseding ADR instead of proceeding.
- Add optional frontmatter for retrieval: `status`, `date`, `scope` (paths or modules), and `tags`.
- Record a "revisit when" trigger under Consequences so future work knows when to reconsider the decision.

## Response style

If the repository already uses another documentation language, match it; otherwise default to English.
