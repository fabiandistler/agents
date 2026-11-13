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

- 2026-11-11: State of the brake PRs when read that evening
  (*superseded 2026-11-12 for #785 and #791, see below*):
  - #781 (refs #763, docs only) merged by the maintainer, merge commit
    `fabiandistler/agents@7005ffc`. #763 stays open: the Actions event
    policy is a manual repository setting, due before the brownout of
    2026-11-16 16:00 UTC.
  - #785 (closing #770) open, labelled `risk:high` and `review:pass`.
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

## 2026-11-12 brakes merged, probe done

- 2026-11-12 (supersedes the 2026-11-11 state of #785 and #791): merge
  times read with the PR API, all merged by the maintainer:
  - #781 merged 2026-11-11 20:19 UTC (`fabiandistler/agents@7005ffc`).
  - #785 merged 2026-11-11 21:00 UTC (`fabiandistler/agents@218c23c`).
  - #791 merged 2026-11-12 08:38 UTC (`fabiandistler/agents@ea645d3`),
    after "Update branch" (`4778eaf`); this was step 2 of the order above.
  - #795 merged 2026-11-12 08:38 UTC (`fabiandistler/agents@9242f8d`),
    after "Update branch" (`7c0353b`).
- 2026-11-12: #796 (token probe, "do not merge") closed without merging
  at 11:36 UTC. dotfiles#62 (probe caller) merged at 11:31 UTC;
  dotfiles#63 (probe removal) open (*superseded 2026-11-13, see below*).
  Result: see
  [cross-repo token exchange](problems/cross-repo-token-exchange.md).
- 2026-11-12: still manual:
  - the Actions event policy for `pr-review.yml` (#763, #781's manual
    step), due before the brownout of 2026-11-16 16:00 UTC;
  - once a PR shows the `pr-review/verdict` status, adding `bats` and
    `pr-review/verdict` to the `default` ruleset (steps 3–4 above).

## 2026-11-13 triage: agent queue and manual steps

See [2026-11-13 triage](snapshots/2026-11-13-triage.md) and
[triage decisions](decisions/2026-11-13-triage-decisions.md).

- 2026-11-13: agent queue, one implementer run at a time
  (`MAX_WORKING_RUNS=1`), order set by the chief-of-staff session:
  1. #783: labelled `ready-for-agent` 20:20 UTC; run 43500665465 in
     progress when read.
  2. #782
  3. #787
  4. #784
  5. #769 (script-only scope)
  6. #789 and #788, after #787 is closed.

  The session sets the next label when a run ends, until the queue from
  #801 exists.
- 2026-11-13: not in the agent queue: #797, #793, #790 and #767 go to
  interactive sessions; sessions for #797 and #767 started 20:33 UTC.
- 2026-11-13 (supersedes the 2026-11-12 "open" for dotfiles#63): dotfiles#63
  merged 2026-11-12 at 11:40 UTC.
- 2026-11-13: manual steps still open, with deadlines (extends the
  2026-11-12 list):
  1. Actions event policy for `pr-review.yml` (#763), before the brownout
     of 2026-11-16 16:00 UTC; default block from 2026-12-02.
  2. Add `bats` and `pr-review/verdict` to ruleset 18264711 (#764), after
     step 1. On 2026-11-13 the ruleset required only `checks`, `mermaid`
     and `secrets`. `pr-review/verdict` last reported 2026-11-12 11:46 UTC
     on #799's head, so the picker offers it until about 2026-11-19
     11:46 UTC unless the status reports again.
  3. Dependabot runner-type setting (repo-maintenance#142, dotfiles#52);
     a scheduled check runs 2026-11-15 09:07 UTC.
  4. Decisions without a fixed date: #765 before `PR_AUTO_MERGE=true`;
     repo-maintenance#151 before its review on 2026-12-01.
