# Trigger-recall A/B (routers)

A standalone check that answers the question issue #50 gates category routing
on: **does collapsing a category's skills behind one broad router skill hurt
which skill the model would pick?**

The main eval-suite (`../`) force-injects a skill via `AGENTS.md` and grades
the resulting R code — it measures output quality once a skill is *already*
loaded, so it can't see triggering. This check is the missing piece.

## How it works

`check_recall.py` builds two menus of skill descriptions from `skills.json`:

- **flat** — every auto skill listed individually (the pre-router world);
- **routed** — one broad router entry per routed category, plus the individual
  skills of any non-routed category.

For each labelled prompt in `prompts.json` it asks the model (via the `claude`
CLI) to pick the single best-matching skill, then scores recall. A pick is a
hit when it names the expected skill; in the routed menu, naming the **router**
of the expected skill's category also counts — the router is the correct next
hop, which then routes to the sub-skill.

The gate: **routed recall must be ≥ flat recall − tolerance** (default 0). A
regression means that category should not be flipped (or its router
description needs broadening).

## Running

```sh
# print the two menus and the prompt count without calling the model
python3 eval-suite/recall/check_recall.py --dry-run

# full A/B (needs the `claude` CLI on PATH; skips cleanly if absent)
python3 eval-suite/recall/check_recall.py

# only the architecture prompts, allow a 1-prompt drop
python3 eval-suite/recall/check_recall.py --category architecture --tolerance 1
```

If `claude` is not on `PATH` the check prints `SKIP` and exits 0, so it is safe
to wire into CI environments without model access; run it locally (or in a
model-enabled job) before flipping a category.

## Extending

Add prompts to `prompts.json` (`{ "prompt": ..., "expected": <skill name> }`)
when you add or reword a skill; keep `expected` names in sync with
`skills.json`. Before routing the next category (workflow, refactoring, …), add
a few prompts per member and confirm the routed recall holds for that
`--category`.
