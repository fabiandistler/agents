---
name: adr-workflow
description: Establish and maintain Architecture Decision Records (ADRs) in software repositories. Use whenever the user mentions ADRs, architecture decisions, decision logs, technical choices with long-term impact, or wants to set up a repo workflow for documenting why important decisions were made, even if they do not explicitly say "ADR".
compatibility: Works in any software repository. No special dependencies.
---

# ADR Workflow

Use this skill when a repository needs a durable record of important architectural choices. The goal is not to add more documentation for its own sake. The goal is to make the repo explain why key choices exist so future contributors can maintain or revisit them without rediscovering the same debate.

## Core principles

- Keep ADRs close to the code, usually under `docs/adr/`, unless the repository already uses a better convention.
- Prefer one ADR per decision. Small, reversible choices usually do not need an ADR.
- Treat accepted ADRs as immutable history. If the decision changes, write a new ADR that supersedes the old one.
- Write for future readers who were not in the room.
- Capture the trade-offs honestly, including the downsides of the chosen option.

## What to check first

Before proposing a new ADR setup or drafting a record, inspect the repository for:

- Existing docs folders and naming patterns
- Any current decision-record convention such as `adr/`, `decisions/`, or `docs/architecture/decisions/`
- Markdown style and tone used elsewhere in the repo
- Existing ADRs that should be indexed instead of duplicated

If the repo already has a convention, follow it unless there is a strong reason to change it.

## Recommended repo setup

If the repository does not already have a decision-record home, propose this default structure:

- `docs/adr/`
- `docs/adr/README.md` or `docs/adr/index.md` as the entry point
- `docs/adr/0001-template.md` as a starter template
- `docs/adr/0001-short-title.md` for individual records

Use zero-padded numbers so records stay sortable as the list grows.

## When an ADR is worth writing

Use an ADR when the choice has one or more of these traits:

- Long-term maintenance cost
- Cross-team impact
- Security, compliance, or operational consequences
- Hard-to-reverse technical debt
- A likely future disagreement about why the team chose this path

Do not use an ADR for trivial implementation details, local style preferences, or decisions that only matter for a single short-lived task.

## ADR template

Use this structure when drafting a new record:

```markdown
# ADR-0001: Short title

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-000X

## Context
What problem are we solving? What constraints matter?

## Decision
What did we choose?

## Decision drivers
- Why these factors mattered
- What trade-offs shaped the choice

## Considered options
- Option A
- Option B
- Option C

## Consequences
- Positive outcomes
- Negative trade-offs
- Follow-up work or risks

## Notes
Optional links, migration steps, or implementation details
```

If the team wants a lighter format, keep the same essentials: title, status, context, decision, and consequences.

## Workflow for adopting ADRs in a repo

1. Identify the decision-record location and naming convention that best matches the repository.
2. Add a short README or index that explains what ADRs are and when to use them.
3. Add a template file so new ADRs start from the same structure.
4. Define the review flow: work in a dedicated branch, open a PR, discuss the trade-offs, then merge the ADR separately from the implementation when practical.
5. Explain the rule for when an ADR is required and when it is unnecessary.
6. Link older ADRs from the index instead of creating duplicate records.

## Workflow for drafting a new ADR

When the user wants a specific decision recorded, draft the ADR in repo-appropriate language and structure it like this:

1. State the decision in plain language.
2. Capture the context, constraints, and decision drivers.
3. List realistic alternatives, not strawmen.
4. Record the chosen option and why it won.
5. Document the consequences honestly, including the drawbacks.
6. Assign the next sequential number only after the ADR is ready to commit.
7. Open a PR for review before merging.

## Workflow for changing a decision

- Do not rewrite accepted ADRs to hide history.
- Create a new ADR that references the earlier one.
- Mark the old ADR as `Superseded` or `Deprecated`.
- Explain what changed in the environment or understanding that justified the new decision.

## Response style

When the user asks for guidance, return a practical adoption plan instead of abstract process advice. When the user asks for an ADR, draft the record directly with repo-appropriate naming and structure. If the repository already uses another documentation language, match it; otherwise default to English.

## Common pitfalls to avoid

- Writing ADRs for trivial implementation details
- Treating the ADR as a meeting transcript
- Omitting consequences or alternatives
- Renumbering old ADRs after the fact
- Editing old accepted ADRs instead of superseding them
- Letting the repository have ADRs with no index or README
