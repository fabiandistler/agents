# A dry run in the review's concurrency group

- 2026-11-18, at `fabiandistler/agents@b101adc`: a manual `pr-review` dispatch shares the concurrency group `pr-review-<n>` with the review runs of the same pull request (`.github/workflows/factory-pr-review.yml:93-97`, `cancel-in-progress: true`).
- 2026-11-18, on #878:
  - The dry run [44335933096](https://github.com/fabiandistler/agents/actions/runs/44335933096) was dispatched at 15:27:55Z, 7 s after the pull request opened (15:27:48Z).
  - The `opened` run [44336062821](https://github.com/fabiandistler/agents/actions/runs/44336062821) was created at 15:28:36Z and cancelled the dry run.
  - The same `opened` run then armed the bot's auto-merge, which is row 2 of the acceptance record.
  - The dry run's `publish` still ran (`always()`). Its job log shows `review_status: unavailable` and `verdict: null`, so the review was rebuilt without a model token. It planned the following, but wrote none of it, being a dry run:
    - `review:unavailable`;
    - a comment blaming a missing provider;
    - `pr-review/verdict` with state `error`.
- 2026-11-18, inferred, not observed: a dry run dispatched during a real review cancels that review, and the cancelled run then writes exactly that plan.
  - The `error` status fails the required check.
  - Recovery: dispatch with `"dry_run": "false"`.
- 2026-11-18: until #882 gives dry runs their own group, wait for the review run of the head to finish before dispatching a dry run.

Related: [PR review acceptance record](../../agents/pr-review-acceptance.md), [missing pull_request runs](missing-pull-request-runs.md).
