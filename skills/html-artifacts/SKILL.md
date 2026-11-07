---
name: html-artifacts
category: communication
environments: coding, chat
description: Produces a self-contained HTML file for deliverables the reader will keep, share, or manipulate; not for ordinary answers. Use when spatial layout, comparison, or interaction carries meaning.
---

# HTML Artifacts

## When to use

Default to a one-line offer and stay in markdown unless the user asked for HTML or the output is clearly a deliverable they will keep, share, or manipulate. Reach for HTML only when that deliverable test holds and one of the following is true.

- **Comparison.** Two or more options/approaches/designs the reader needs to weigh against each other. Side-by-side beats stacked.
- **Spatial information.** Diffs, call graphs, module maps, flowcharts, timelines, before/after — anything where position carries meaning.
- **Interaction matters.** Animations, easing curves, parameter tuning, state transitions — things the reader needs to *feel*, not read about.
- **Reference material.** A document the reader will navigate non-linearly: tabs, collapsible sections, glossary in the margin, jump links.
- **Color or hierarchy carries meaning.** Severity tags, status colors, syntax highlighting, design tokens.
- **One-off editor.** The reader needs to manipulate a thing (drag tickets, toggle flags, tune a prompt) and round-trip the result back into a prompt or a commit.
- **The reader will share it.** A spec going to leadership, a PR writeup going to reviewers, a status report going to a team. Readers often engage more with an HTML page than a markdown file.

The request rarely says "HTML" or "artifact." It says: doc, writeup, plan, spec, report, explainer, comparison, review, PR description, mockup, diagram, flowchart, deck, slides, status update, post-mortem, incident report, playground — or a one-off editor for triaging, reordering, or tuning something. A bare verb alone (explain, summarize, compare, explore options, brainstorm) without a keep/share/manipulate deliverable stays in markdown.

Trigger examples — HTML: "compare these three options side by side for the leadership review"; "turn this incident timeline into a shareable post-mortem"; "build a board to triage these tickets and copy the result back". Markdown: "summarize what's in this file"; "explain this error in three bullets".

## This skill picks the format, not the content

It decides how a deliverable is rendered. What goes *in* the deliverable is often another skill's job, and the two compose — run the other skill for the substance, then render its output as HTML instead of markdown:

