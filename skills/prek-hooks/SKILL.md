---
name: prek-hooks
category: workflow
description: Set up prek git hooks in Python/R repos — detects project type and assembles a pinned pre-commit config from fragments.
environments: coding
metadata:
  version: "1.0"
---

# Prek Hooks

Set up Git hooks with [prek](https://prek.j178.dev/) as the runner, a single-binary replacement for `pre-commit` without a Python runtime dependency. The fragments under `references/fragments/` are the single source; the setup script assembles `.pre-commit-config.yaml` from them based on detected project type. There are deliberately no two finished configs for Python and R that could drift apart.

## When to use

- A Python repo, an R repo, or a mixed repo needs Git hooks from scratch.
- An existing `.pre-commit-config.yaml` should be rebuilt from pinned fragments after drift.
- Commits need formatting and linting on every commit: ruff and ty for Python, air and lintr for R, plus generic whitespace and file checks.
- A pure R repo should avoid a Python virtualenv just for whitespace checks.

## Workflow

1. **Check prerequisites.** `prek` is in PATH (`uv tool install prek`), the target is a Git repo, and for the `lintr` hook a system `Rscript` exists. Without `Rscript` the lintr hook fails at run time.
2. **Pick the base.** Default is compat (`references/fragments/base-compat.yaml` via `pre-commit/pre-commit-hooks`), so the config also runs under original pre-commit while prek uses its native implementations. Use `--builtin` for `references/fragments/base-builtin.yaml` (`repo: builtin`) in pure R repos to skip the clone and Python fallback; that config is prek-only.
3. **Run the setup script from anywhere inside the target repo.** Flags and exit codes are in `--help`. It moves to the repo root itself, refuses to overwrite an existing `.pre-commit-config.yaml` or a `prek.toml` unless `--force` is given, and detects the project type (`pyproject.toml`, `setup.py`, or tracked `*.py` files mean Python; `DESCRIPTION` or tracked `*.R`/`*.r` files mean R). With neither present it stops.
    ```bash
    references/setup-hooks.sh
    references/setup-hooks.sh --builtin
    references/setup-hooks.sh --force
    ```
4. **Let the script assemble and install.** It concatenates the base fragment with `references/fragments/python.yaml` and/or `references/fragments/r.yaml` into `.pre-commit-config.yaml` with a date header, then runs `prek update --cooldown-days 7` and `prek install`.
5. **Format once in its own commit.** The script intentionally does not run the first pass. Run it manually; it reformats the whole repo and produces a large diff that does not belong in the next feature commit.
    ```bash
    prek run --all-files
    ```

## Decisions

| Decision | Reason |
|---|---|
| air for R formatting, not styler | air is a binary and needs neither R nor `renv`; the styler path via `lorenzwalthert/precommit` runs through a renv environment |
| lintr in addition to air | linting stays R-bound, there is no binary replacement |
| ruff-check before ruff-format | `--fix` results still get formatted |
| ty as typechecker, not mypy | uv-native and fast |
| Compat path as default | the config also runs under original pre-commit; prek still uses its native implementations |

## Known issues

- `repo: builtin` is prek-only. With `--builtin` the config no longer runs under pre-commit. Most useful in pure R repos, where otherwise a Python environment exists only for whitespace checks. Available IDs per prek version: `prek util list-builtins -v`.
- ty is at 0.0.x. Breaking changes between patch versions are expected. A mypy replacement block is included in `references/fragments/python.yaml`.
- `lorenzwalthert/precommit` publishes only development tags (`v0.4.3.90xx`). The pin is the newest one as of 2026-09-26; `prek update` during setup moves it forward.
- ruff ≥ 0.16 enables 413 rules by default (up from 59). In a repo without its own rule selection the first `prek run --all-files` floods it with findings; the setup script warns when it finds no ruff config. Pin e.g. `[tool.ruff.lint] select = ["E", "F", "I", "B", "UP"]`.
- lintr is the expensive hook. renv restore on the first run, and an R version change invalidates the cache. `stages: [pre-push]` is prepared in the fragment when the commit path is too slow.
- The compat path is not setup-free. prek clones `pre-commit-hooks` and creates a venv fallback even when execution runs natively.

## References

- `references/setup-hooks.sh` — detection, assembly, pinning, installation; run with `--help` for flags.
- `references/fragments/base-compat.yaml` — generic hooks, pre-commit compatible (pinned `v6.0.0`).
- `references/fragments/base-builtin.yaml` — same hooks as prek builtins, prek-only.
- `references/fragments/python.yaml` — ruff-check `--fix`, ruff-format, ty (pinned `v0.16.9`, `v0.0.84`, verified 2026-09-26).
- `references/fragments/r.yaml` — air-format, lintr (pinned `0.11.0`, `v0.4.3.9032`, verified 2026-09-26).
