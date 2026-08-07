---
name: html-artifacts
category: communication
environments: coding, chat
description: Produce a self-contained HTML file instead of a markdown reply when the content has spatial, comparative, or interactive structure. Covers side-by-side comparisons, diagrams, timelines, decks, and throwaway editors.
---

# HTML Artifacts

Markdown is the default agent output, but for anything longer than a handful of sentences it's a poor format. It can't show two options side by side, can't render a real diagram, can't be interactive, and can't be shared by link. HTML can do all of those — and when the artifact is the deliverable rather than something you'll skim and forget, the difference between "a document I'd skim" and "a document I'd actually read" is enormous.

The use cases below are not the only places HTML helps, but they cover most of the territory. The pattern in every category is the same: the agent picks a layout that makes the *shape* of the content visible, instead of flattening it into linear prose.

## When to use

Reach for HTML when **any** of the following is true. Don't wait for the user to ask explicitly.

- **Comparison.** Two or more options/approaches/designs the reader needs to weigh against each other. Side-by-side beats stacked.
- **Spatial information.** Diffs, call graphs, module maps, flowcharts, timelines, before/after — anything where position carries meaning.
- **Interaction matters.** Animations, easing curves, parameter tuning, state transitions — things the reader needs to *feel*, not read about.
- **Reference material.** A document the reader will navigate non-linearly: tabs, collapsible sections, glossary in the margin, jump links.
- **Color or hierarchy carries meaning.** Severity tags, status colors, syntax highlighting, design tokens.
- **One-off editor.** The reader needs to manipulate a thing (drag tickets, toggle flags, tune a prompt) and round-trip the result back into a prompt or a commit.
- **The reader will share it.** A spec going to leadership, a PR writeup going to reviewers, a status report going to a team. People are dramatically more likely to actually read an HTML page than a markdown file.
- **Length.** Anything longer than ~100 lines in markdown becomes hard to read. HTML's navigation and layout earn their keep past that threshold.

The heuristic, said another way: if the user is going to *do* something with the document — read it carefully, share it, refer back to it, hand it to an implementer, paste edits back in — make it HTML.

The request rarely says "HTML" or "artifact." It says: doc, writeup, plan, spec, report, explainer, summary, comparison, review, PR description, mockup, diagram, flowchart, deck, slides, status update, post-mortem, incident report, playground — or a one-off editor for triaging, reordering, or tuning something. It also shows up as a verb: explain, summarize, compare, explore options for, brainstorm directions for, walk through. When any of those lands on a non-trivial topic, HTML is on the table.

## This skill picks the format, not the content

It decides how a deliverable is rendered. What goes *in* the deliverable is often another skill's job, and the two compose — run the other skill for the substance, then render its output as HTML instead of markdown:

- Weekly/monthly leadership status, launch announcements, risk escalations → `stakeholder-update`.
- Standup prep or a status update assembled from recent repo activity → `repo-status`.
- The internal structure of a technical explanation (problem before solution) → `problem-first-explanation`.

## When to stay in markdown

Markdown still wins for:

- Short conversational replies inside chat.
- Code-only outputs (a function, a config block, a one-liner).
- Terminal/command-flavored answers ("run this, then that").
- Quick three-bullet summaries the reader will scan once and discard.
- Files that need to be diffed in version control regularly. HTML diffs are noisy. If the artifact will live in git and be reviewed in PRs over time, markdown is friendlier — though even then, *generating* an HTML view alongside is often worth it for review.

If the artifact is going to be edited by hand by a human afterward, markdown is also friendlier. But increasingly artifacts are edited by re-prompting Claude, which removes that advantage.

## Universal rules for every HTML artifact

Every artifact this skill produces must satisfy all of these:

1. **Single self-contained `.html` file.** No build step, no bundler, no `npm install`. CSS goes in a `<style>` tag, JS goes in a `<script>` tag, images are inline SVG or data URIs.
2. **Works offline.** No required network calls at view time. If a CDN is used (Tailwind, a font, a library), prefer well-known stable CDNs and assume the user might want to swap to inlined later. For a file that may be archived or uploaded to object storage, lean toward fewer external dependencies.
3. **Mobile responsive.** Include `<meta name="viewport" content="width=device-width, initial-scale=1">` and a layout that survives a narrow viewport. The reader may open it on a phone.
4. **Real layout, not stacked headers.** If the content is a comparison, lay it out in columns. If it's a timeline, draw a timeline. If it's a diff, render a diff. Don't translate markdown structure 1:1 into HTML — that's wasted effort.
5. **Readable on its own.** Title at the top, a one-paragraph TL;DR or framing sentence right below, then the substance. The reader should know what they're looking at within five seconds.
6. **Tasteful by default.** A neutral but considered design: legible serif or sans body, comfortable line length (60–75ch), generous spacing, restrained color, dark-mode-friendly if cheap. Resist the default-AI aesthetic of "everything is a card with a gradient." See `references/matching-your-style.md` if the user has an existing design system to match.
7. **Editors export back to text.** This one is non-negotiable for any artifact where the reader manipulates state. The artifact must end with a "copy as markdown" / "copy as JSON" / "copy as prompt" button that turns the UI state into something pasteable. The whole point of a throwaway editor is the round-trip.

