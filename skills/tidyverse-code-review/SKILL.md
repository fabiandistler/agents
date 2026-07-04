---
name: tidyverse-code-review
description: Review or author a pull request against an R package using the tidyverse code review conventions, prioritised by the Code Review Pyramid so design and correctness get attention before style and formatting. Use whenever reviewing an R/tidyverse-style pull request, writing review comments, deciding how deep a review should go, sizing and describing an R PR before opening it, or responding to review feedback on R code. Surfaces the R-specific pitfalls a generic language-agnostic review misses — zero-length object and NA edge cases, roxygen2/NAMESPACE consistency, lifecycle::badge() usage, the usethis::pr_fetch()/pr_forget() local-review workflow, NEWS.md bullet conventions, and single-purpose PR sizing — alongside the general practice of navigating a PR, calibrating review depth to its size, writing courteous comments, and handling pushback.
compatibility: Written for R packages that follow tidyverse conventions (roxygen2, testthat, NAMESPACE, NEWS.md, usethis PR helpers). The prioritisation logic and comment-writing guidance generalize to any language; the R/usethis-specific steps do not.
metadata:
  version: "1.0"
---

# Tidyverse Code Review

This skill combines two checklists — reviewing a pull request and authoring one
— into a single workflow for R packages that follow tidyverse conventions. Both
checklists are ordered by the same rule: **spend review time where it is worth
the most, not where it is easiest to comment.**

## Core principle: the Code Review Pyramid

Code reviews drift toward the aspects that are easiest to argue about —
formatting, spacing, naming taste — while the aspects that actually determine
code health — design, correctness, performance — get comparatively little
attention. The Code Review Pyramid (Morling) frames this as a priority
ordering: the foundation of a review should be the layers that automation
cannot check, and the top of the pyramid — style and formatting — should be
handled by tooling (`styler`, `lintr`), not by human back-and-forth.

The tidyverse guide's own aspect ordering embodies this pyramid directly:
design is explicitly called out as the **highest priority**, and style is
explicitly the aspect to hand off to automated tools and keep separate from
functional changes. Use this ordering whenever you are deciding what to look at
first, or what to let go of:

| Priority (base → tip) | Aspect | What to check |
|---|---|---|
| 1 (highest) | **Design** | Does the overall architecture make sense? Does this change belong in this package, or upstream / in a dependency? Does it integrate with the rest of the ecosystem? If there's a design misalignment, resolve that in a separate conversation before reviewing code line by line. |
| 2 | **Functionality** | Does the PR do what the author intended? Is that good for the end user and for future maintainers? Check R-specific edge cases explicitly: unexpected types, **zero-length objects**, `NA` handling. For user-facing changes, pull the PR locally with `usethis::pr_fetch()` and try it. |
| 3 | **Complexity** | Are individual lines or functions too complex to execute "in your head"? Is the code over-engineered for a speculative future problem instead of the present one? |
| 4 | **Tests** | Does new functionality or a bug fix ship with tests? Does the test reference the issue number (e.g. `#553`)? Are tests minimal, self-contained, and actually testing the right thing? |
| 5 | **Naming, comments, consistency** | Are names consistent with the rest of the package? Do comments explain *why*, not *what*? Is terminology used consistently (e.g. `loc` always means the same thing)? |
| 6 | **Documentation** | Is `roxygen2` documentation updated and complete for exported changes? Is there a `NEWS.md` bullet with the issue/PR number? Is the `pkgdown` reference index updated for new functions? |
| 7 (lowest — automate) | **Style** | Defer to `styler`/`lintr` output and the [tidyverse style guide](https://style.tidyverse.org/). Keep pure style changes in a separate PR from functional changes; use the style guide, not personal preference, to resolve disputes. |

If you find yourself spending most of a review on tier 6–7 issues while a tier
1–2 problem sits unaddressed, that is the pyramid telling you to reorder.

## Reviewing a PR

### Step 0 — does the change make sense at all?

Before reading a single line: read the linked issue and the PR description.
If the rationale doesn't hold up, say so early and courteously — for an
external contributor, point back to filing an issue first rather than
reviewing code that won't be merged regardless of quality.

### Navigating the PR

1. **Main parts first.** Find the file with the most logical changes — it
   gives you the context for everything else. Comment on major design
   problems as soon as you see them; don't wait until you've read every file.
2. **Rest, in logical order.** After the main file, work through the
   remainder in whatever order makes sense (tests first is sometimes better
   than main code first). Cover every file — don't skip any human-written
   code. Generated `.Rd` files can be scanned rather than deeply read (GitHub
   collapses them by default).
3. **Local testing for UI/user-facing changes:** `usethis::pr_fetch(<pr-number>)`
   checks out the PR locally so you can actually run it. Clean up afterward
   with `usethis::pr_forget()`.

Read every line of human-written code — you are responsible for understanding
what it does. If something is unclear, ask the author to clarify rather than
guessing; if it's outside your expertise, say so and suggest another reviewer.

### Calibrating review depth to PR size

| PR size | Typical depth | What that looks like |
|---|---|---|
| Small | 5–15 min | Surface bugs by "mental execution"; usually no local checkout needed. |
| Medium | up to 30 min | `usethis::pr_fetch()` and some local exploration. |
| Large | up to 1h+ (rare) | Design-level comments, and often a request to split the PR rather than review it whole. |

Team velocity matters more than any single reviewer's speed: slow reviews push
authors toward larger, worse PRs, and next-day feedback (across time zones)
should land before the author's next work session. Don't interrupt someone's
deep-work block for a review — wait for a natural break, and batch reviews
into your own break points.

### Writing comments

- Comment on the **code**, never the author. "This function" has the
  problem, not "you."
- Explain *why* — intent, best practice, or how it improves code health —
  not just *what* to change. This is what makes the comment a learning
  opportunity instead of an order.
- Point out the problem and let the author fix it when possible; provide a
  reprex for a bug rather than writing the fix yourself. Sometimes a direct
  code suggestion is still the more helpful choice — use judgment.
- Label severity so intent is unambiguous: `Nit:`, `Optional:`, `FYI:` for
  anything that isn't a required change.
- Use GitHub's suggestion feature for small tweaks (typos, comment
  additions); remind the author that suggestions applied via web UI still
  need a local `devtools::document()` if they touch roxygen comments.
