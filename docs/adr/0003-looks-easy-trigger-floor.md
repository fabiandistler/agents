# ADR-0003: Accept the auto-trigger floor for requests that look easy

## Status
Accepted (2026-09-13)

## Context

Some requests never reach the skill that would improve them, and the reason is
not the trigger text. The model only consults a skill for work it cannot easily
do itself; when a request *looks* like ordinary prose or drawing work, the model
simply does it. Three cases are now measured, across two different categories:

| probe | skill | reached | source |
| --- | --- | --- | --- |
| `c4-de` — "Zeichne mir eine Übersicht, wie unsere Services, die Datenbank und die externen APIs zusammenhängen. Am liebsten als Mermaid." | `c4-modeling` | 0/3 old description, 0/3 rewritten, 0/3 with `when_to_use`, 1/3 flat (Opus 5: 0/2, 0/2, 1/2) | #107, #110 |
| `decisions-deck-de` — walking a group through open decisions | `html-artifacts` | **0/10** | #142 |
| `easing-feel` — an interaction the reader has to *feel* | `html-artifacts` | **1/10** | #142 |

The contrast inside a single skill is what makes this a request-shape problem
rather than a skill problem. The same unmodified `html-artifacts` reaches
`cli-variants-de` (three options side by side) **10/10** and `triage-board` (a
throwaway editor whose result is copied back out) **8/10**. Its 47.5 % aggregate
is an artifact of the probe mix — adding or dropping a never-firing probe moves
it arbitrarily.

`coupling-de` also misses in every layout and is excluded from ADR-0002's
headline for that reason. Its mechanism was not separately established, so it is
listed here as a likely fourth case, not a measured one.

Two hypotheses were ruled out with evidence, so neither gets chased again:

- **Not the skill body suppressing itself.** `html-artifacts` carries a *When to
  stay in markdown* section, so the suspicion was that the model reaches the
  skill and answers in markdown anyway. With `Write` allowed and a wider turn
  budget: **8 sessions reached the skill, 8 wrote an HTML file** — perfect
  correspondence. The failure is entirely upstream of the body. (`check_live.py`
  cannot see this distinction at all: `ALLOWED_TOOLS` grants no `Write`, so it
  observes *reached*, never *written*.)
- **Not missing or buried trigger nouns.** `system diagrams (C4)` sits in the
  *first* sentence of the router's description, ahead of `Routes to a
  sub-skill.`, so this is not the truncation-to-first-sentence failure mode.
  Stronger still: the phrase `draw an overview of how the system fits together`
  is present verbatim in the router's `when_to_use` on `main` today, and `c4-de`
  still scored 0/3.

And one candidate fix was measured and came back **worse**: broadening
`html-artifacts`' description away from the concrete nouns ("spatial,
comparative, or interactive structure") toward reader-intent wording moved it
**6/20 → 2/20**. The concrete nouns were doing the triggering work.

## Decision

Accept the floor. These request shapes are below what an auto-trigger
description can reach, and we stop trying to close the gap by rewriting
descriptions.

Concretely:

- `c4-modeling` is treated as **effectively user-invoked** for "draw me an
  overview" requests: reached through `/architecture`, by naming C4, or by
  reading the member directly. Its value is the structured interview and the
  level discipline, not the drawing — and the drawing is the part the model does
  unprompted anyway.
- `html-artifacts` stays on the auto-trigger surface unchanged. It serves
  comparison and editor requests reliably, and it will keep missing
  feel-this-interaction and walk-a-group-through-decisions requests.
- No `activation` changes, no description changes, no `when_to_use` additions
  for this purpose.

The limitation is recorded here rather than as a note in each affected
`SKILL.md`, so the skills keep one job each and nothing leaks into the
description budget.

## Decision drivers

- **The available lever was measured twice and does not work.** Broadening a
  description made it worse (6/20 → 2/20); the exact target phrase already sits
  in `when_to_use` and still yields 0/3. Rewording is not an untried option, it
  is a refuted one.
- **`when_to_use` is Claude-Code-only.** Codex ignores the key (documented in
  `scripts/check_descriptions.py`, verified against `codex debug prompt-input`).
  #142 was reported against both clients, so a `when_to_use` fix could never
  have addressed half of it.
- **Option 3 would cost more than it buys.** Moving a skill to
  `activation: command` is a per-skill decision, not a per-class one: taking
  `html-artifacts` off the auto surface would sacrifice `cli-variants-de` at
  10/10 to chase `decisions-deck-de` at 0/10.
- **The acceptance bar cannot currently judge an attempt anyway.** See
  Consequences: at 20 observations the noise band swallows a 25-point effect in
  either direction.
- **Honest documentation beats an unreachable trigger.** A skill that is
  documented as user-invoked is usable; one that advertises an auto-trigger it
  does not achieve is a false promise, and paying description characters for it
  taxes every other entry.

## Considered options

The three options in #110, plus one the evidence since then suggests:

- **Accept it, document it (chosen).**
- **Reword the router (or a `when_to_use`) around the outcome the skill improves
  rather than the artifact** — "a diagram reviewers can agree on", "which level
  of detail to draw". Rejected: the closest measured form of this change made
  things worse, and the artifact-phrase version is already shipping at 0/3. See
  `.out-of-scope/trigger-chasing-description-rewrites.md`.
- **Move `c4-modeling` to `activation: command`.** Rejected for now, but the
  least unreasonable of the three: it makes the ADR's "effectively user-invoked"
  status literal. Not taken because it is a visible catalogue change bought with
  no measured recall gain — the skill already is not reached — and because the
  same move must not be generalised to `html-artifacts`. Reopen if the
  documented status turns out not to be enough in practice.
- **Fix the measurement before attempting another fix.** Deferred, and recorded
  as this ADR's reopen condition rather than as work.

## Consequences

- #110 and #142 close. Neither skill's files change.
- **The ±25 pp acceptance bar is not resolvable at 20 observations.** Measured
  during #142: `triage-board` scored 2/5, 3/5, 3/5, 4/5, 5/5 and `easing-feel`
  4/5, 3/5, 2/5, 1/5, 0/5 under conditions differing only by chance. Either the
  bar or the rep count has to move before any future attempt here can be judged.
  This is the condition for reopening; "not now" is not.
- The probes for these shapes stay in the recall suite (now
  `fabiandistler/eval-suite`, moved out in #147) as the **record of the floor**.
  A red `c4-de`, `easing-feel` or `decisions-deck-de` is the documented state,
  not a regression. Read the per-probe split, never the category aggregate: an
  aggregate over a mix containing never-firing probes carries no information.
- Anyone who wants C4 discipline has to ask for it. That cost is accepted.

## Notes

Deliberately not done, recorded so it is not helpfully re-added:

- More or better trigger nouns in any affected description.
- Outcome-flavoured rewrites of the `architecture` router description.
- `when_to_use` entries added to chase a shape Codex would not see anyway.
- A per-skill note in `SKILL.md` restating this limitation.
- Reading the `html-artifacts` 47.5 % aggregate as an under-triggering figure.

The open question this ADR does *not* answer: whether a skill that loses to
"looks easy" should exist on the auto surface at all, or whether the catalogue
needs a separate mechanism for work the model is willing to do badly. That needs
a mechanism proposal and its own measurement, not another description pass.
