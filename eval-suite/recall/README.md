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

## Live trigger check (`check_live.py`)

The menu A/B above forces a pick, so it measures *which* skill wins once the
model has decided to consult one. It cannot see the more common failure: the
model answers an architecture question from its own knowledge and never opens
the router at all. `check_live.py` measures that. It starts a real `claude -p`
session with the repo's plugins loaded in a throwaway git repository, sends one
realistic prompt from `live_prompts.json`, and reads from the event stream
whether the router was invoked and how the member was reached.

Three surfaces lead to a member and the report tells them apart in the `via`
column: `router` (the router fired and handed off), `read` (the model opened
the member's `SKILL.md` without the router), and `subagent` (a plugin subagent
that works from that member was launched, so the router never opened at all —
what `architecture:coupling-analyst` does for `coupling-cohesion`). `fired`
stays a count of the router alone, so a member reached without it is visible
rather than absorbed.

```sh
# routed layout, 3 runs per prompt (triggering is stochastic; read rates)
python3 eval-suite/recall/check_live.py --category architecture

# the same prompts with the members registered flat, for comparison
python3 eval-suite/recall/check_live.py --category architecture --flat

# pin the model you actually run
python3 eval-suite/recall/check_live.py --category architecture --model claude-opus-5

# the other routed category
python3 eval-suite/recall/check_live.py --category ai-ml
```

Prompts deliberately describe a situation without naming the technique
("two services share a database table", "keep a record of past decisions")
and some are in German; `category` decides which `--category` run selects a
prompt, and `expected` is the member that should handle it, `any` when only
the router firing matters, or `none` for near-misses that must not fire.
Every run spends real tokens, so this is a local check before touching a
router description, not a CI gate. Compare the same model and
prompt set before and after a change; with 3 reps per prompt, differences of
one or two runs are noise.

## Extending

Add prompts to `prompts.json` (`{ "prompt": ..., "expected": <skill name> }`)
when you add or reword a skill; keep `expected` names in sync with
`skills.json`. Before routing a further category, add a few prompts per member
and confirm the routed recall holds for that `--category`. The `workflow`
category is deliberately not routed: its skills are invoked explicitly rather
than picked by description matching, so a router would add a hop without
saving trigger surface.