## Category index

Pick the matching reference file below before drafting. Each one has the per-category pattern (what the layout should look like, what's load-bearing, what mistakes to avoid) plus a sketch of a concrete example.

| If the request is about… | Read… |
|---|---|
| Brainstorming options, side-by-side comparisons, implementation plans, exploring directions before committing | `references/exploration-and-planning.md` |
| Annotated diffs, PR writeups, code review, module maps, "explain this code" | `references/code-review-and-pr.md` |
| Design systems, component sheets, mockups, prototyping animations or interactions | `references/design-and-prototypes.md` |
| Inline SVG figures, flowcharts, architecture diagrams, technical illustrations | `references/diagrams-and-illustrations.md` |
| Status reports, incident timelines, post-mortems, concept explainers, feature deep-dives, learning material | `references/reports-and-research.md` |
| Slide decks, arrow-key presentations | `references/decks.md` |
| One-off custom editors: triage boards, flag toggles, prompt tuners, dataset curators | `references/custom-editors.md` |
| Matching the user's existing visual style or design system | `references/matching-your-style.md` |

If the request spans multiple categories (e.g., "implementation plan with mockups and a flowchart"), read all the relevant references. They're short.

## Output mechanics

Two delivery modes, slightly different mechanics. Which one applies depends on the runtime, not on the content.

### Writing a file to disk

Save to the working directory with a descriptive `kebab-case` name and a `.html` extension. Examples: `onboarding-design-explorations.html`, `pr-streaming-review.html`, `cycle-14-triage.html`. After saving, tell the user the path and offer to open it in their default browser (`open <file>` on macOS, `xdg-open <file>` on Linux). The user may want to upload it somewhere shareable — that's their call, but mention the option once.

If the artifact is a member of a *web* of related files (explorations → mockups → plan), put them in a folder together so they can be opened/shared as a unit.

### Rendering into an inline preview

Some runtimes render a document inline next to the conversation instead of writing it to disk. Emit a single `text/html` document — not a component framework, not a bare diagram, not SVG-only — unless the request specifically calls for one of those. It is the closest analog to the file on disk and gives the user the same affordance: open, screenshot, share.

Sandboxed preview panes are stricter than a local file. Assume: no `localStorage`/`sessionStorage` (use in-memory state), no external scripts beyond whatever the host allows, and everything in one file.

## A note on token cost and time

HTML artifacts cost roughly 2–4× the tokens of a markdown equivalent and take longer to generate. This is a real tradeoff. The skill is configured to err toward HTML because the reading experience is dramatically better and shareability matters, but if the user is iterating fast on something disposable ("just summarize what's in this file"), a markdown reply is fine. Don't manufacture a use case for HTML where there isn't one.

## A note on taste

Bad-looking HTML is worse than good markdown. If the artifact would render as a wall of generic Tailwind cards with emoji headers, slow down. Read `references/matching-your-style.md` first. If the user has a `frontend-design` skill or design system file in the repo, lean on it. If not, default to a calm typographic layout — system serif body, restrained palette, real structure — rather than a busy "dashboard" look.

## A note on what this skill is not

This skill is not "always answer in HTML." The point is not the format; the point is that for many of the things people ask agents to produce — plans, comparisons, reviews, explainers, editors — the format markdown forces (linear text, no spatial layout, no color, no interactivity) actively obscures the content. HTML lifts that constraint. Where markdown is genuinely the better medium, use markdown.

## Credits

Adapted from [dogum/html-artifacts](https://github.com/dogum/html-artifacts)
(Apache-2.0), which in turn builds on Thariq Shihipar's essay *The
Unreasonable Effectiveness of HTML*. Edited here for the conventions of this
repo: a shorter frontmatter description, agent-neutral prose, and hand-offs to
the neighbouring skills.
