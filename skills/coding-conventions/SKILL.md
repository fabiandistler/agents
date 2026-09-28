---
name: coding-conventions
category: workflow
description: Standing coding conventions — Python (uv, ruff), R (data.table, namespacing), PRs, comments, bug-fix limits, agent pipelines — for chats without a global instruction file.
environments: chat
targets: claude
metadata:
  version: "1.0"
---

# Coding conventions

The same rules `install.sh --instructions` writes into the global instruction
file of Claude Code, Codex CLI and opencode, packaged for surfaces that have no
such file: Claude Desktop, claude.ai, Cowork, and Langdock.

## When to use

- Writing, reviewing, or refactoring Python or R code in a chat.
- Planning a branch, commit, or pull request.
- Designing modules, an agent pipeline, or a script an agent will run.
- Fixing a bug that has already resisted more than one attempt.

If these rules are already part of your standing instructions (a managed
`agents instructions` block in a global instruction file), they are in context
already — apply them and do not reload this file.

Apply every rule in the sections below. `[rule]` items are hard constraints.
Everything from here to the end of the file is generated from `instructions/`
by `scripts/build_conventions_skill.py` — edit the fragments, not this file.

<!-- BEGIN generated:instructions -->

## Coding standards

- [rule] All text in code, comments, and README files should be in English

## Module design

Cut modules by shared knowledge, not by pipeline phase.

- When a file or function carries a phase name (`load_`, `clean_`, `transform_`, `save_`, `init_`), check whether format or schema knowledge lives in two places. If it does, merge them — execution order is an implementation detail, not a module boundary.
- A wrapper that passes its arguments through unchanged is not a layer. Remove it, or give it an abstraction of its own.
- Add a new layer only when it brings its own abstraction, never for technical reasons.
- Let dependencies point from specific to general only. General code must not know about any specific use case.

## Python

- [rule] Use uv for Python package development
- [rule] Use ruff for Python formatting and linting
- **New project baseline**: when setting up a new Python project with uv, add this dev group and config without asking:

  ```sh
  uv add --dev ruff ty pytest pytest-cov pip-audit
  ```

  ```toml
  [tool.ruff.lint]
  extend-select = ["S"]

  [tool.coverage.run]
  branch = true
  ```

  Why (keep this list when trimming the rule; the non-obvious choices get undone without it):
  - `extend-select`, never `select`: since ruff 0.16 the default set (413 rules) already covers `UP`, `DTZ` and `B`, which catch what models copy from training data (`datetime.utcnow()`, `typing.List`). `select` would replace that default.
  - `S` adds the bandit rules, so bandit itself is not needed. The default has only 3 of them. The hardcoded-secret rules (S105–S107) match on variable names, so a real key under an innocent name still gets through. Keep reviewing secrets by eye.
  - `branch = true` shows untested error paths that happy-path code skips.
  - `pip-audit` finds known vulnerabilities in dependencies.
  - `ty`: same checker the prek hooks run. It is still beta. If it breaks on a library it does not support yet, fall back to `mypy` with `[tool.mypy] strict = true`.

## R

