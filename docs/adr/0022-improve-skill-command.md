# ADR-0022: `improve-skill` refactors one skill, checked by a rule inventory or a behavior diff

## Status

Accepted (2026-11-26) by the maintainer in spec #992, after a grilling
session that settled its decisions. Built in slices: #993 (snapshot, slop
scan, candidate list) first, then #994–#996.

## Context

Skills in this catalogue and the ones uploaded to claude.ai collect filler:
definitions of what a model already knows, one case worded several ways,
option menus without a default, shouted `IMPORTANT`/`MUST` without a reason,
rules repeated across sections, trigger lists in the description, decorative
headings and closing summaries. The existing tooling only diagnoses: the
skill audit checklist, the `skill-reviewer` subagent, `writing-for-agents`
and the `audit-finding` issues ([ADR-0020](0020-audit-finding-issues.md)).
Nothing drives the cleanup itself, and after a hand rewrite there is no way
to tell whether the skill still behaves the same.

## Decision

A command skill, `improve-skill` (category `refactoring`), follows the flow
of `improve-codebase` ([ADR-0008](0008-fork-improve-codebase.md)) for one
skill folder: snapshot, slop scan, numbered candidates, an interview about
what is load-bearing, one rewrite, one check, and a unified diff as output.
It is a command, not an auto skill, so it does not fire on every "edit a
skill" request beside `writing-for-agents` and `skill-creator`.

- **Input** is any skill folder, git not required. The snapshot is both the
  baseline of the check and the way back.
- **Rubric**: the slop signals (`SL1`–`SL7`) live in the skill's own
  `references/slop-signals.md`, worded by structure so they hold for German
  skills too. The skill audit checklist points to them (B8–B10, and the
  signal IDs on B2, B4 and D3) instead of copying them. An installed copy
  carries its rubric with it; this repository keeps one source.
- **Check**: by default a **rule inventory** with no model runs, which blocks
  delivery on any unmapped rule and states that it cannot see emphasis or
  tone. On request, or proposed when an `evals.json`-covered rule is touched
  or more than a third of the text goes, a **behavior diff** through Anthropic's
  `skill-creator` old-skill/new-skill comparison. Outside Claude the run
  ends after the rewrite with a "verify by hand" note.
- **One rewrite and one check per run**, not per candidate, to bound the
  eval cost.
- **Descriptions are reported, never rewritten**: a trigger change would
  blur the behavior check. Description findings go to `skill-creator`'s
  description optimisation.
- **Output**: a repository skill gets a branch and a pull request; a
  claude.ai skill gets a ZIP packed by `skill-creator`'s packager, with the
  old ZIP kept beside it.

## Considered options

- **Use `ki-stil` as the rubric.** Rejected: it judges German prose for
  human readers; skill slop is structural and language-neutral.
- **Copy the slop signals into the checklist, with a drift check.**
  Rejected: a copy step plus a drift check is a layer without an
  abstraction of its own. The checklist points instead.
- **Compare two `claude plugin eval` runs by hand.** Rejected: that tool
  compares a session with and without a plugin, not version A against
  version B.
- **An own eval runner, for example on OpenRouter.** Rejected: a second
  runner to maintain next to `skill-creator`'s comparison loop.
- **Rewrite and check per candidate.** Rejected: an eval run per candidate
  multiplies the cost for no extra safety over one coherent rewrite.
- **Migrate claude.ai skills into a repository or org sync.** Rejected as
  too complicated: org sync needs a private or internal GitHub repository
  and syncs only merged pull requests with a plugin version bump.

## Consequences

- The skill audit and `improve-skill` share one vocabulary: an audit finding
  B9 and a candidate `SL4/B9` name the same thing.
- Moving or renaming `skills/improve-skill/references/slop-signals.md`
  breaks the checklist's pointer; both change in the same pull request.
- The behavior diff depends on `skill-creator` being installed; without it
  the rule inventory is the only check, and the skill says what that check
  cannot see.
- Catalogue-level analysis (overlapping triggers, rules duplicated across
  skills) stays out of scope and would need its own decision.
- `improve-skill` ships `evals.json` although command skills are exempt
  ([ADR-0006](0006-skill-eval-prompts.md)): the eval prompts and their
  planted-slop fixture in `docs/evals/fixtures/` are its regression net, and
  `scripts/check_evals.py` checks the shape of a command skill's file when
  one exists.
