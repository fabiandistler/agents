# PR review event policy

For the repository maintainer, who sets up the Actions event policy that lets
`.github/workflows/pr-review.yml` run on `pull_request_target`. It is step 8
of the [runbook setup](pr-review-runbook.md#setup).

## Why

From 2026-12-02 GitHub blocks `pull_request_target` in public repositories
unless an Actions event policy allows it. A blocked event creates a failed
run with an error annotation and runs no job. Before that, two brownouts
enforce the block: 2026-11-09 and 2026-11-16, 16:00–18:00 UTC; between them
the default rule runs in evaluate mode and runs continue with warnings
([changelog of 2026-11-02](https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2/)).

The review depends on the trigger: it runs the workflow from the default
branch and never executes the pull request head (see
[Jobs and security model](pr-review-runbook.md#jobs-and-security-model)).
A test in `scripts/test_pr_workflow.py` forbids switching to `pull_request`.
So the fix is an allow policy scoped to this one workflow file, the option
GitHub's changelog names for workflows that depend on the trigger.

## Create the policy

In the repository: *Settings → Actions → Policies* (a page of its own, not
*General*), then create a policy:

1. Name: `pr-review: allow pull_request_target`.
2. Enforcement status: **Active**. **Evaluate** is GitHub Enterprise Cloud
   only.
3. Target: the workflow file `.github/workflows/pr-review.yml` only. It is
   the caller that carries the trigger; the jobs run from the reusable
   `factory-pr-review.yml` it calls. Keep that file name: renaming the caller
   breaks the policy's match. Whether a policy matches the caller's path or
   the called workflow's path is not documented (ADR-0018, open question 2);
   the first run after the extraction settles it in *Policy insights*.
4. Rule **Restrict events**: allow `pull_request_target` and
   `workflow_dispatch`. The rule is an allowlist for the targeted workflow,
   so without `workflow_dispatch` the [dry run](pr-review-runbook.md#dry-run)
   and the [manual re-run](pr-review-runbook.md#manual-re-run) would be
   blocked.
5. Save the policy.

The same policy through the REST API (untested; the docs describe the
`workflow_path` patterns only as "workflow file paths or glob patterns"):

```bash
gh api --method POST -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/fabiandistler/agents/actions/policies --input - <<'JSON'
{"name": "pr-review: allow pull_request_target", "enforcement": "active",
 "conditions": {"workflow_path": {"include": [".github/workflows/pr-review.yml"], "exclude": []}},
 "rules": [{"type": "restrict_action_events",
            "parameters": {"allowed_events": ["pull_request_target", "workflow_dispatch"]}}]}
JSON
```

## Check

- *Settings → Actions → Policies → Policy insights* lists no `pr-review` run
  after the policy's creation as blocked or would-be-blocked.
- The policy is listed by
  `gh api -H 'X-GitHub-Api-Version: 2026-03-10' repos/fabiandistler/agents/actions/policies`.
- During the brownout on 2026-11-16, 16:00–18:00 UTC, a push to an open pull
  request starts a normal `pr-review` run.

## Sources and limits

Read on 2026-11-11:

- [pull_request_target blocked by default December 2](https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2/)
  (GitHub changelog, 2026-11-02)
- [Workflow execution protections generally available](https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available/)
  (GitHub changelog, 2026-09-17)
- [Governing execution of GitHub Actions workflows](https://docs.github.com/en/actions/how-tos/administer/control-workflow-execution):
  the settings path, **Evaluate** limited to Enterprise Cloud, *Policy
  insights*; available to repository administrators in all public
  repositories
- [Default policy for `pull_request_target`](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target#default-policy-for-pull_request_target)
- [REST API endpoints for GitHub Actions policies](https://docs.github.com/en/rest/actions/policies)

Not verified on 2026-11-11, because the repository settings and the policies
API were not readable from an agent session:

- the exact labels of the policy form, such as the button that creates a
  policy and the workflow targeting field;
- that a repository of a personal account shows *Policies* and *Policy
  insights* (the docs name repository administrators and all public
  repositories, not account types);
- whether such a policy already exists;
- that the event allowlist also blocks `workflow_dispatch` when it is left
  out (read from the docs' allowlist wording, not observed);
- the effect of the first brownout: no `pr-review` run started between
  16:00 and 18:00 UTC on 2026-11-09.
