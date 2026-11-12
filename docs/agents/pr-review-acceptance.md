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
| Dry run on a docs pull request: all jobs green, plan shows `risk:low`, no writes | Pending. Needs `CLAUDE_CODE_OAUTH_TOKEN` set (it is, for `claude.yml`); then dispatch with `dry_run: true` on an open docs-only pull request ([rollout](pr-review-runbook.md#rollout) step 2). |
| Throwaway docs pull request: bot arms auto-merge, adds `auto-merge:bot`, and the merge waits for `checks`, `bats`, `mermaid`, `secrets` and `pr-review/verdict` | Pending. Needs the observation week, the [ruleset change](pr-review-runbook.md#setup) and `PR_AUTO_MERGE=true` (rollout steps 3–5). Open the pull request while its checks still run, so decision D does not apply. |
| Non-docs pull request (for example a skill change): `risk:medium`, `needs-review`, sticky comment, reviewer request or assignment, no auto-merge | Pending. Needs the workflow merged and the secret set; any skill-content pull request after the merge serves. |

Record format, one line per scenario: `run <URL>, head <sha>, observed:
<labels, auto-merge state, merge time against check completion>`.
