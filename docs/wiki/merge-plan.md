# Merge plan

- 2026-10-19: Open PRs from this session and their order constraints:
  - #534 wiki — independent.
  - #535 evals + strict `check_evals` — conflicts with #537 on CI files;
    whichever merges second moves `check_evals.py --strict` into the
    `evals)` case of `scripts/check_all.sh`.
  - #536 command-skill check — waits on the user's call on
    `pypet-snippets` (restore `disable-model-invocation` vs. make it `auto`;
    the flag was removed deliberately in `36c008c`).
  - #537 `scripts/check_all.sh` as the single check list.
  - #538 SessionStart hook — after #537 (installs its requirements file);
    fetches Go via proxy.golang.org because cloud sessions block go.dev.
    Startup time in a fresh container not yet measured.
- Side effect noted 2026-10-19: testing #538 ran `prek install` in the main
  checkout, so commits there now run the pre-commit hook.

## Updates

- 2026-10-19: #535 merged. #537 took main in via merge commit `d8da6c6`;
  `check_evals --strict` now runs in the `evals)` case of `check_all.sh`;
  ADR-0006 got a dated status note (`fdb027d`).
- 2026-10-19: #536 merged by the user with the commit restoring
  `disable-model-invocation: true` on `pypet-snippets`, i.e. it stays a
  command skill. Read as the user's answer to the open question.
