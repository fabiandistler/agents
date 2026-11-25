# 2026-11-25 decisions

- repo-maintenance#205 (waiting issues never start): the maintainer chose
  option 2 out of two. Option 1 was to add queue callers to repo-maintenance
  and dotfiles and bump their pin. Option 2 adds to that a claim in agents that
  promises the queue only when the caller configures one (`queue_workflow`), and
  an onboarding check that requires a queue caller next to the implementer.
  Reason given by the session: the defect sits in shared code that makes a
  promise it never checks, so a per-consumer fix leaves the next consumer
  exposed (`.claude/rules/agents-55-bug-fixing.md`). See
  [consumers without a queue caller](../problems/consumers-without-queue.md).
- The workflow changes are done in this interactive session, not by the
  implementer, because the implementer cannot write `.github/workflows/`
  ([implementer write limits](../problems/implementer-write-limits.md)).
- The session did not dispatch repo-maintenance#200 or dotfiles#79/#80 by
  hand (its own call, not the maintainer's): once the callers merge, the hourly
  queue schedule is expected to start them [inferred].
- Later on 2026-11-25, the maintainer chose option B for agents#953's queue
  check. Option A checked on every claim. Option B checks only where the
  claim would park the issue, so a disabled queue fails no run with free
  capacity. Reason: GitHub disables scheduled workflows in public repositories
  after 60 days without activity (docs.github.com, read 2026-11-25), and
  agents is public. A rework of #953 was delegated the same day.
- The same reply said "ja" to filing two issues: triage in consumer repos
  cannot read agents, and 15 dotfiles Bats tests fail locally with
  `rm: command not found`. The session read "ja" as covering both and had the
  `rm` cause diagnosed before choosing the repo.
- Triage of #954–#961, the maintainer's choice "wie empfohlen" (as
  recommended):
  - #957, #958 (with `.github/pull_request_template.md`), #960 (option 1:
    base content counts as context) and #954 (agent part, `Blocked by #957`)
    became `ready-for-agent`.
  - #955, #959 and #961 became `ready-for-human`.
  - #956 lost its upstream part to repo-maintenance#208. It has no label
    until #208 closes, because a native cross-repo dependency did not block
    its claim (run 45591673371 stopped `at-capacity`). Issue #964 covers that.
  - #957 merged the same day as PR #962.
- The same day this interactive session did #955 and #961 (agents#965) and
  carried #961 to the consumers (repo-maintenance#209, dotfiles#84). Bats in a
  4-core cloud session took 241 s serial and 81 s with `--jobs 4` [read,
  subagent report]. The first brief for #965 was refused by the auto-mode
  classifier because it planned a `--force-with-lease` push. That was not
  needed: the merged branch had been deleted on the remote and held no
  unmerged commits.
