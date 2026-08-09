---
name: refactoring
category: refactoring
environments: coding
description: Improving existing code safely, building features test-first, and staging changes whose blast radius is hard to predict. Use whenever the user wants to restructure existing code, triage code-review findings, judge whether a refactor is safe to start, build a feature test-first or in red-green-refactor cycles, or plan a migration, cutover, or rollout where what could go wrong matters.
metadata:
  version: "3.1"
---

# Refactoring & risky changes

This skill is deliberately short, and the shortness is the design.

Measured against a no-skill baseline on the same tasks, the model already picks
the right Fowler technique, decomposes functions by abstraction level, works in
vertical red-green cycles, catches language-specific smells unprompted, and
triages a review backlog sensibly. Restating any of that spends context to buy
nothing, and a long skill actively crowds out attention that the hard parts need.

What follows is the residue: the few places where default behavior measurably
drifts, and where the drift costs something real. Each section says why, because
a reason survives situations a rule doesn't anticipate.

These notes are additive. They correct a handful of specific tendencies — they
are not a method to follow instead of your own. Everything you would already do
on this task, keep doing; if a note below seems to be pulling you away from an
instinct that was serving the user, trust the instinct.

## Build what was asked, and nothing more

This is the largest measured effect, and it runs against a genuinely helpful
instinct. Left alone, the natural pull is to round a specification up. A
discount engine grows a voucher catalogue, a custom exception hierarchy, an
audit trail of applied rules. Every single addition is defensible on its own —
and the sum is a maintenance surface the user never agreed to own, in code they
now have to review line by line to find the part they actually asked for.

Implement the stated requirements and stop there. When a plausible extension
comes to mind, don't build it: collect it under a short **"deliberately not
built"** list at the end of the response. Nothing is lost — the user can pull
any item back in one line — but the decision stays with the person who carries
the maintenance cost. This applies just as much to refactoring: a request to
restructure is not an invitation to also fix the bugs you notice on the way.

Fix-worthy things you spot while working belong in that same list, described
precisely enough to act on later.

## Refactor or change behavior — never in the same step

Refactoring means external behavior stays identical, which is what makes a
green test suite meaningful evidence. Mix a behavior change into the same diff
and that evidence evaporates: a red test no longer distinguishes "the
restructuring broke something" from "the new behavior isn't finished yet," and
nobody reviewing the diff can tell which lines were supposed to be safe.

Finish one, commit, then start the other.

## Put the checkpoint before the step, not after

The second measured effect. When a change is risky enough to plan in stages,
the instinct is to snapshot the starting state once and then work forward. That
single global snapshot means every failure rolls back everything, which is the
outcome the staging was supposed to prevent.

Before each step, name three things explicitly:

- **Checkpoint** — the known-good state this step can return to, captured *now*, before the risk is taken. Captured afterwards it isn't a checkpoint, it's a post-mortem.
- **Validation signal** — the concrete observation that says this step worked. "Looks fine" is not a signal; a parity diff against the old path is.
- **Rollback action** — the specific thing to run to get back. If it hasn't been thought through, it won't happen at 3am.

If all three can't be named for a proposed step, the step is still too big.

Let unfamiliarity shrink the steps. When nobody involved has done this kind of
change before, the reflex is to reach for a proven, conservative playbook — but
"proven" was established somewhere else, on a system that differed in ways
nobody has mapped yet. Unfamiliar territory calls for smaller steps, tighter
validation, and a deliberately exploratory first move that exists to produce
information, not to make progress. Say so out loud when it applies: a team's
lack of prior experience with a migration is a reason to restructure the plan,
not a caveat to note and move past.

## Ask what happens when it breaks in production

A well-structured migration plan has a way of crowding out this question — the
decomposition looks so orderly that the operational failure mode reads as
already handled. It isn't. A plan can be perfectly staged and still leave
nobody knowing who gets paged when the nightly job dies halfway.

