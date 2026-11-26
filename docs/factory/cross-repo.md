# Factory cross-repo specifics

For a developer, usually an agent session, about to change a factory task
that also runs in a target repository: what holds because the reusable
workflows run from a caller in another repository. How the tasks fit together
is in the [architecture](architecture.md); the rollout checklist is in
[changing a task](changing-a-task.md).

- **Pins.** A target's four callers pin `fabiandistler/agents/.github/workflows/factory-*.yml`
  to one full commit SHA with the comment `# agents main, <date>`. A change reaches a target when a
  pull request bumping all four merges on its default branch; the App token
  exchange also checks the caller there
  ([onboarding](../agents/factory-onboarding.md#one-sha-for-all-callers)).
- **Anonymous fetch.** Every reusable job but the triage label's fetches
  `job.workflow_repository` at `job.workflow_sha` into `$RUNNER_TEMP/factory`
  without a credential (`factory-implementer.yml`, step *Fetch the factory
  scripts*), even when agents
  calls with `./`. agents must stay public: private, all those fetches fail,
  and on the owner's plan agents would lose its ruleset too.
- **Caller's context.** `github` and `vars` are the caller's, so
  `PR_AUTO_MERGE` and the model variables are set per repository
  (`factory-pr-review.yml`, header note *Contexts*).
- **Private targets.** No rulesets on GitHub Free: nothing can be required,
  the push guard stops pushes to the default branch, and the maintainer
  merges only on green ([wiki](../wiki/problems/private-repos-no-rulesets.md)).
- **Capacity.** One implementer per repository, one subscription for all
  (ADR-0018, "Billing and capacity").
- **Proven in the targets, 2026-11-14.** The implementer claimed, pushed
  and opened a pull request in both: dotfiles run 43634268109 (dotfiles#67)
  and repo-maintenance run 43634321706 (repo-maintenance#160), both merged.
  The model review ran on repo-maintenance#157 (run 43628269770, attempt
  2); #786 closed on it (comment 6883412967).
