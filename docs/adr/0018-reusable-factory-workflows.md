# ADR-0018: The factory's tasks are reusable workflows that other repositories call

## Status

Accepted by the maintainer in the parent spec #786 (2026-11-11); recorded
here on 2026-11-14. Extends [ADR-0011](0011-pr-review-merge-exception.md),
[ADR-0013](0013-automated-issue-triage.md) and
[ADR-0014](0014-agent-runs-in-github-actions.md), which describe the factory
as running in this repository only; their decisions stand for this
repository. ADR numbers 0015–0017 are reserved for the Rework (#782), Fix
(#783) and Retro (#784) tasks
([decision log](../wiki/decisions/2026-11-11-new-factory-tasks.md)).

## Context

The factory (implementer, PR review, issue triage, triage label) runs in
`.github/workflows/` of this repository and works on this repository only.
The maintainer wants the same tasks in `fabiandistler/dotfiles` and
`fabiandistler/repo-maintenance` (#786), without a second copy of the
scripts and their brakes in each repository.

Facts below were checked on 2026-11-11 for #786 unless another date is
given:

- A workflow with `on: workflow_call` can be called from another
  repository, and a private repository may call a workflow in a public one.
  In the called workflow the `github` context belongs to the caller, the
  calling job's `permissions` cap the called workflow, which can only
  downgrade them, and runner billing follows the caller
  ([Reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)).
- Pinning the called workflow to a full commit SHA is "the safest option"
  ([Reuse workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)).
- `secrets: inherit` is documented only for callers in the same organization
  or enterprise
  ([workflow syntax, `jobs.<job_id>.secrets.inherit`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretsinherit)).
- The `job` context carries `job.workflow_repository` and `job.workflow_sha`,
  the repository and commit of the workflow file the job runs from
  ([Contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)).
  There is no `github.job_workflow_sha` context; `job_workflow_sha` exists
  only as an OIDC claim
  ([OIDC reference](https://docs.github.com/en/actions/reference/security/oidc),
  [OIDC with reusable workflows](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows)).
- Both targets are private repositories on a plan without rulesets: the
  rulesets API answers "Upgrade to GitHub Pro or make this repository
  public" (checked 2026-11-11, unchanged 2026-11-13).

## Decision

Each task is an `on: workflow_call` workflow in this repository. This
repository's own workflows call them, and each target repository holds thin
callers:

| Task | Reusable workflow (proposed) | Caller triggers | Calling job's permissions |
| --- | --- | --- | --- |
| implementer | `factory-implementer.yml` | `issues: labeled`, `workflow_dispatch` | `contents: read`, `actions: read`, `id-token: write` |
| PR review | `factory-pr-review.yml` | `pull_request_target`, `workflow_dispatch` | `contents: write`, `pull-requests: write`, `issues: write` |
| issue triage | `factory-issue-triage.yml` | `issues: opened, labeled`, `issue_comment`, `workflow_dispatch` | `contents: read`, `issues: write` |
| triage label | `factory-triage-label.yml` | `issues: opened` | `issues: write` |

The permissions are each task's minimum from #786. Because the calling job
caps the called workflow, a caller that grants less breaks the task, and one
that grants more gives the called workflow nothing it does not ask for.

- **Callers** pin the reusable workflow to a full commit SHA and pass
  `CLAUDE_CODE_OAUTH_TOKEN` by name under `secrets:`, not with
  `secrets: inherit`, which is documented only within an organization or
  enterprise.
- **Script access.** A reusable workflow checks out the caller, so the
  factory's scripts are not in the workspace. Each job makes a second
  checkout of `job.workflow_repository` at `job.workflow_sha` into a
  directory outside the workspace and runs the scripts from there. The
  scripts then match the pinned workflow file exactly.
- **Claude GitHub App.** The App is installed per target repository. The
  OIDC claims the action exchanges (`repository`, `workflow`, `ref`)
  describe the caller, so the App installation token reaches the target
  repository only, as ADR-0014 states for this repository.

### Token exchange: settled by the probe of 2026-11-12

anthropics/claude-code-action#443 reported
`401 … Workflow validation failed` from the token exchange for a
cross-repository reusable workflow. The probe ran on 2026-11-12: dotfiles run
[43209973289](https://github.com/fabiandistler/dotfiles/actions/runs/43209973289),
a `workflow_dispatch` with the caller on dotfiles `main`, called
`fabiandistler/agents/.github/workflows/token-probe.yml@cacc67a` and logged
"OIDC token successfully obtained" and "App token successfully obtained"
(#786 comment 6822505952; same record in
[cross-repo token exchange](../wiki/problems/cross-repo-token-exchange.md)).
Probe pull requests: #796 (closed unmerged), dotfiles#62 (the caller,
merged), dotfiles#63 (its removal, merged 2026-11-12).

- **Default-branch rule.** The exchange checks that the *calling* workflow
  file exists, with identical content, on the caller's default branch.
  Sources: the 401's own text and the #443 thread (a collaborator on
  2025-08-12, a reporter on 2026-01-19), as quoted in #786 comment
  6806728845. So each caller is merged to its target's default branch before
  its first run, and a caller changed on a branch (a pin bump in a pull
  request, a dispatch from a feature branch) gets no App token until merged.
  Only the positive case was observed: the first attempt (run 43096185342,
  2026-11-11, caller on a feature branch) never started because of an
  Actions stall and shows nothing.
- **Still unverified: the App token's rights inside the target.** The
  probe's only checkout is a plain `actions/checkout` of the caller with the
  job's `GITHUB_TOKEN` (`.github/workflows/token-probe.yml:28` at `cacc67a`,
  the head of the closed #796), and its one `gh api` call was refused by the
  model's permission rule (`permission_denials_count: 1`). Whether the App
  token can check out the target, push a branch, open a pull request,
  comment and label there is unknown. The first implementer run in dotfiles
  (#790, then dotfiles#61, whose first `ready-for-agent` ticket is a trivial
  one) settles it before real tickets run there.

### Fallback

Recorded, not needed after the probe: pass `github_token` explicitly with
the job's `GITHUB_TOKEN`. It skips the exchange, but comments then come from
`github-actions[bot]`, and its pushes and pull requests start neither CI nor
the PR review. That is why ADR-0014 rejected this option for this repository
(`docs/adr/0014-agent-runs-in-github-actions.md:65-67`). #786 comment
6806728845 (2026-11-11) names it as the fallback this ADR records, and #786
comment 6822505952 (2026-11-12) names it again and finds it not needed. No
dedicated-App fallback is recorded.

### Brakes in target repositories

- Both targets are private on a plan without rulesets, so there are no
  required checks. The maintainer merges only on green, and a push guard
  (#789) stops agent pushes to the default branch. ADR-0014's other brakes
  (the prompts' hard limits, the PR merge guard, the automated PR review,
  the human merge) apply unchanged.
- If a target becomes public, rulesets become available, and
  `pull_request_target` needs an event policy: GitHub blocks it by default
  from 2026-12-02
  ([changelog 2026-11-02](https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2/)).

### Billing and capacity

- **Billing.** Runner minutes are billed to the caller's repository. The
  private targets draw from the owner's included compute usage; public
  repositories are free on standard runners
  ([GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
- **Capacity.** `MAX_WORKING_RUNS` counts per repository
  (`scripts/implementer_capacity.py:18`; the runs it counts are listed per
  repository at `scripts/agent_run_capacity.py:110`), so three repositories can run three implementers
  on one Claude subscription at once. Accepted: one implementer per
  repository keeps each repository's branch and PR queue serial, which is
  what the limit protects. Subscription limits are shared anyway with
  interactive use, the PR review and the triage (ADR-0014). If three
  parallel runs hit the limits, a cross-repository count is a follow-up,
  not part of this decision.

## Considered options

- **Copy the scripts into each repository.** Rejected: the brakes drift
  between copies.
- **A composite action per task.** Rejected: a composite action cannot hold
  jobs, and the PR review's split into separate jobs with separate
  credentials (ADR-0012, ADR-0013) needs jobs.
- **Required workflows or organization rulesets.** Not available to a
  personal account.
- **Reusable workflows.** Chosen.

## Consequences

- A change to a reusable workflow reaches a target only when its caller's
  SHA pin is bumped and, by the default-branch rule, merged there.
- The risk path rules in `scripts/pr_risk.py` are written for this
  repository. In targets they are advisory, because auto-merge
  (ADR-0011) stays off there.
- The implementer's working-run count matches its job by its plain name or
  as `<caller job> / <name>` (`scripts/implementer_setup.py:48`), and lists
  the runs of the caller's workflow file from `--workflow-file` or
  `GITHUB_WORKFLOW_REF` (#788).
- The second checkout makes every job depend on reading this public
  repository from a private caller (open question 3).

## Open questions

Numbered as in #786's "Not verified" list.

1. **Token exchange from a cross-repo reusable workflow.** Settled
   2026-11-12 for dotfiles (run 43209973289, above). Still open: the App
   token's rights in the target, settled by the first implementer run in
   dotfiles (#790, dotfiles#61); and repo-maintenance, which has not run the
   exchange, settled by its own first run (repo-maintenance#153).
2. **Whether an event policy's workflow file targeting matches the caller's
   path or the called workflow's path.** Open. Matters only if a target
   becomes public; settled by a live check before that.
3. **Whether `actions/checkout` of the public `agents` repository works with
   a private caller's `GITHUB_TOKEN`.** Open: the probe checked out only the
   caller. The first reusable-workflow run in a target that makes the second
   checkout settles it.
4. **The job name a reusable job shows in the Actions jobs API.** Settled
   2026-11-14: `<caller job> / <called job>`, each by its display name.
   python/cpython run 43566160543's jobs API lists `Docs / Doctest` for
   caller job `Docs` and called job `Doctest` (read 2026-11-14); run
   43209973289 listed `probe / probe` (read 2026-11-13). #788 adapted
   `implementer_claim.py`.
5. **Whether Dependabot (`github-actions`) bumps
   `uses: owner/repo/.github/workflows/<file>@<sha>` in callers.** Open,
   settled by the first Dependabot run after a caller lands. Dependabot
   update jobs on the private targets have never run
   ([Dependabot on private repos](../wiki/problems/dependabot-private-repos.md),
   2026-11-10, cause not verified), so pin bumps may stay manual there.
6. **App installation and secrets of the targets.** Settled for dotfiles
   (2026-11-12: the probe's exchange succeeded and its model step ran on
   `CLAUDE_CODE_OAUTH_TOKEN`). Open for repo-maintenance, settled by its own
   first run (repo-maintenance#153).

## Sources

- [Reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) (checked 2026-11-11)
- [Reuse workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) (checked 2026-11-11)
- [Contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts) (checked 2026-11-11)
- [OIDC reference](https://docs.github.com/en/actions/reference/security/oidc) and [OIDC with reusable workflows](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows) (checked 2026-11-11)
- [`secrets: inherit`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretsinherit) (checked 2026-11-11)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) (checked 2026-11-11)
- [`pull_request_target` blocked by default](https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2/) (checked 2026-11-11)
- [Claude GitHub App setup](https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md) and anthropics/claude-code-action#443 (checked 2026-11-11)
- Probe: dotfiles run [43209973289](https://github.com/fabiandistler/dotfiles/actions/runs/43209973289) and #786 comment 6822505952 (2026-11-12)
