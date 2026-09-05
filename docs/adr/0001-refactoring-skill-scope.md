# ADR-0001: Scope of the `refactoring` skill

## Status
Accepted (2026-09-05)

## Context

The `refactoring` skill was restructured four times between late July and
early September 2026, each time with the reasoning recorded only in a commit
message:

1. `refactoring-checklist` + `fowler-refactoring-catalog` merged into one skill (#50).
2. Turned into a category router with four members: `refactoring-techniques`,
   `stepdown-rule`, `tdd`, `uncertainty-management` (#56).
3. Collapsed back into one skill whose text justified every section with a
   "measured against a no-skill baseline" claim (commit `ba7ee79`, no body).
4. A review-feedback section forged from obra/superpowers was added (`5ff7439`).

A scope review on 2026-09-05 found:

- **The measurement claims have no artifact.** The eval-suite grades R code
  only; there is no refactoring task, no judge run, no ablation log. The
  skill's shape rested on a measurement nobody can re-run.
- **Five of seven sections were not about refactoring.** "Build what was
  asked" and "take review feedback apart" are general conduct, exactly the
  class of rule the skill's own omit-list said belongs in a rules file (and
  the repo had already decided, in `c309eec`, to keep such a rules file out
  of version control). The checkpoint/rollback and "what happens at 4am"
  sections are migration planning. "Feel the interface" is test-first
  development.
- **The Fowler catalog had no reader.** Nothing referenced
  `references/CATALOG.md`; the 62 technique names are in every model's
  training data, and the skill itself said the common techniques are applied
  without prompting.
- **Distribution metadata had drifted.** `plugin.json`, `marketplace.json`
  and two of four recall probes still advertised the stepdown rule, TDD and
  the Fowler catalog, all of which the skill no longer contained.
- The one component with a job the model does not do unprompted is
  `scripts/churn.py`: a git-history hotspot ranking for "where should we
  start?" in an unfamiliar repo.

## Decision

Reduce `refactoring` to one job: finding refactoring targets. It keeps
`scripts/churn.py`, a workflow for reading its output, the cases where the
ranking lies, and two short discipline notes (refactor or change behavior,
never in the same step; characterize untested code first). Everything else is
removed. The skill stays an auto-triggered skill named `refactoring` in its own
category, with a description under the default 250-character budget; it leaves
the description allowlist.

The skill no longer claims measured effects. The two retained notes are marked
as reasoned, not measured.

## Decision drivers

- A skill should carry only what the model would not do unprompted; the churn
  ranking is the only part of the old skill that clearly meets that bar.
- Unverifiable "measured" language is worse than an honest "reasoned"
  qualifier.
- "Where should I start?" is asked in natural language, so the skill needs an
  auto-trigger description; a user-invoked command would be forgotten.
- The always-loaded description budget is shared across all auto skills; a
  393-character description covering five intents was the most expensive
  entry in the manifest.

## Considered options

- **Trim to the refactoring residue (chosen).**
- **Split** into a refactoring core plus a `risky-change` skill for
  migrations. Rejected: the migration notes would not justify their own
  description budget, and there is no natural router slot for them.
- **Delete the skill, keep churn.py as a loose tool.** Rejected: a script
  nobody is pointed at is not used.
- **User-invoked command skill.** Rejected: the trigger is a natural-language
  question, not a remembered command.
- **Fold churn.py into `coupling-cohesion` as a fourth mode and dissolve the
  category.** Rejected: that skill is already the second-largest in the repo
  and measures structure, not history; dissolving the category touches six
  files for no gain.
- **Build refactoring tasks into the eval-suite first, then cut by
  evidence.** Rejected for now: the suite grades R code with tests; judging
  refactoring output needs an LLM judge with high variance, a separate
  project. Reopen if the trimmed skill is suspected of missing something.

## Consequences

- Skill drops from ~12,000 to ~3,500 characters; the always-loaded description
  from 393 to under 250 characters.
- The migration-staging notes (checkpoint before the step, validation signal,
  rollback action, "what happens at 4am"), the review-feedback notes, the
  scope-discipline note and the TDD note are gone from the repo. They remain
  recoverable at commit `5ff7439`. If any of them proves missed in practice,
  the conduct rules belong in a personal global rules file outside the repo
  (per `c309eec`); the migration notes would need their own skill with its
  own trigger evidence.
- The Fowler catalog is gone. Look up an unfamiliar technique in the book.
- Recall probes for TDD, the stepdown rule and migration staging are removed;
  no skill owns those intents any more.

## Notes

Deliberately not in the skill, recorded here so it is not helpfully re-added:

- Fowler mechanics or a technique catalog.
- Smell-to-technique lookup tables, priority matrices, language-specific
  smell checklists.
- Wall-clock or calendar rules ("steps under 30 minutes"); outcome
  checklists ("complexity below 10") that cannot be observed from inside a
  task.
- General conduct: build only what was asked, review-feedback handling,
  anti-sycophancy. Rules files, not skills.
- Co-change / temporal-coupling analysis in `churn.py`. A real signal, but it
  needs a pair pass over the log and a section explaining how to read it.
  Reconsider only with evidence that the hotspot ranking alone leaves the
  question unanswered.

Before adding anything back, compare against a no-skill baseline on the same
prompt and keep the transcript or score in the repo, so the next scope review
has an artifact instead of a claim.
