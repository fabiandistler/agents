# R-Code Eval Suite for opencode

Minimal A/B harness to measure what a skill, MCP, or AGENTS.md does to the R
code that opencode generates. Each task is run twice — once with a baseline
config, once with a configured config — and graded with `lintr` + `testthat`.

## Layout

```
tasks/<id>/
  prompt.md     # what opencode is asked to do
  setup.R       # optional, runs in workdir before opencode (creates inputs)
  target.R      # optional, copied into workdir (e.g. function under test)
  tests.R       # testthat file run against the produced solution.R
configs/<name>/
  AGENTS.md     # dropped into the workdir as ./AGENTS.md before opencode runs
runs/<ts>/<config>/<task>/
  solution.R    # what opencode produced
  meta.json     # timing, exit code
  test.json     # testthat results
  lint.json     # lintr results
```

## Running

```sh
# run all tasks for both configs (default)
./run.sh

# only one task, only one config
./run.sh --task 03-pkg-state-env --config with-skill

# replay a previous run's scoring without invoking opencode
./run.sh --score-only runs/2026-05-02_19-30-00
```

Then `Rscript score.R runs/<ts>` prints a markdown comparison table and writes
`results.csv`.

## Wiring opencode + your skill

The runner is opencode-agnostic on purpose: it just sets up a workdir, drops
`AGENTS.md` into it, and shells out to `opencode run "<prompt>"`. How skills
get loaded is up to you — typical options:

- Edit `configs/with-skill/AGENTS.md` to inline-reference the skill, e.g.
  `Follow the skill at ~/.agents/r-package-dev/SKILL.md`.
- Or load the skill via your global opencode config and leave `AGENTS.md` as
  a bare opt-in marker.

`configs/baseline/AGENTS.md` is the control. Keep it minimal — anything in it
is something the skill cannot get credit for.

## Adding a task

1. `mkdir tasks/05-foo && cd tasks/05-foo`
2. Write `prompt.md` (what opencode should produce, in which file)
3. Write `tests.R` — `testthat` expectations against `solution.R`
4. Optional: `setup.R` to create input data, `target.R` to ship a fn-under-test

## Mock mode (for testing the harness itself)

If `OPENCODE_MOCK_DIR` is set, the runner copies fixtures from
`$OPENCODE_MOCK_DIR/<config>/<task>/solution.R` instead of calling opencode.
Useful for verifying `score.R` end-to-end without burning tokens.