When production systems, scheduled jobs, or downstream consumers are in scope,
ask directly: what happens if this fails at 4am, who finds out, what runs
stale in the meantime, and how does the backlog get reprocessed afterwards.
Ask it even when — especially when — the rest of the plan looks tidy.

## Characterize before changing untested code

Tests are the instrument that says a refactor preserved behavior. Refactoring
code that has no tests means restructuring without that instrument and calling
the result safe because nothing visibly broke.

When coverage is thin in the area being changed, write characterization tests
first — tests that pin down what the code *currently* does, bugs included,
without judging whether it's right. Say this plainly rather than proceeding
with a caveat: "this needs tests around it first" is a real answer to "can you
refactor this," and it's usually the honest one.

## Feel the interface before implementing behind it

Writing the test first puts you in the caller's seat while changing the
interface is still free. The value is in that ordering, not in the ritual —
which is why a test written after the implementation, against an interface
that's already set, tends to confirm the design rather than question it.

When the public interface isn't obvious from the request, ask about it before
writing the first test, not after the third. Friction in writing the test is a
finding about the design, not an inconvenience to push past. If the request is
ambiguous enough that guessing would shape the API, name the ambiguity and the
assumption you're proceeding with, so the user can correct it cheaply.

Deliberate about the interface does not mean deliberate about the
implementation. Hardcoding a return value to get the first test green is a
legitimate move, not a shortcut to feel bad about: it separates "does this path
work at all" from "is the logic right," and lets the second test be the thing
that forces generalization. Reaching for the full implementation on the first
green skips that separation and gives up the design feedback the ordering was
meant to buy.

## When nobody knows where to start

For "where should we refactor first?" in a codebase nobody in the conversation
knows well, the bundled script ranks files by git churn instead of by guess:

```
python3 skills/refactoring/scripts/churn.py [path] [--since '12 months ago'] [--json]
```

It reports, per file: commits in the window, distinct authors, current size,
recency, and one composite score (change frequency × size — the classic hotspot
heuristic). Its own docstring explains each column.

Read the output as a reading list, not a work queue. Churn on its own is not a
defect: config files, route tables, and well-tested integration points churn
because the system is alive. The candidate is a file that changes often *and*
is hard to change safely, and only opening it tells you which. Skip the script
entirely when the repo is younger than the window, when a bulk reformat sits
inside it, or when the user already named the target — in all three the ranking
is noise.

## Long-tail technique lookup

[references/CATALOG.md](references/CATALOG.md) indexes all 62 Fowler techniques
by name with their inverses. Reach for it only for the unfamiliar tail —
looking up Extract Function or Guard Clauses there is pure overhead.

## What this skill deliberately omits

Recorded so it doesn't get helpfully re-added:

- **Fowler mechanics for the common techniques.** Both arms of the ablation applied them identically; the step-by-step was decoration.
- **Smell-to-technique lookup tables and priority matrices.** Non-discriminating across every test case.
- **Language-specific smell checklists.** The baseline found all of them unprompted, and a fixed list ages badly while general attentiveness doesn't.
- **Wall-clock and calendar rules** ("steps under 30 minutes", "changes under 2 weeks"). An agent has no calibration for either, so they resolve to noise.
- **Outcome checklists** ("complexity below 10", "team more confident", "delivery speed improved"). Not observable from inside the task, so they get answered by assertion rather than evidence.
- **A router with separate sub-skills.** At this size the indirection cost more than it saved.
- **Co-change / temporal-coupling analysis in the churn script.** Which files keep changing together is a real signal, but it needs a pair pass over the log and a section explaining how to read it — enough weight to stop the script being the small thing it is. Deliberately left out; reconsider only with evidence that the hotspot ranking alone leaves the question unanswered.

Before adding anything back, check it against a no-skill baseline on the same
prompt. If both arms produce it, it belongs here as a note like this one, not
as instructions.