- Approve-with-comments when you trust the author to address the remainder
  appropriately (more often with close collaborators, less with new
  contributors); reserve "request changes" for genuinely necessary
  additional review rounds.
- Compliment what's good, explicitly. Positive feedback reinforces the
  practices you want to see again.

### Handling pushback

- The author is often closer to the code and may have insights you don't.
  Evaluate their argument on code-health merits, and admit when they're
  right — but keep advocating when there's a real code-health risk.
- Don't fight every stylistic point; pick battles that matter.
- "We'll clean it up later" usually means never — insist on the cleanup
  happening in the current PR. Track genuinely unrelated bugs discovered
  along the way as separate issues, not blockers on this PR.
- If consensus doesn't emerge from the discussion, escalate to a
  synchronous conversation (video call) and document the outcome as a PR
  comment; involve a third team member if needed. Never let a PR stall
  indefinitely over disagreement.

## R-specific edge cases a generic review misses

A language-agnostic checklist will not catch these. Check them explicitly:

- **Zero-length objects, unexpected types, `NA` handling** — the classic R
  edge cases that silently break otherwise-correct-looking code.
- **NAMESPACE** — review every export/import change; an unreviewed
  `NAMESPACE` diff is an easy way to accidentally expose or break an API.
- **roxygen2** — is the documentation for the changed/added function
  actually complete, not just present? Internal-only helpers can use
  `@noRd` instead of full documentation.
- **`lifecycle::badge()`** — when a function's stability status changes
  (introduced as experimental, later stabilized, superseded, or
  deprecated), the badge should be added or updated to match.
- **Performance implications** — for `data.table`/`dplyr` (or base R)
  changes, consider whether the change has a real performance cost, and
  ask for a benchmark if it's not obvious.
- **Backward compatibility** — is a breaking change documented as such
  (`NEWS.md`, lifecycle badge, deprecation warning) rather than silent?
- **Dependencies** — CRAN-eligible dependency vs. a development-only one;
  make sure the distinction is intentional.

## Authoring a PR

### Before opening

- **Title (≤72 characters):** a short summary that stands on its own
  without the description — state what was done, not just what issue it
  fixes ("Fix bug" or "Add patch" is not enough).
- **Description:** the problem being solved, any shortcomings of the
  chosen approach, links to related issues (`Closes #545` / `Fixes #545`
  to auto-close; `Related to #545` / `Part of #545` to reference without
  closing), a before/after reprex, and benchmarks if performance is
  relevant. Summarize long prior discussion for the reviewer's benefit.
- **Reading order:** for large PRs, suggest an order (e.g. tests/examples
  before implementation) so the reviewer doesn't have to guess.
- **Self-review first:** re-read your own diff, check the description
  still matches the current state of the PR, fix grammar, and make sure CI
  is green before requesting review.
- **Reviewer selection:** match expertise to the affected part of the
  codebase; a high-level structural review from a non-expert is still
  valuable. For bigger changes, consider splitting API-design review from
  in-depth review across two reviewers.

### Scope and size — the single-purpose PR rule

- One PR changes **one clearly scoped thing.** Not "and while I was in
  there…"
