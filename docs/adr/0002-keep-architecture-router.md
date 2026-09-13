# ADR-0002: Keep the `architecture` category behind a router

## Status
Accepted (2026-09-13)

## Context

The `architecture` category ships nine deep sub-skills behind one router entry.
#108 asked whether to keep that router or register the nine members flat, on the
strength of the live-recall measurement in #107:

| Layout (from #107) | Fired on architecture prompts |
| --- | --- |
| router, old description | 17/27 (63 %) |
| router, rewritten description | 59/81 (73 %) |
| members registered flat | 22/27 (81 %) |

That table read as roughly eight points in favour of flat, and #108's migration
plan followed from it: `build_routers.py`, `install.sh`'s member-disabling block
for Codex, `plugins/architecture/skills/`, and the README / AGENTS / recall
tables all encode the routed layout and would have to follow.

Both conditions behind those numbers have since changed:

- **`when_to_use` shipped on the router** (#109, commit `e9c9ae2`; verified in the
  frontmatter on `main`). In #107's own table that variant scored 22/27 on
  Sonnet 5 — identical to flat's 22/27. The eight-point framing compares flat
  against a router that is no longer what we ship.
- **The flat arm was measured against a placeholder plugin description.** Until
  #144, the throwaway flat plugin wrote a generated `plugin.json` description in
  place of the category's real one, removing part of the trigger surface from
  the flat arm only. `eval-suite/recall/README.md` now states those rates must
  not be pooled with post-fix rates.

#145 re-measured both layouts at `ddb968b` (post-#144), one isolated worktree
shared by every arm, `claude-sonnet-5` pinned, 5 reps per prompt, arms run
concurrently so a degraded moment hits both in the same window, no `SKILL.md`
touched. Headline over the seven discriminating positives, pooled across two
independent batches at 70 runs per arm:

| Arm | expected member reached |
| --- | --- |
| **routed** (description + `when_to_use`) | **62/70 (88.6 %)** |
| flat (nine members registered individually) | 42/70 (60.0 %) |

The direction is reversed, and the size of the gap reproduced exactly:

| batch | routed | flat | gap |
| --- | --- | --- | --- |
| v2 | 30/35 | 20/35 | +10 |
| v3 | 32/35 | 22/35 | +10 |

Three prompts carry the effect, each batch-stable: `ddd` 10/10 vs 3/10,
`microservices` 10/10 vs 4/10, `adr` 5/10 vs **0/10 — zero in every single
batch**. Three more (`pattern-de`, `fitness`, `sql-de`) are 10/10 in both arms.
Removing `ddd`, the largest single contributor, still leaves +13.

The headline deliberately excludes `c4-de` and `coupling-de`, the two prompts
that miss in *every* layout. They are not evidence about routing; they are
ADR-0003's subject.

## Decision

Keep the router. The `architecture` category stays one `activation: router`
entry with nine members behind it, exactly as it ships today.

No code changes. This ADR records a decision to leave the current state alone,
which is why the only artifact is documentation.

## Decision drivers

- **The measured gap favours the router and reproduced across independent
  batches.** +28.6 points pooled, +10 in each of two batches, with the routed
  arm stable at 31/30/32 of 35 across three batches. This is the strongest
  layout evidence the repo has.
- **`adr` is the clearest case: flat scored 0/10.** Registering
  `adr-workflow` on its own surface did not make the model reach it even once.
  Nine narrow descriptions do not add up to nine narrow triggers.
- **Only the router claims the broad question.** #107 measured "Is our
  architecture okay? Have a look at the repo" firing the router 6/9 and no flat
  member 0/3. Nothing in a flat layout owns the unspecific request.
- **One always-loaded description instead of nine.** The description budget is
  shared across every auto-triggered entry and capped in CI by
  `scripts/check_descriptions.py`. Flat spends nine entries to score lower.

## Considered options

- **Keep the router (chosen).** Zero migration, better measured recall.
- **Flip the category to flat.** Rejected on the re-measurement: 60.0 % against
  88.6 %, and it would touch `build_routers.py`, `install.sh`, the plugin tree
  and four documentation tables to get there.
- **Hybrid — keep the router and additionally register the three winning
  members flat.** Not rejected on evidence, because it was never measured; the
  per-prompt data does not support it either, since the members flat mode
  scored *worst* on exactly the prompts a promotion would target (`adr` 0/10).
  It would also double-register members and spend the description budget twice.
  Reopen only with its own measurement.
- **Decide on #107's numbers.** Rejected: both of that measurement's
  conditions have since changed, in the direction that flattered flat.

## Consequences

- The migration named in #108 does not happen. `build_routers.py`,
  `install.sh`'s Codex member-disabling block, `plugins/architecture/skills/`
  and the README / AGENTS / recall tables keep encoding the routed layout.
- **The result is Sonnet 5 only.** Every number above is `claude-sonnet-5`. The
  Opus 5 sample is two runs per prompt from #107 and was not repeated, so do
  not read 88.6 % as a cross-model figure. If the routed layout is ever
  suspected of behaving differently on Opus 5, that is a new measurement, not a
  re-reading of this one.
- `c4-modeling` and `coupling-cohesion` remain unreached from their natural
  prompts in both layouts. Routing is not what is wrong there — see ADR-0003.
- Reproduce with the command lines recorded on
  [#108](https://github.com/fabiandistler/agents/issues/108#issuecomment-5636928760);
  the superseded pre-#144 numbers are kept in that comment, marked as such.

## Notes

Deliberately not decided here, so it is not helpfully re-litigated:

- Whether nine members is the right count, or whether any member should be
  merged or dropped. Separate question, separate evidence.
- Whether the router's `description` or `when_to_use` wording can be improved.
  ADR-0003 covers why more or better trigger nouns are not the available lever.
- Anything about `activation: command`. Nothing in this category moves off the
  auto-trigger surface as a result of this decision.

Before re-opening the flat question, re-run both arms concurrently on the same
commit with the model actually in use, and report per-prompt counts per batch —
an aggregate over a changed probe mix moves arbitrarily and cannot carry the
decision.
