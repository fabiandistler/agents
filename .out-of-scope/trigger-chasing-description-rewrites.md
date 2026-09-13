# Rewriting Skill Descriptions to Chase a Missing Trigger

When a skill does not fire for a request it should serve, this project does not
respond by rewriting the skill's `description` (or adding a `when_to_use`) to
target that request. The specific mechanism rejected is: take a probe that scores
near zero, reword the trigger text around it, re-measure, repeat.

## Why this is out of scope

Because it was tried, measured, and came back worse or flat — twice, in two
categories.

**Broadening beats nothing.** `html-artifacts` was rewritten away from its
concrete nouns ("spatial, comparative, or interactive structure") toward
reader-intent wording. Recall moved **6/20 → 2/20** (#142). The concrete nouns
were what had been doing the triggering work; generalising the description
removed the surface it fired from.

**The target phrase is already shipping, and does not help.** #110's option 2
proposed rewording the `architecture` router around the outcome rather than the
artifact, for the prompt "Zeichne mir eine Übersicht, wie unsere Services, die
Datenbank und die externen APIs zusammenhängen". But
`draw an overview of how the system fits together` sits verbatim in that
router's `when_to_use` on `main` today, and `c4-de` still scores **0/3** — as it
did with the old description, the rewritten description, and Opus 5. The noun is
on the surface. The model still does not reach for it.

**The remaining variant cannot reach half the audience.** `when_to_use` is
Claude-Code-only; Codex ignores the key (documented in
`scripts/check_descriptions.py`, verified against `codex debug prompt-input`).
#142 was reported against both clients, so any fix that travels in
`when_to_use` addresses at most half of the report by construction.

**And the rewrite is not free.** Every character of an auto-triggered
description is spent from a shared, CI-capped budget
(`scripts/check_descriptions.py`). Trigger-chasing spends that budget on the
request shapes that measurably do not respond to it.

The underlying reason, per ADR-0003: these requests are not missing a keyword,
they *look easy*. The model does them itself rather than consulting anything. No
phrasing of a description changes that judgement.

## What is in scope instead

- Documenting the skill as effectively user-invoked, which is what ADR-0003 does.
- Proposing a different **mechanism** for work the model is willing to do badly.
  That is an open question, and it needs its own design and measurement.
- Fixing a description that is genuinely wrong, missing its subject, or over the
  character budget. That is ordinary maintenance, not trigger-chasing.

## Reopen condition

Not "not now" — a specific, checkable one: **the acceptance bar has to become
resolvable first.** At 20 observations the run-to-run noise band swallows a
25-point effect in either direction (`triage-board` scored 2/5, 3/5, 3/5, 4/5,
5/5 under conditions differing only by chance; `easing-feel` 4/5, 3/5, 2/5, 1/5,
0/5). Any future rewrite attempt is unjudgeable until either the rep count rises
or the ±25 pp bar moves. Raise the measurement's resolution, then a rewrite
proposal can be evaluated on evidence rather than on a coin flip.

A proposal must also state which client it targets, and not rely on
`when_to_use` for a cross-client problem.

## Prior requests

- #110 — "c4-modeling is never reached from 'draw an overview of how the system fits together'" (option 2)
- #142 — "html-artifacts trigger iwie nicht richtig" (description rewrite, measured 6/20 → 2/20)
