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
- 2026-10-19: #537, #538 and #534 merged; all PRs of this session landed.
  SessionStart hook cold-start time still unmeasured.
- 2026-10-20: #540 (router-reference check, 63 refs fixed), #541 (prek
  hooks regenerate skills.json/routers/.claude on commit; ~0.5 s per
  commit) and #542 (runnable commands in repo-status, release-pr,
  MAINTENANCE.md; check_gh_graphql scans root *.md) merged.
- 2026-10-20: SessionStart hook cold-start time still unmeasured: the
  container resumed with yesterday's cache, so no cold run happened.

## 2026-11-11 factory brakes

See [expansion order](decisions/2026-11-11-factory-expansion-order.md).

- 2026-11-11: State of the brake PRs when read that evening:
  - #781 (refs #763, docs only) merged by the maintainer, merge commit
    `fabiandistler/agents@7005ffc`. #763 stays open: the Actions event
    policy is a manual repository setting, due before the brownout of
    2026-11-16 16:00 UTC.
  - #785 (closes #770) open, labelled `risk:high` and `review:pass`.
  - #791 (refs #764) open; GitHub reported it as not mergeable
    (`mergeable_state` dirty) after #781 merged, so it needs updating
    against main first.
- 2026-11-11: Order of the manual steps around #791, from the
  chief-of-staff session; steps 2–4 follow #791's own manual step:
  1. Event policy allowing `pull_request_target` for `pr-review.yml`
     (#781's manual step). Without it, from 2026-12-02 or during a
     brownout, no review run reports, so a required verdict would hold
     every merge.
  2. Merge #791.
  3. Wait until a PR shows the `pr-review/verdict` status; GitHub offers
     only checks that reported in the last seven days.
  4. Require `bats` and `pr-review/verdict` in the `default` ruleset, then
     push to or re-dispatch the review for each PR still open.
- 2026-11-11: The rollout tickets (#786 and children, dotfiles#61,
  repo-maintenance#153) wait until #763, #764 and #770 are done.
