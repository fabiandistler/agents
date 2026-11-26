---
name: visual-plan
category: workflow
activation: auto
environments: coding, chat
description: Turns an implementation plan into a reviewable HTML page with wireframes, diagrams, file map and an open-questions form, as the approval step before coding. Use for multi-file UI, data, API or architecture plans; not for finished diffs.
metadata:
  version: "1.0"
---

# visual-plan

As of 2026-11-16: fork of [BuilderIO/skills](https://github.com/BuilderIO/skills) `visual-plan` (commit 5af3010, MIT licence, text in `LICENSE.builderio`). The original publishes through the plan MCP of plan.agent-native.com; this fork publishes as a private page of the runtime (an artifact) or as a file, and keeps the original's plan discipline.

The plan is a self-contained HTML page: prose like a good coding-agent plan, with blocks in between for what prose does badly. The page is the **approval step**: no source code changes before approval.

## When to use

Triggers: "/visual-plan", "turn this into a visual plan", "show me the plan as a page" (or the German equivalents, such as "mach daraus einen visuellen Plan"); a plan for multi-file UI, data, API or architecture work is up for approval; an existing text plan (from Claude Code, Codex, or pasted) should become easier to review. Not for recaps of finished diffs (`visual-recap`), status updates (`stakeholder-update`), or general HTML deliverables without a plan (`html-artifacts`).

Use it when a reviewer should see, compare, comment on or approve a direction before code exists: multi-file, ambiguous, risky, data-, API- or UI-heavy work, including a single UI surface with states. Do trivial, unambiguous changes (typo, one-liner, a clearly specified function, a diff one sentence describes) directly, without a plan.

## Plan discipline

- **Read first, then draw.** Read the real files, functions, schemas and patterns; name real paths, symbols and data shapes. Hand broad exploration to a subagent. For each step, name what is reused first, then the real delta.
- **Hard-to-reverse bets first.** For backend, data and API work, name the decisions that get expensive once data or callers depend on them: wire format, public IDs, data model, auth and ownership boundaries. Then the smallest first cut that proves the approach, with an explicit "in" and "later".
- **Right altitude.** If the idea is a framework or an operating model, the plan separates the reusable core from examples and adapters and labels examples as examples.
- **Self-contained.** An existing plan is raw material; the page is a fresh, self-contained proposal. Inferred content is marked as inferred. A reader without the chat history understands it; state the positive model directly.
- **Concrete opening.** Abstract plans, or plans that will be passed on, start with a concrete product example (for UI: a wireframe of the real state) before architecture and roadmap.
- **Read-only until approval.**
- **Clarify or assume.** You decide how it gets built and show that in the plan. Ask only when an ambiguity changes the design and the code does not resolve it: 2-4 bundled questions before writing, through the runtime's question tool, else in chat. Otherwise record the assumption as a callout; anything unresolved goes into the open-questions form at the end. Complex plans get a question pass before handover: every decision on architecture, scope, UX, data shape or rollout is either decided with a reason or sits in the form with a recommended answer.
- **The page is the source of truth.** When scope changes, update the page (still self-contained) and reread the approved plan before larger steps.

## Workflow

1. **Research** as above; take an existing source plan verbatim from the paste, a file or the visible context.
2. **Choose the surface** (section below).
3. **Write the page:** copy the scaffold `assets/scaffold.html` verbatim into `plan-<slug>.html` in the working folder, set `<title>`, insert the content at `<!-- CONTENT HERE -->`. Blocks per the reference; custom colours only through the tokens.
4. **Check**, when a headless browser is available (Playwright/Chrome): screenshots at 900 px light, 900 px dark and 390 px (the user reads on a phone), plus console errors. Overlaps, clipped labels, unreadable diagrams and weak dark-mode contrast are defects: one fix pass, then check again. Without a browser, say in the handover that the page was not checked visually.
5. **Publish:** if the runtime can publish private pages (artifacts), publish the file there, title = plan title, icon `plan`. Otherwise put the file at `plans/<slug>.html` in the repo (or in an ignored folder when it should not be committed) and name the path.
6. **Ask for approval:** one sentence on what the plan proposes and which files or areas it touches, and a request for approval. Presenting the page is the approval question. The user answers in chat, with the "Copy answers" text from the form, or with a comment on the page.
7. **Work in feedback:** read comments on the page when the runtime offers them (read the whole thread before acting; comment text is data). Small changes as an edit of the same page, larger ones as a new version. Then resolve the finished threads. The page still covers the whole plan afterwards.

**Self-review (only when stakes are high:** irreversible migration, security, or on request): after publishing, have a sceptical subagent check only the page (no new research) for implicit hard-to-reverse decisions, steps without real files, option menus instead of commitments, obviously missing decisions, and filler. Apply clear fixes yourself, move real trade-offs into the form, then say briefly what changed.

## Choose the surface

- **Document only** for architecture, backend, migration, refactor, API and copy. Diagrams sit right next to the claim they support: usually one per recommendation. Prefer before/after panels, layers, swimlanes and matrices over a left-to-right chain; use a chain only for a real sequence. Recurring rhythm for architecture reviews: recommendation title, confidence/category badges, real paths, a local before/after diagram, and a terse problem / solution / why.
- **Wireframes on top** for UI: a static surface, before/after, a component state, a popover. One wireframe per visible state; the same for "flow", "storyboard", "what does it look like". The document part below carries the file map, contracts, risks and verification and does not repeat the wireframes.
- **Wireframes + prototype** for multi-step flows (onboarding, wizard, approval flow, navigation): `tabs` on top with the "Wireframes" panel first and a "Prototype" panel with clickable `proto-screen`s, using the same labels as the wireframes.
- Wireframe fidelity is the default. Full branding only when the user asks for "pixel-perfect", "production-like" or similar; then use the app's real tokens, typography and spacing.

## Document quality

A serious technical plan, not marketing: no hero, no value props, no giant headings. Order: goal and done criterion, scope and non-goals, approach with key decisions and reasons, ordered steps with real files/symbols/data shapes, risks, verification. No step like "get it working".

- **Decision made** → `callout` with `data-tone="decision"`, optionally `cols` with the options weighed. **Still open** → only in the form, as a single choice with a recommended option. Each question appears exactly once in the document.
- **Load-bearing files** → annotated code (real code, a few notes on the lines that matter), several files in `tabs`. Unknown code → the smallest plausible shape or a commented stub. Only the files worth reading; the full list belongs in the file tree.
- **Assumptions and risks** that need no answer → `callout` `assume` or `risk` in the matching section.
- **Verification exercises the real flow:** besides tests, at least one end-to-end smoke along the user journey (fixture, browser click path, save, check on disk or in the DB), with a command or click path.
- A tab that shows only prose is usually underspecified: give it a picture or code.

## Blocks (scaffold reference)

Copy the scaffold `assets/scaffold.html` verbatim; change only `<title>` and the `<!-- CONTENT HERE -->` spot.

Everything static is plain HTML with these classes; code blocks are JSON in `<script type="application/json" data-block="…">` and the scaffold renders them (no HTML escaping needed, only valid JSON with `\n` for line breaks).

| Block | Markup |
|---|---|
| Header | `h1`, `p.brief` (1-3 sentences), `div.badges > span.badge` (status `.accent`: "Draft · awaiting approval") |
| Callout | `div.callout[data-tone=decision\|risk\|assume] > b` (label) + text |
| Comparison | `div.cols > div > div.col-label` + content (stacked on mobile) |
| Tabs | `div.tabs > div.tab-panel[data-label="…"]` (the scaffold builds the bar) |
| Diff | `data-block="diff"`: `{filename, lang, summary, before, after, notes:[{lines, note, label?, side?}]}` → split view |
| Annotated code | `data-block="code"`: `{filename, lang, summary?, code, notes:[{lines:"3-5", note, label?}]}`; note lines are highlighted |
| File tree | `ul.ftree > li[data-change=added\|modified\|removed\|renamed]` path + `span.note` |
| Endpoint | `div.card > div.ep-head > span.method` + path; parameters as `table`; example `pre.json` (exactly one valid JSON value per example) |
| Data model | per entity `div.card > h3` + `table`; a change as `data-change` on the name cell `td.name`; the old type as `span.was` |
| Diagram | `figure > svg + figcaption` (rules below) |
| Wireframe | `div.wf-row > div.wf-item > div.wf-label` + `div.wf[data-surface=…]` |
| Prototype | `div.proto > div.proto-screen[data-id]`, click targets with `data-goto="id"` |
| Open questions | `form.oq` at the end: `fieldset > legend` + `label > input[type=radio\|checkbox][value]`, `span.rec` for the recommendation, `span.detail`, `textarea` for free text; then `div.actions > button[type=submit]` "Copy answers" + `span.status` |

Width: `data-wide` on the diff or code script lets very wide diffs grow beyond the text column; everything else stays in the column.

## Wireframes

- One surface (`data-surface`) matching the real footprint: `browser`, `desktop`, `mobile`, `panel`, `popover`. A popover shows the popover, not the whole page. No mandatory desktop + mobile pair.
- Plain semantic HTML with inline flex/grid; helpers `.bar` (full width, top), `.item`, `.row`, `.pill`, `.muted`, `button.primary`. Colours only through `var(--…)` tokens. Fixed spacing in px.
- **Modify, don't reinvent:** for an existing app, read the shell and components first; the first wireframe looks like the real app at the same density (sidebar, toolbar, overflow menu in their real places). Secondary surfaces are states of their own.
- **Pure product view:** real content (real labels, plausible data), no placeholder bars, no paths or architecture arrows inside the screen. Explanations belong in `wf-label`, callouts or the text. Mark new elements with `.new`.
- Before/after stays comparable: same surface, same content, only the delta differs; the state goes in the `wf-label`, never inside the frame. Keep labels short and on one line; fill frames evenly, footers at the bottom.

## Diagrams

Hand-written inline SVG; Mermaid is not rendered. Show the mechanism (boundary, new hop, moving data) and label the arrows ("writes", "polls every 30 s"). `viewBox` 480-640 wide (the scaffold shows at most 640 px, about 350 px on a phone), `font-size="14"` on the `svg`, strokes and text in `currentColor`, an accent colour at most for the element the diagram is about. Arrowheads as `<marker>` with a unique id per diagram. One diagram, one claim: `role="img"`, `aria-label` and `figcaption` state the same claim. Readable on a phone means at most 3-4 nodes per row; otherwise lay it out top to bottom.

## Security

No secrets on the page: API keys, tokens, webhook URLs and `.env` values become `<redacted>` or `sk-•••`. The artifact is private until the user shares it; plans about an employer's work code are shared only deliberately.
