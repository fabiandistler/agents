# PR review acceptance record

For the maintainer closing #621 and its tickets: the evidence that the PR
review workflow behaves as specified on real pull requests. Offline tests
cannot show live token scopes, provider availability, label writes or
ruleset enforcement, so each live scenario below needs a recorded run.
How to run each step: [runbook](pr-review-runbook.md).

## Offline evidence

| Scenario | Evidence |
| --- | --- |
| Risk policy, review parser, planner, writer, workflow structure | `python3 -m pytest -q scripts/test_pr_*.py`; fixtures and fake transports only, no network. |
| Auto-merge gates: enable, keep, disable per gate; `do-not-merge` veto; human-enabled auto-merge left alone | `scripts/test_pr_auto_merge*.py`, `scripts/test_pr_publish*.py`, `scripts/test_pr_apply_auto_merge.py`. |
| State changes between assessment and write | Regression cases change the head, files, labels, comment or state; stale or closed pull requests write nothing. |

## Live scenarios

Each row is pending until the maintainer records the run URL, head SHA and
observed result in place of the pending note. All three need the workflow
merged to `main` first.

| Scenario | Status and manual step |
| --- | --- |
| Dry run on a docs pull request: all jobs green, plan shows `risk:low`, no writes | Partial, 2026-11-18, on #878. No single run shows both green jobs and a `risk:low` plan. Run https://github.com/fabiandistler/agents/actions/runs/44335933096, head `31feb92`, observed: dispatched 8 s after #878 opened; the `opened` review run shares the concurrency group `pr-review-878` and cancelled this run's `review` job; `publish` planned `risk: low`, no verdict, `auto_merge: off`, status `planned`; no labels or comments written. Run https://github.com/fabiandistler/agents/actions/runs/44336357750, head `31feb92`, observed: dispatched after the review run finished; all jobs green, assessment `risk: low`, review `pass`; the bot merged #878 at 15:30:43Z, so `publish` aborted with `pull_request_closed` and wrote nothing. A clean run needs an open low-risk pull request that neither a review run nor a merge touches during the dry run (about 60 s). |
| Throwaway docs pull request: bot arms auto-merge, adds `auto-merge:bot`, and the merge waits for `checks`, `bats`, `mermaid`, `secrets` and `pr-review/verdict` | Passed, 2026-11-18. Run https://github.com/fabiandistler/agents/actions/runs/44336062821 on #878, head `31feb92`, observed: labels `risk:low`, `review:pass`, `auto-merge:bot`, and `needs-review` because the maintainer's login opened the pull request (`_needs_review` in `scripts/pr_plan.py`); auto-merge enabled by `github-actions[bot]`, method `merge`; `pr-review/verdict` success 15:29:49Z; `mergeable_state` `blocked` at 15:30:10Z while the `pull_request` CI suite ran; latest completions `secrets` 15:28:44Z, `mermaid` 15:28:54Z, `checks` 15:30:12Z, `bats` 15:30:21Z; merged by `github-actions[bot]` at 15:30:43Z. |
| Non-docs pull request (for example a skill change): `risk:medium`, `needs-review`, sticky comment, reviewer request or assignment, no auto-merge | Passed, 2026-11-16 and 2026-11-18, on #873 (three files under `skills/llm-application-engineering/`, opened by `claude[bot]`). Run https://github.com/fabiandistler/agents/actions/runs/43833447254, head `6874239`, observed: labels `risk:medium`, `needs-review`, `review:concerns`; review requested from `fabiandistler`; sticky comment; `auto_merge: off`. The rerun on head `6687bd2` (https://github.com/fabiandistler/agents/actions/runs/43834287438) changed the verdict to `review:pass` and kept the rest; the maintainer merged by hand at 09:03:11Z. `PR_AUTO_MERGE` was still empty then, so #873 did not exercise the risk gate. Run https://github.com/fabiandistler/agents/actions/runs/44337500486 on #880 (this record, `docs/agents/`), head `95ba534`, observed: `PR_AUTO_MERGE: true` in the publish job; labels `risk:medium`, `review:pass`, `needs-review`; assigned to `fabiandistler`; `auto_merge: off`. |

Record format, one line per scenario: `run <URL>, head <sha>, observed:
<labels, auto-merge state, merge time against check completion>`.
