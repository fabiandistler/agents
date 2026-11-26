# Eval mode

The behavior check of step 7 in `SKILL.md`, run after the rule inventory
when the author asked for eval mode or accepted it.

Eval mode needs `skill-creator` among the session's skills and subagents to
run the two versions apart, as in Claude Code. In claude.ai `skill-creator`
skips its baseline runs, so there is nothing to compare. When either is
missing, run no behavior check: print the note below and go on to step 8
with the rule inventory as the only check.

```markdown
Behavior not checked: eval mode needs skill-creator and subagents, which this
session lacks. Verify the behavior by hand: run <prompts> once with old_skill/
and once with new_skill/ and compare the results.
```

Otherwise follow `skill-creator`'s "Running and evaluating test cases" in its
case for improving an existing skill, set up as follows:

- Workspace: `evals/` in the run directory.
- The with-skill runs use `new_skill/`. The baseline runs use `old_skill/`:
  the snapshot of step 1 is the `skill-creator` snapshot, so skip its copy.
- Prompts: those of `old_skill/evals/evals.json` with its expectations as
  assertions; else every `should_trigger` prompt of `old_skill/evals.json`,
  with assertions drafted from `expected_behavior`; else two or three
  prompts the author confirms that exercise the touched rules.
- Grade every run with its grader and aggregate the benchmark. Skip its
  viewer and its iteration loop; the comparison below replaces them.

Print a table per prompt: each assertion with its result for `old_skill` and
for `new_skill`. A **deviation** is an assertion that passed for `old_skill`
and failed for `new_skill`. For each deviation name the prompt, the
assertion, and the section of `new_skill/` that governs it (heading and
`path:line`), then list the candidates whose snapshot lines fall in that
section. Deliver nothing. Ask again about those candidates only, as in step 5;
the author may also accept a deviation as intended, a recorded answer. Apply
the changed answers to `new_skill/` as a repair (step 6), run the rule
inventory again, and rerun only the deviating prompts on `new_skill/`.

An assertion that failed for `old_skill` and passes for `new_skill` is a gain:
report it, it does not block.

Done when no deviation is open.
