---
name: uncertainty-management
description: Manage risky, hard-to-predict changes by decomposing them into small validated steps, checkpointing before each one, and rolling back on trouble. Use whenever a change is risky, its full impact cannot be foreseen in advance, or the user is planning a migration, refactor, deployment, rollout, or any other change where "what could go wrong" matters — even if they do not name a specific pattern like canary or feature flag.
metadata:
  version: "1.0"
---

# Uncertainty Management

Some changes cannot be fully understood in advance — the effects only become clear once the change is partially made. The temptation is to try to anticipate every scenario up front. That does not scale: real systems (codebases, deployments, data pipelines, personal routines) are too complex to model exhaustively before acting.

This skill encodes the alternative: **accept the uncertainty and build a safety net instead of trying to eliminate it.** Decompose the change, checkpoint before each step, validate after each step, and roll back the moment something looks wrong. The point is not to avoid risk — it is to bound how much of it any single step can cost, and to turn each step into a source of information for the next one.

## Core principle

Every risky change should be decomposed into small, validatable steps. Before each step, create a checkpoint that allows returning to the prior state if something goes wrong.

## The three pillars

1. **Decomposition** — break the large change into small, atomic steps. Each step should be independently meaningful and independently reversible.
2. **Checkpointing** — capture the current state before each step, not after. The checkpoint is what you roll back *to*, so it must exist before the risk is taken.
3. **Validated rollback** — after each step, check whether it succeeded. If not, roll back to the last checkpoint rather than pushing forward or patching in place.

Skipping any one of the three collapses the pattern: decomposition without checkpoints just means smaller uncontrolled failures; checkpoints without validation mean you never know when to use them; rollback without decomposition means an all-or-nothing revert of a change too large to reason about.

## Anti-pattern: the big-bang change

Doing the whole change at once maximizes risk and minimizes learning. When something breaks, it is unclear which part of the change is responsible, and there is no smaller state to fall back to — only "before" and "after."

## Why this works

- **Bounds damage** — a failure only ever implicates the most recent step.
- **Enables learning** — feedback from each step informs the next decision, rather than betting everything on one prediction made in advance.
- **Reduces the fear of experimenting** — a safety net makes it rational to try things that would otherwise feel too risky to attempt.
- **Raises the success rate** — small steps are easier to validate than large ones; "did this work?" is a much easier question for a small step than for a whole migration.

## The three meta-questions

When designing a change under uncertainty — in software, in a process, in anything — ask:

1. **Early detection** — how will I notice if something is going wrong, as early as possible?
2. **Return to a stable state** — how do I get back to a known-good state if it does?
3. **Learning** — what does this step teach me for the next one?

If you cannot answer all three for a proposed change, the change is not yet decomposed enough, or the checkpoint is not yet real.

## Confidence-gated strategy selection

Uncertainty is not uniform — how cautiously to proceed should scale with how much is actually known about the situation. Use measured confidence to pick a strategy:

| Confidence | Strategy | Behavior |
|---|---|---|
| High — this kind of change has been done many times, with consistent success | Conservative | Use proven, well-tested methods; minimal deviation. |
| Moderate — done a few times, or with mixed results | Moderate | Balanced adjustments, with active monitoring. |
| Low — novel situation, little or no direct experience | Experimental / learning | Deliberately experimental approach, with heightened attention and tighter checkpoints. |

The apparent paradox: low confidence calls for the *more* exploratory strategy, not a more cautious one. This is not extra risk-taking — it is that in a genuinely unfamiliar situation, conservative "proven" methods are not reliably proven for *this* case. Learning fast, under tight monitoring, is the safer bet than committing to an untested assumption of safety. Correspondingly, low confidence should also mean smaller steps and more frequent checkpoints, not fewer.

Confidence itself should come from evidence, not gut feel: how often has this situation been encountered before, how often did the chosen strategy actually succeed, and how large is that sample (small samples should pull confidence down, not up). Treat confidence as something that gets updated after every step — situation → confidence → strategy → outcome → updated confidence — so the approach converges toward the conservative end for well-understood cases while staying appropriately exploratory for novel ones.

## Concrete patterns that implement this

Each of these is a specific technique for realizing decomposition + checkpoint + rollback in software:

- **Feature flags** — the change ships dark; enabling it for a subset of traffic *is* the atomic step, and disabling the flag *is* the rollback. Confidence in the flag's safety should gate how much traffic it is exposed to.
- **Canary releases** — deploy to a small slice of infrastructure or users first; the rest of the fleet is the checkpoint you never left. Validate on the canary before continuing the rollout; roll back the canary alone if it fails.
- **Strangler Fig pattern** — replace a legacy system piece by piece behind a routing seam, instead of a full rewrite. Each migrated piece is a decomposed step; the old code path remains the checkpoint until the new path is proven.
- **Tracer-bullet development** — build a thin, end-to-end slice of the system first to get real signal, then widen it. This is the decomposition pillar applied to *design* uncertainty: rather than designing the full system up front, take the smallest step that produces real feedback.
- **Small commits with tests** — in refactoring, each commit is a checkpoint and each test run is the validation gate; a failing test is the rollback trigger.
- **Blue-green deployment** — the idle environment is a standing checkpoint; cutting traffic back to it is the rollback with near-zero cost.

## Applying it outside software

The same three pillars and three meta-questions transfer directly to non-software changes — the checkpoint is just a different kind of "known-good state" and the atomic step a different kind of action:

| Domain | Atomic step | Checkpoint / rollback |
|---|---|---|
| Personal systems / process change | Adopt one new habit or rule at a time | Revert to the prior process for that one change without touching the rest |
| Energy management | Introduce one change to load or routine | A recovery protocol to fall back to when overloaded |
| Training | Progressive overload, one increment at a time | A deload or lighter week when signals indicate overreaching |
| Data pipelines | One graduated transformation stage | Pipeline checkpoints that allow reprocessing from a known-good stage |

## Workflow

1. **Name the change and its risk.** What is uncertain about the outcome, and what would "going wrong" look like?
2. **Decompose** the change into the smallest steps that are each independently meaningful and independently reversible.
3. **For each step, before taking it:**
   - Define the checkpoint (what "known-good state" you are capturing).
   - Define the validation signal (how you will know the step succeeded).
   - Define the rollback action (what exactly reverts to the checkpoint).
4. **Judge confidence** for the step — high / moderate / low, bucketed by prior experience with this kind of situation — and pick conservative / moderate / experimental accordingly (table above). Let low confidence shrink the step size and tighten monitoring, not skip the checkpoint.
5. **Take the step, then validate.** On success, the new state becomes the checkpoint for the next step. On failure, roll back — do not attempt to push through or patch forward from a partially-failed step.
6. **Update confidence** for this kind of situation based on the outcome, before moving to the next step.
7. **Close the loop with the three meta-questions** — confirm detection, return-path, and learning were all real for this change, not just assumed.

## Common mistakes

- Treating checkpointing as optional once "the change is simple." Simplicity is exactly what big-bang failures look like in hindsight.
- Creating the checkpoint *after* the risky step instead of before it — by then it is not a checkpoint, it is a postmortem.
- Choosing "conservative" strategy by default regardless of confidence, which under-explores well-understood situations and over-commits in novel ones.
- Validating only at the very end of a decomposed change, which throws away the main benefit (early detection, isolated blame for failures).
- Rolling back without asking what the failure teaches — the point is not just safety, it is that each step should raise confidence for the next one.


