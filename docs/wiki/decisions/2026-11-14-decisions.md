# 2026-11-14 decisions

Decided by the maintainer in the chief-of-staff session on 2026-11-14:

- #802 (closing keyword in quoted text): option 1: a "no issue" body must declare no closing. Brief: #802 comment 6873776016. PR #821 merged.
- repo-maintenance#150: `--plugin-sha` is required wherever the plugin cannot determine its commit, with a clear error. `update` stays as it is, and jobs.md documents `copy` for absent assets. PR repo-maintenance#154 merged; it also reads the commit from a commit-named cache folder or a git checkout, an addition the subagent made.
- #822: option 1 (trusted PR comments and the Agent Brief go into the review payload). #823: option 1 (neutralize HTML comments in code diffs). They run one after the other because both change `scripts/pr_review.py`.
- Reconfirmed 2026-11-14 ~11:15 UTC: #790, #792, #793 and #801 are done in interactive sessions, not by the implementer. Between 10:19 and 10:30 UTC they had been labelled `ready-for-agent` under the maintainer's account; all four runs ended at once, with 1 turn, $0 and `is_error`, during a usage-limit window. The labels were set back to `ready-for-human`.
- #764 done: ruleset `default` requires `checks`, `mermaid`, `secrets`, `bats` and `pr-review/verdict` (source GitHub Actions); the issue was closed 2026-11-14. #763: the maintainer created the event policy. A check is scheduled for 2026-11-16 17:40 UTC (`trig_0159BdYMZ82Lzb9o2aTGk19Y`), during the brownout.
- Cloud sessions started 2026-11-14: #793 (`session_0154VwoYMn9xz8tdgNXf2Dbp`), #790 (`session_0154VwoZ6pmYe1VCKvXiUYHJ`, PR #828), #792 (`session_0154VwoYMXmq9WKKCrGaRi8g`, PR #831, merged).

Related: [2026-11-13 triage decisions](2026-11-13-triage-decisions.md).
