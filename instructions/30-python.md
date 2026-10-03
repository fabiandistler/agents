---
title: Python
targets: all
---

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

  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["S101"]

  [tool.coverage.run]
  branch = true

  [tool.uv]
  exclude-newer = "7 days"
  ```

  Why (keep this list when trimming the rule; the non-obvious choices get undone without it):
  - `extend-select`, never `select`: since ruff 0.16 the default set (413 rules) already covers `UP`, `DTZ` and `B`, which catch what models copy from training data (`datetime.utcnow()`, `typing.List`). `select` would replace that default.
  - `S` adds the bandit rules, so bandit itself is not needed. The default has only 3 of them. The hardcoded-secret rules (S105–S107) match on variable names, so a real key under an innocent name still gets through. Keep reviewing secrets by eye. `S101` flags `assert`, which pytest tests are made of, hence the `tests/**` ignore.
  - `branch = true` shows untested error paths that happy-path code skips.
  - `pip-audit` finds known vulnerabilities in dependencies.
  - `exclude-newer = "7 days"` is a dependency cooldown: the resolver ignores uploads younger than a week, so a malicious release is usually yanked before it can land. It lives in `pyproject.toml` because cloud sessions never read a user-level `uv.toml`. Relative durations need uv ≥ 0.9.17; check `uv --version` first and leave the line out on an older uv, which fails to parse it. When a fix needs a package newer than that, opt that one package out: `uv lock --exclude-newer-package "<package>=false"`.
  - `ty`: same checker the prek hooks run. It is still beta. If it breaks on a library it does not support yet, fall back to `mypy` with `[tool.mypy] strict = true`.
