---
name: visual-recap
category: workflow
activation: auto
environments: coding, chat
description: Turns finished work (PR, branch, commit, diff, session changes) into a visual HTML recap with wireframes, diagrams, schema and API changes, file tree and annotated diffs. Use when a reviewer should see the shape before the line diff.
metadata:
  version: "1.0"
---

# visual-recap

As of 2026-11-16: fork of [BuilderIO/skills](https://github.com/BuilderIO/skills) `visual-recap` (commit 5af3010, MIT licence, text in `LICENSE.builderio`). The original publishes through the plan MCP of plan.agent-native.com; this fork publishes as a private page of the runtime (an artifact) or as a file.

A recap is a plan in reverse: it describes a change that exists, one altitude above the line review. Schema, API, file and architecture changes become the same blocks as in a plan. The reviewer sees the shape first, then the load-bearing lines.

## When to use

Triggers: "/visual-recap", "recap this PR", "show me what the branch changed", "summarize the changes visually" (or the German equivalents, such as "recap diesen PR"). Not for plans before coding (`visual-plan`), review against standards or a spec, or status updates for stakeholders (`stakeholder-update`).

Use it for large, multi-file changes or changes that touch schema, API contracts, architecture or UI. Small, single or obvious diffs are faster to review as a diff: say so briefly and build no recap.

## Workflow

1. **Determine the scope.** A given reference (PR, branch, commit, range) or, in a running session, the session's **whole unit of work**: the original implementation, later fixes, UI touch-ups, tests, changesets, skill and docs changes. Unrelated changes that existed before stay out. If the scope cannot be derived, state the assumption or ask briefly.
2. **Read the diff in one pass** (`git diff --stat`, then the files; for a PR, read the PR diff: Use the GitHub MCP tools if the session has them; otherwise `gh api repos/<owner>/<repo>/pulls/<n> -H 'Accept: application/vnd.github.diff'`) and keep notes as you go: an inventory of changed routes, components, popovers/dialogs, role and access states, empty and error states, schema, API and shared abstractions. Afterwards work from the notes without rereading the whole diff.
3. **Load the `visual-plan` skill** and take from it: the scaffold (its `assets/scaffold.html`), the blocks, the wireframe and diagram rules, and checking and publishing (its steps 4-5). Those parts apply here unchanged.
4. **Write the page to `recap-<slug>.html`** following the canon and mapping below. Every inventory item is either represented by a block or deliberately left out (tiny, redundant, not visible).
5. **Check and publish** as in visual-plan; badge status "Recap", icon `review`.
6. **Hand over:** one sentence on the core of the change. Feedback in chat or as a comment on the page flows back into the code (comment → agent → diff); afterwards update the recap so it still covers the whole unit of work plus the correction.

## Canon and budgets

Top to bottom:

1. **UI headline:** wireframes first when the diff changes rendered UI.
2. **Outcome narrative:** 1-3 paragraphs on what changed and why.
3. **Data model / endpoint** for schema and contract changes, before/after in `cols`.
4. **File tree** with `data-change` per file.
5. **`## Key changes`:** exactly one `tabs` block with diffs or annotated code, one tab per key file (label = path, or a short name with a folder hint).

Budgets, which are also the cost ceiling: 3-8 key-change tabs; under about 150 lines per tab, summarizing the rest of a long file; title ≤ 70 characters; brief 1-3 sentences.

**Lean but substantial.** No prose block that only says the recap is a help, how many files changed or which ref it comes from: the title, brief and file tree carry that. Prose only for the goal, a real compatibility risk, a visible decision or a grounded review note. A large diff still needs a file tree and key-change diffs; one wireframe plus one sentence for 40 files sends the reviewer back to the raw diff.

Good: a 25-file auth change with before/after wireframes of the login surface, two paragraphs of narrative, the session table's data model with change flags, the endpoint of the new refresh route, a file tree and five focused key-change tabs, each with a summary and a few notes.

## Mapping diff → block

- **Schema/migration** → data model of the resulting entities; `data-change` (added/modified/removed/renamed) per field, a changed type with `span.was`. This is the headline; an SQL diff only when the exact statement matters.
- **API/route/action** → endpoint in its post-change state; changed parameters/responses with `data-change` and `span.was`; a wholly new or removed route with `data-change` in the header, a removed one also explained in prose. Every example is exactly one valid JSON value; several message shapes (success vs. error, frame types) each get their own labelled example. Several endpoints go one below the other, except for a real before/after contract.
- **Compatibility-critical** → a short `callout` `risk` next to the block: which field, endpoint or behaviour, and whether it is breaking, risky or not breaking.
- **Meaningful code hunk** → a split diff with the real `before`/`after`, `filename`, `lang` and a one-sentence `summary` (what and why). Key files get a few notes on the lines that matter (after-side line numbers; `side:"before"` for removed lines).
- **New file / large new block with no meaningful before** → annotated code instead of a one-sided diff.
- **Files added/removed/renamed** → file tree with `data-change` and a short note.
- **Architecture or data-flow shift** → a diagram as before/after panels, layers or swimlanes. Show UI controls as a wireframe, not as a diagram.

## UI changes need wireframes

If the diff changes layout, density, visible state, controls, navigation, menus, dialogs or design tokens, the recap contains wireframes. Derive the coverage from the diff:

- **Entry point:** where the change appears (header, list row, toolbar, menu trigger).
- **Interaction surface:** what opens or changes (popover, dialog, tab, sheet, inline editor, toast).
- **Result:** the target state (page, read-only, empty, error, loading, no-access, saved state).
- **Roles:** for permission changes, owner/admin vs. viewer as a pair or a matrix.

For UI-heavy PRs, show all three stages entry → surface → result. Choose the smallest clear form: before/after for a direct comparison; after only for purely additive changes; a state sequence for flows. Small surfaces get the matching `data-surface`. Wireframes rely on component names and labels visible in the diff; mark inferred content as "inferred" in the `wf-label`.

## True by construction

Diff, data model, endpoint and file tree are built mechanically from the real changed lines: real paths, fields, methods, before/after text. Only the prose is written freely: the why, the narrative, the risk assessment. What the diff does not contain stays out; inferred content is marked as inferred. A confidently wrong recap leads the reviewer to skip exactly the line it summarized wrongly.

## Security

Secrets from the diff (API keys, tokens, webhook URLs, signing secrets, `.env` values) appear in no block, note or caption: use `<redacted>` or `sk-•••`. A recap exposes unpublished schema and internal endpoints; treat it like the source code. The artifact is private until the user shares it.