- **~100 lines is the ideal size; more than ~1000 lines is almost always
  too big.** Size isn't only line count: 200 lines in one file is fine,
  200 lines spread across 50 files usually is not — file distribution
  matters as much as total lines.
- Keep refactoring PRs separate from feature/bugfix PRs. Small in-place
  cleanups (renaming a local variable) and small doc updates tied directly
  to the changed code are fine to include; a broader refactor is not.
- Refactoring PRs still need tests. If coverage doesn't exist yet, add
  tests in a separate PR *before* the refactor, not as part of it.
- If you discover a new bug while working, file it separately — don't let
  the current PR's scope creep to also fix it.
- **Exceptions where a large PR is acceptable:** whole-file deletions
  (a deletion is a single conceptual change), tool-generated automatic
  refactors (with verification), and cases where the reviewer has
  pre-consented to an unavoidably large PR — all of which call for extra
  diligence (longer review, more tests, more vigilance for bugs) rather
  than being skipped.

### Does this change belong upstream?

Ask this explicitly before investing effort in the PR, not after: is this
functionality actually the responsibility of this package, or should it live
in a dependency / a different, more general-purpose package? This is a
design-tier (pyramid tier 1) question, and it's cheaper to answer before
writing the code than after a reviewer raises it.

### NEWS.md convention

- Every user-facing change gets a `NEWS.md` bullet referencing the GitHub
  issue or PR number, e.g. `(#565)`.
- The chicken-and-egg problem (you don't have a PR number until you open
  the PR) resolves as: open the PR → note the PR number in the `NEWS.md`
  bullet → push the update.

### Documentation checklist

- `roxygen2` docs updated (and `devtools::document()` re-run) for any
  exported function whose interface or behavior changed.
- `@noRd` on internal-only functions that don't need a user-facing help
  page.
- `pkgdown` reference index updated when a new function is added.
- `lifecycle::badge()` added or updated whenever stability status changes.

### After receiving feedback

- Don't take it personally, and never reply while angry — pause first.
  Interpret reviewer frustration constructively; professional courtesy
  matters more than being right in the moment.
- Try to fix the *code* to be clearer before adding an explanatory
  comment — an explanation that only lives in the review tool doesn't help
  future readers of the source.
- Check your own understanding of what's being asked before pushing back;
  when you disagree, share the tradeoffs and any additional context you
  have (about users, the package, or the PR) and aim for a decision based
  on technical merits.
- Resolve addressed threads (thumbs-up + "Resolve conversation") to keep
  noise down for everyone; leave a thread open if a real question remains.
- Re-request review once all comments are addressed. If you can't
  re-request (e.g. as an external contributor), tag the reviewer directly.

### Finishing and merging

- `usethis::pr_fetch(<pr-number>)` — pull a PR (yours or someone else's)
  locally.
- `usethis::pr_forget()` — clean up the local checkout after a review is
  done.
- `usethis::pr_push()` — push changes when finishing off an external
  contribution yourself (after 1–2 review rounds, and always thank the
  contributor).
- `usethis::pr_finish()` — delete local and remote branches after merge
  and switch back to the default branch.
- Squash-and-merge is the default so history stays legible; use a real
  merge commit only when the individual commit history is itself
  meaningful.
- On close-knit teams, the author merges once approved and doesn't wait
  for further feedback after approval; on external contributions, the
  maintainer merges.
- Draft PRs are a legitimate tool for work-in-progress: parking CI runs,
  sleeping on a change overnight for a fresh self-review pass, or parking
  a proof of concept. Solo/one-person projects benefit from PRs too — it's
  practice for collaborative review, gives a historical record, and forces
  a CI run before merging to main.

## Common pitfalls

- **Relitigating style while a design problem sits unaddressed** — this is
  the pyramid inverted; automate style (`styler`/`lintr`) and spend the
  saved time on design and functionality.
- **Skipping the R-specific edge cases** — zero-length objects and `NA`
  handling are exactly the bugs a generic, language-agnostic review misses.
- **Mixing refactor and feature/bugfix in one PR** — makes both harder to
  review and to revert independently.
- **A `NEWS.md` bullet with no issue/PR number** — loses the traceability
  the convention exists for.
- **Accepting "we'll clean it up later"** — it usually doesn't happen;
  insist on the cleanup now, in this PR.
- **Merging without `pr_forget()` / `pr_finish()`** — leaves stale local
  and remote branches accumulating.
- **A PR that grew past ~1000 lines without reviewer consent** — ask for a
  split instead of trying to review it in one pass.

## Related skills

- **codebase-design** — vocabulary for design-tier review comments about
  module boundaries and deep-module interfaces.
- **adr-workflow** — record a genuine design disagreement and its
  resolution when review surfaces one worth remembering.
- **r-package-dev** — broader R package architecture and state-management
  guidance beyond the review process itself.