- Weekly/monthly leadership status, launch announcements, risk escalations → `stakeholder-update`.
- Standup prep or a status update assembled from recent repo activity → suggest the user run `repo-status`, then render its Yesterday / Today / Blockers output as HTML.
- The internal structure of a technical explanation (problem before solution) → `problem-first-explanation`.
- Review findings on a diff or PR, and a PR description → whichever review or PR-writing skill is installed (in this repo's cloud sessions: `code-review` and `pr`) supplies the substance; render it with `references/code-review-and-pr.md`. The PR body posted on the forge stays markdown; the HTML page is the shareable companion for reviewers.

## When to stay in markdown

Markdown still wins for:

- Short conversational replies inside chat.
- Code-only outputs (a function, a config block, a one-liner).
- Terminal/command-flavored answers ("run this, then that").
- Quick three-bullet summaries the reader will scan once and discard.
- Files that need to be diffed in version control regularly. HTML diffs are noisy. If the artifact will live in git and be reviewed in PRs over time, markdown is friendlier — though even then, *generating* an HTML view alongside is often worth it for review.

If the artifact is going to be edited by hand by a human afterward, markdown is also friendlier. But increasingly artifacts are edited by re-prompting the agent, which removes that advantage.

## Universal rules for every HTML artifact

Every artifact this skill produces must satisfy all of these:

1. **Single self-contained `.html` file.** No build step, no bundler, no `npm install`. CSS goes in a `<style>` tag, JS goes in a `<script>` tag, images are inline SVG or data URIs.
2. **Works offline, inline-first.** No required network calls at view time: ship CSS, JS, SVG, and fonts inline in the single file with no external CDN dependencies. If a library is needed while drafting, pin the exact version with `integrity` and `crossorigin` from cdnjs or the jsDelivr npm endpoint, then inline it before delivery. Avoid third-party web fonts in shared files; use system stacks.
3. **Mobile responsive.** Include `<meta name="viewport" content="width=device-width, initial-scale=1">` and a layout that survives a narrow viewport. The reader may open it on a phone.
4. **Real layout, not stacked headers.** If the content is a comparison, lay it out in columns. If it's a timeline, draw a timeline. If it's a diff, render a diff. Don't translate markdown structure 1:1 into HTML — that's wasted effort.
5. **Readable on its own.** Title at the top, a one-paragraph TL;DR or framing sentence right below, then the substance. The reader should know what they're looking at within five seconds.
6. **Tasteful by default.** A neutral but considered design: legible serif or sans body, comfortable line length, generous spacing, restrained color, dark-mode-friendly if cheap. Resist the default-AI aesthetic of "everything is a card with a gradient." See `references/matching-your-style.md` for document defaults and existing design systems.
7. **Editors export back to text.** This one is non-negotiable for any artifact where the reader manipulates state. The artifact must end with a "copy as markdown" / "copy as JSON" / "copy as prompt" button that turns the UI state into something pasteable. The whole point of a throwaway editor is the round-trip.
8. **Accessible and safe.** Set `lang`, use semantic landmarks (`header`/`main`/`nav`/`footer`), keep contrast readable, label every control and give every figure `alt` text or a caption. Keep every interaction keyboard-operable with a visible focus style, honor `prefers-reduced-motion`, give each figure unique IDs, offer a keyboard or button alternative to drag and swipe, and redact secrets and personal data before sharing.

## Category index

Before drafting, read `references/matching-your-style.md` for every artifact, alongside its category reference: it holds the default look when no style exists and the steps for adopting one that does. Then pick exactly one row below. Choose by what the page is built around, not by the verbs in the request; "explain" or "compare" alone fits several rows.

| The page is built around… | Typical requests | Read… |
|---|---|---|
| Two or more candidates side by side, or a plan for the one chosen | compare approaches, flows, or UI directions; brainstorm; implementation plan | `references/exploration-and-planning.md` |
| Code at file and line level that the reader reviews, changes, or navigates | annotated diff, code review, PR writeup, module map of a package | `references/code-review-and-pr.md` |
| One design to look at or click through | mockup, component sheet, design tokens, animation or interaction prototype | `references/design-and-prototypes.md` |
| What connects to what in a system, drawn as boxes and arrows | how services fit together, request flow, deploy pipeline, figures for an article | `references/diagrams-and-illustrations.md` |
| How or why something works, or what happened, in prose sections | concept or feature explainer, onboarding material, status report, incident timeline, post-mortem | `references/reports-and-research.md` |
| Slides presented in sequence | deck, arrow-key presentation, talk | `references/decks.md` |
| Controls that change state and export it back as text | triage or reorder board, flag toggles, prompt tuner, dataset curator | `references/custom-editors.md` |

When two rows still seem to fit, these tie-breaks decide:

- **Code, system, or concept.** Code the reader reviews, changes, or walks file by file → `code-review-and-pr`. What connects to what (services, pipelines, request paths) → `diagrams-and-illustrations`. How or why something works, for a learner → `reports-and-research`. A figure inside an explainer does not move it to diagrams.
- **Several candidates or one.** Two or more candidates to choose between → `exploration-and-planning`, even when each candidate is a mockup or a flow. One design to build out → `design-and-prototypes`.
- **State the reader changes.** If the reader manipulates the page and exports the result → `custom-editors`, even when it lays items out side by side.

If the request asks for several deliverables (e.g., "implementation plan with mockups and a flowchart"), read the reference for each. They're short.

## Output mechanics

Two delivery modes, slightly different mechanics. Which one applies depends on the runtime, not on the content.

### Writing a file to disk

Save to the working directory with a descriptive `kebab-case` name and a `.html` extension. Examples: `onboarding-design-explorations.html`, `pr-streaming-review.html`, `cycle-14-triage.html`. After saving, tell the user the path and offer to open it in their default browser (`open <file>` on macOS, `xdg-open <file>` on Linux). The user may want to upload it somewhere shareable — that's their call, but mention the option once.

If the artifact is a member of a *web* of related files (explorations → mockups → plan), put them in a folder together so they can be opened/shared as a unit.

### Rendering into an inline preview

Some runtimes render a document inline next to the conversation instead of writing it to disk. Emit a single `text/html` document — not a component framework, not a bare diagram, not SVG-only — unless the request specifically calls for one of those. It is the closest analog to the file on disk and gives the user the same affordance: open, screenshot, share.

Sandboxed preview panes are stricter than a local file. Guard storage access with try/catch and an in-memory fallback instead of assuming `localStorage`/`sessionStorage` exists, keep everything in one file, and load no external scripts beyond whatever the host allows. Some runtimes render a single self-contained file with storage possibly unavailable, so the guarded in-memory fallback above is the portable default.

## A note on token cost and time

HTML artifacts cost roughly 2–4× the tokens of a markdown equivalent and take longer to generate. Account for that cost when deciding whether a deliverable warrants HTML; a disposable iteration such as "summarize this file" usually does not.

## A note on taste

Bad-looking HTML is worse than good markdown. If the artifact would render as a wall of generic Tailwind cards with emoji headers, slow down. That is why `references/matching-your-style.md` is read for every artifact, alongside its category reference (see the Category index). If the user has a design-system skill or design system file in the repo, lean on it. If not, default to a calm typographic layout — system serif body, restrained palette, real structure — rather than a busy "dashboard" look.

## Credits

Adapted from [dogum/html-artifacts](https://github.com/dogum/html-artifacts)
(Apache-2.0), which in turn builds on Thariq Shihipar's essay *The
Unreasonable Effectiveness of HTML*. Edited here for the conventions of this
repo: a shorter frontmatter description, agent-neutral prose, and hand-offs to
the neighbouring skills.