- [rule] Use message() or warning() for console output, not print() and cat()
- [rule] cat() should only be used in print() methods
- [rule] Use {data.table} instead of {dplyr}
- [rule] Use tidyverse style guide and tidyverse design principles
- [rule] set.seed() should not be used. Use withr::local_seed() instead.
- **Namespace** — no `library()` or `require()` in `R/`; always call foreign functions as `package::fun()`; declare dependencies under `Imports`, not `Depends`; reach for Suggests only behind `requireNamespace(..., quietly = TRUE)`
- **State and persistence** — keep session state in a `the` environment in `R/aaa.R`; persist across sessions with `tools::R_user_dir()`; store credentials via `keyring`; never write to the home directory (a CRAN violation)
- **API design of exported functions** — applies when writing a new exported function or changing its signature:
  - Several options: an enum vector as the default plus `match.arg()`. Use a boolean only when the argument name speaks for itself.
  - Once a function reaches five to seven arguments, group related optional arguments into a `*_options()` object.
  - Booleans that depend on each other (the `perl`/`fixed` antipattern of base R's regex functions): use a strategy constructor instead of a flag pair.
  - Functions called for their side effect return `invisible(x)`, never `NULL`.
  - From the third identical `stop()` string in a package on, add a `stop_*()` constructor with its own error class; tests then assert via `class=`, not via regex.
  - Validate with `stopifnot()`, or with `checkmate` for user-facing functions. Use `rlang` only where error classes require it.
- **Domain model in R6** — applies when business rules or amounts with a unit live in bare functions or vectors. Not for CRUD code in supporting subdomains, where Transaction Script stays the default:
  - Aggregate root as an R6 class, private fields, access only through methods.
  - Call `private$validateInvariants()` with `checkmate` after every state change.
  - Value object: immutable R6. Mutating methods return a new instance.
  - A value object needs `equals()`. It has no ID, no repository and no table of its own.
  - Reference foreign aggregates by ID only, never embed them as objects.
  - One package equals one bounded context.

## Development best practices

- [rule] Always ask to create a new feature branch before implementing changes on main.
- [rule] Always connect issues with PRs.
- [rule] Always run the test suite before pushing a PR.
- [rule] Always run available checks, linters, stylers, and formatters before pushing a PR.
- [rule] Keep each diff single-purpose.
- [rule] Put refactoring in its own commit.
- [rule] Include tests with the change they cover.

## Bug fixing

- Count failed fix attempts. After the third, stop: if each fix exposed new coupling elsewhere, the design is the bug — list attempts, ask before fix #4.

## Code comments

Do not add new code comments when editing files.
Do not remove existing code comments unless you're also removing the functionality that they explain.
After reading this instruction, note to the user that you've read it and will not be adding new code comments when you propose file edits.

## Code review conventions

- Files under test fixtures / `fixtures/` / `bad_examples/` are INTENTIONALLY broken — do not flag their contents as bugs in reviews
- Always check the path/purpose of a file before reporting lint or correctness issues

## Agent pipelines

- Whoever finds a problem does not grade it. Grading runs as its own step with fresh context.
- Hand the grader the scale verbatim, with anchored levels (what exactly 0, 25, 50, 75 and 100 mean). No paraphrase, no free-form "confidence: high".
- The threshold applies before writing, not after. Anything below it appears nowhere — not even as "uncertain, but worth mentioning".
- Silence is a valid output. Produce a no-findings report only when someone explicitly expects one.
- The false-positive catalogue belongs in the finder prompt, not the grader's. It enumerates what is never reported: pre-existing issues, anything a linter, typechecker or compiler already catches, nitpicks, anything outside the change.
- Split parallel finders by evidence source, not by topic. Two agents on the same source produce correlated errors, not coverage.
- Run classification and grading on the cheap model, the actual analysis on the strong one.
- **Writing into external systems**:
  - Re-check the entry condition immediately before the write, not only at the start. The pipeline runtime sits between the first check and the write, and the state can have changed since.
  - A state file and a re-check cover different failure modes: the file prevents repetition across runs, the re-check catches a state change within a run. Both are needed.
  - If the re-check fails, abort with no side effect and one log line naming the reason.
  - An unattended LLM step never holds a write credential; it emits a patch artifact, a separate model-free step validates and publishes it.
  - Enforce scope outside the prompt: check every changed path against an anchored allowlist, including untracked files (`git ls-files --others --exclude-standard`), and stage only that list.
  - Agent self-edits (prompt, workflow, references) pass the same allowlist and human PR; an edit loosening tools, tokens or permissions is reported, never applied.

## Scripts an agent runs

Applies to any executable an agent invokes: skill or plugin scripts, hook commands, CI helpers.

- Never read from an interactive prompt. Agents run non-interactive shells; a TTY prompt hangs the session until timeout. Take every input as a flag, env var, or stdin. On a missing required input, exit non-zero naming the flag and its allowed values.
- `--help` is the agent's only interface documentation — one usage line, the flags, two examples. It is also context cost: keep it under ~25 lines.
- Distinct exit code per failure class, documented in `--help`, so the caller can branch without parsing prose. Data to stdout, diagnostics to stderr.
- One named verb per write, narrowest stable ID, `--dry-run` first; never hide writes in `fix`/`auto`/raw.
- Secrets from env or config, never a flag (shell history, `ps`); never echo them, not in `--json` errors.
- Smoke-test the installed command from `/tmp`, not the source folder.
- Bound the output. Harness output is truncated past roughly 10–30k characters, silently. Default to a summary; offer `--output FILE` and `--offset` for the rest.

<!-- END generated:instructions -->
