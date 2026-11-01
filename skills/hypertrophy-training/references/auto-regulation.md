# Part B — Auto-regulation: precise stop criteria

Part B of the hypertrophy-training skill. Section numbers such as A.6
refer to `programming-principles.md`.

## Contents

- [Prerequisite: RIR calibration (single working set)](#prerequisite-rir-calibration-single-working-set)
- [The three protocols](#the-three-protocols)
- [Plateau diagnosis: fatigue problem or stimulus problem](#plateau-diagnosis-fatigue-problem-or-stimulus-problem)

Auto-regulation lets a session's actual volume emerge from real-time
performance instead of a fixed prescribed number of sets — a direct
application of the Stimulus:Fatigue ratio. All three protocols below assume
an accurate sense of RIR; see the calibration step first if that is in doubt.

## Prerequisite: RIR calibration (single working set)

Most trainees systematically underpredict proximity to failure by about 1
rep (Halperin et al. 2022) — enough to turn a programmed 1 RIR into an
actual 2 RIR. Accuracy is worse on high-rep sets (above about 12 reps) and
better near failure, on heavier lower-rep sets, and in later sets, so treat
early-set high-rep RIR calls as the least trustworthy. Before relying on any
auto-regulation protocol, recalibrate:

1. Use a single working set per exercise.
2. Choose safe exercises (machines, dumbbells, a power rack with safeties) —
   true failure without experience carries injury risk.
3. Aim for true muscular failure (0 RIR).
4. Hold this for 3–4 weeks, then add volume gradually (1–2 sets per
   progression) once RIR estimation is accurate.

This is especially worth repeating after a long layoff or when switching to
unfamiliar exercises.

## The three protocols

- **5% Fatigue Rule**
  - Best fit: Heavy compounds, 1–6RM, plates fine enough to drop ~5%
  - Stop criterion: Start set at 1 RIR; drop load ~5% and repeat the same rep count; keep dropping until 1 RIR is reached again — then stop
  - Worked example: 100kg×4 @1RIR → 95kg×4 @2RIR (still light) → 95kg×4 @1RIR → **stop**
- **Rep Drop**
  - Best fit: Moderate-to-high reps, 6–15+RM, where fine load jumps aren't practical
  - Stop criterion: Start set at 1 RIR; keep the same load; continue until reps fall 2 below the starting set's rep count — then stop. Safety cap: even with exceptional work capacity, stop at a maximum of 5 sets regardless of rep reduction
  - Worked example: 80kg×10 @1RIR → 80kg×9 @1RIR → 80kg×9 @1RIR → 80kg×8 (−2 reps) → **stop**
- **Myo-Reps**
  - Best fit: Time-efficient work using an activation set + mini-sets
  - Stop criterion: Perform an activation set, then mini-sets at 0–1 RIR; stop when a mini-set falls 1 rep below the *initial* mini-set. Failure on the very last mini-set is common and acceptable, since volume is already auto-regulated
  - Worked example: 80kg×10 (activation) + 4 + 4 + 3 (1 rep below the first mini-set) → **stop**

Rough volume equivalence for Myo-Reps: one Myo-Rep set (5–15 reps after
activation) ≈ 2–4 traditional sets; 1–2 Myo-Rep sets (15–25 reps after
activation) ≈ 4–6 traditional sets.

All three share the same logic: a specific, observable drop in performance
(load tolerated, reps completed, or mini-set reps) signals accumulated fatigue
and serves as a built-in volume limiter — replacing a fixed, pre-decided set
count with a real-time readout of the Stimulus:Fatigue ratio.

## Plateau diagnosis: fatigue problem or stimulus problem

When progress stalls for 3–4 weeks, do not guess whether the fix is more or
less training — test it. Applying the wrong fix (more volume to an
over-fatigued trainee, or less volume to an under-stimulated one) is common
and can delay progress by months.

```
3-4 weeks of stagnation
        │
        ▼
Phase 1 (1-2 weeks): increase rest days / reduce frequency,
keep intensity and per-session volume unchanged
        │
        ├── Progress returns ──▶ FATIGUE problem
        │                        → reduce volume and/or frequency
        │                          durably (trade one for the other)
        │                        → deload when need signals show it (see Part A.6),
        │                          rather than on a fixed 4–6 week cycle
        │
        └── No progress ──────▶ STIMULUS problem
                                 → train closer to failure (lower RIR)
                                 → increase volume gradually
                                 → introduce exercise variety
                                   (e.g. shift from compound to
                                   isolation exercises to raise the
                                   Stimulus:Fatigue ratio and reach
                                   under-recruited fibers/regions)
```

Volume cycling (Part A.6) is the preventive version of this test — cycling
volume down periodically before a genuine plateau forces the diagnosis.
