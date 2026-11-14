# What the PR review model sees

- 2026-11-14, at `fabiandistler/agents@origin/main` before PR #826: the review model never saw a PR's comments, so it could not see rebuttals. `scripts/pr_github.py:342-344` fetched them, but only `scripts/pr_comment.py:115-127` used them, to find the sticky comment. The payload (`scripts/pr_review.py:210-297`) held title, body, files, base files, diff and linked issues. Linked issues carried only title and body, not the Agent Brief. `scripts/pr_review_prompt.md:7-8` still listed comments as input. Effect: rebutted findings came back on #815, #809 and #800. Filed as #822; the maintainer chose option 1 (trusted comments plus brief); PR #826 merged 2026-11-14 11:37 UTC.
- 2026-11-14: `scripts/pr_review_sanitize.py:14-15,50-56` deleted HTML comments from the diff, so factory bot markers were reviewed blind and every such PR was marked Partial (e.g. #809 at `4edec95`). Filed as #823; the maintainer chose option 1 (neutralize in code diffs); implementer PR #832 opened 2026-11-14.
- 2026-11-14 observation: every agent PR got `review:concerns`. On #815, 2 of 5 findings held up. `concerns` does not block a merge: `pr-review/verdict` is `success` for pass, concerns and block (`docs/agents/pr-review-verdict-status.md`).

Related: [implementer write limits](implementer-write-limits.md).
