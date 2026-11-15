# HTML Artifacts: example pages

This README is for people browsing the repository who want to see what the
`html-artifacts` skill produces. Agents read [SKILL.md](SKILL.md) and the pages
under [references/](references/); they do not load this file or the examples.

Each layout reference has one example page in [examples/](examples/). Every
page is a single self-contained HTML file: no network requests, no build step.
All of them use the default look from
[references/matching-your-style.md](references/matching-your-style.md), which
is why that reference has no example of its own.

## Viewing the examples

GitHub shows an `.html` file as source code. To see the page, open the file in
a browser from a local clone (`xdg-open` on Linux, `open` on macOS), or
download it with the *Download raw file* button and open the download.

## The examples

| Example page | Layout reference | What it shows |
| --- | --- | --- |
| [exploration-and-planning.html](examples/exploration-and-planning.html) | [exploration-and-planning.md](references/exploration-and-planning.md) | Three options in columns with the same structure, a pro/con table and metrics each, and a recommendation |
| [code-review-and-pr.html](examples/code-review-and-pr.html) | [code-review-and-pr.md](references/code-review-and-pr.md) | An annotated diff: margin notes pinned to lines, severity tags, jump links, collapsible files |
| [design-and-prototypes.html](examples/design-and-prototypes.html) | [design-and-prototypes.md](references/design-and-prototypes.md) | An animation prototype: sliders, an easing-curve graph, replay, and live CSS to copy |
| [diagrams-and-illustrations.html](examples/diagrams-and-illustrations.html) | [diagrams-and-illustrations.md](references/diagrams-and-illustrations.md) | A hand-placed SVG flowchart with a highlighted happy path, a legend, click-to-expand details, and Copy SVG |
| [reports-and-research.html](examples/reports-and-research.html) | [reports-and-research.md](references/reports-and-research.md) | A post-mortem: impact summary, minute-by-minute timeline with log excerpts, root cause, action items with owners |
| [decks.html](examples/decks.html) | [decks.md](references/decks.md) | A 16:9 slide deck: arrow keys, buttons and swipe, slide counter, fullscreen, presenter notes, light/dark switch |
| [custom-editors.html](examples/custom-editors.html) | [custom-editors.md](references/custom-editors.md) | A triage board: drag or keyboard moves, a capacity warning, saved state, export as markdown or JSON |

Each reference describes several shapes (a reports reference covers concept
explainers, status reports and post-mortems, for example); the example shows
one of them.

## The examples are illustrations, not specifications

The examples are written by hand and are not generated from the references or
checked against them. When a reference changes, its example may lag behind.
Where the two disagree, the reference wins. All names, numbers and events in
the examples are made up.
