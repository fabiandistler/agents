# A Skill for Writing PR Titles and Bodies

This catalogue ships no skill whose job is writing a pull request title or
body. `pr-description` (#518, ADR-0009) did that — German title and body, an
executed before/after reprex, the change in the smallest fitting visual, a
reading order, checks run — and was removed on 2026-10-20 (#544). This
project keeps it that way.

On 2026-10-20, after #544, the user asked for Matt Pocock's `pr` back. It is
vendored into `.claude/skills/` again. That copy serves cloud sessions in this
repo only and is not part of the catalogue, so this record still holds.

## Why this is out of scope

**The user does not need it.** The skill was built, used, and judged
unnecessary by the person it was built for. Writing a PR body is work the
agent does well enough unprompted, and the one convention that matters
everywhere — connect each PR to its issue — already lives in
`instructions/50-dev-practices.md`.

**An auto skill is never free.** As an `auto` skill it spent the always-loaded
description budget (`scripts/check_descriptions.py`) on every session, and its
references cost context on every PR. Keeping it in step with the vendored `pr`
upstream added maintenance with no reader to show for it.

**Skills that write a PR body as part of a larger job keep doing so.**
`release-pr` writes its own release body (see
`release-pr-body-language.md`), and `poc-spec-loop` opens its pull request
itself. Neither depended on `pr-description`.

Elsewhere, anyone who wants Pocock's `pr` can install the mattpocock-skills
plugin; that is outside this catalogue.

## What would reopen it

A recurring, documented failure of unprompted PR bodies that a skill would
demonstrably fix, linked in the request — not a wish for a nicer template.

## Prior requests

- #518: "pr-description" spec (built, then removed in #544)
- #528: "pr-description: forge-agnostic and leaner" (forge rules removed
  before the skill itself; the former `pr-description-forge-rules.md` record
  is folded in here)
