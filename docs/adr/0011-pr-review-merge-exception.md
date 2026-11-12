# ADR-0011: A narrow docs-only CI merge exception

## Status

Accepted (2026-10-28) by the maintainer on #621, for the gated cases below
only. Amended 2026-11-07 with decisions A–D, and 2026-11-11 with the five
required checks of decision A (#764). Implemented in #635 and in force
from merge, but inert until the maintainer sets `PR_AUTO_MERGE=true` at the
end of the [rollout](../agents/pr-review-runbook.md#rollout). The interactive
merge guard is unchanged.

## Context

The repository reserves merging for humans: coding agents act under the
maintainer's GitHub account, and agents merging their own pull requests led to
red-CI merges and reverts (#557). The merge guard enforces that rule on every
interactive agent.

The PR review pipeline (#621) splits a read-only model review from a
model-free publisher. Routine documentation pull requests still wait for the
maintainer even when they are low risk and the review passed. Automating those
merges crosses the governance boundary, so it needs an explicit decision; a
passing model verdict alone cannot grant it.

## Decision

One narrow exception to "only the human merges": the model-free `publish` job
of `.github/workflows/pr-review.yml` may enable GitHub's native auto-merge
(merge commit, head pinned with `expectedHeadOid`) on a docs-only pull
request. It never merges directly, never approves and never requests changes.
No interactive agent gains any merge right; the merge guard
(`scripts/pr_merge_guard.py`, `merge-guard` plugin) stays as it is.

The model job holds the model key and no write scope; the publishing job holds
the write scope and no model key. The model's output is a recommendation that
can only raise the risk.

All gates must hold on data re-fetched right before the write:

- `PR_AUTO_MERGE` is exactly `true` (off by default).
- Deterministic risk is low: only `docs/**` outside `docs/agents/` and
  `docs/adr/`, `GLOSSARY.md`, `MAINTENANCE.md` or `maintenance/reports/**`,
  within the size limits and with no deletion or rename. `README.md` and the
  ADRs state policy, including this rule, so they are medium.
- The review is complete (not partial) with verdict `pass`.
- Same repository, not a draft, targets the default branch, mergeable.
- Head SHA unchanged since the assessment; no human change request; no
  `do-not-merge`.

Decisions taken on 2026-11-07:

- **A. The ruleset waits for checks.** The publisher does not require green
  checks at enable time. The default ruleset requires `checks`, `mermaid` and
  `secrets`, and native auto-merge waits for them. Pending checks never
  disable the bot's auto-merge; failing checks block the merge. Adding the
  required checks is a one-time manual step of the rollout.
- **B. `do-not-merge` disables any auto-merge.** It is a hard veto, applied at
  once through a `labeled` trigger, even to an auto-merge a human enabled.
  This is the only case in which the bot touches a human-enabled auto-merge.
- **C. One integration branch.** The pipeline, auto-merge and docs land
  together in one pull request that supersedes #637.
- **D. Already-mergeable pull requests stay with the human.** When GitHub
  refuses to arm auto-merge because the checks are already done, the
  publisher records "not enabled", adds `needs-review` and says so in its
  comment. It never falls back to a direct merge.

**Amendment of 2026-11-11 to decision A (#764).** The default ruleset
requires five checks: `checks`, `bats` and `mermaid` from `ci.yml`, `secrets`
from `maintenance-gate.yml`, and the commit status `pr-review/verdict`.

- `bats` is the only job that runs `install.sh` and `scripts/install/*.sh`;
  `checks` only lints them. It was missing from the ruleset by omission, and
  two hand-armed auto-merges merged before it reported.
- `pr-review/verdict` makes a merge, a hand-armed auto-merge included, wait
  for the review. The `publish` job sets it on the head it reviewed: green
  for any verdict (`pass`, `concerns`, `block`), so the review stays
  advisory. A draft stays pending until its `ready_for_review` run; an
  unavailable review is an error until a re-run yields a verdict; a fork,
  which the model never reviews, is green once published. Nothing sets the
  status ahead of the review: a new head starts without one, which the
  ruleset reads as waiting.
- Whether a `concerns` verdict on a `risk:high` pull request should block is
  a separate decision, not taken here.
- Adding the two checks to the ruleset is again a manual step
  ([runbook setup](../agents/pr-review-runbook.md#setup), step 6).

The bot marks its own auto-merge with `auto-merge:bot`. It disables only that
one when a later push, a worse verdict or a failed gate revokes eligibility,
and a model-free `hold` job disables it on every push before the new head is
reviewed.

## Considered options

- **Advisory review, human merges only.** Smallest write surface, but routine
  documentation keeps queueing behind risky changes.
- **Narrow native auto-merge (chosen).** Removes that queue for the safest
  class; GitHub's ruleset remains the last word on checks.
- **Model-held write or merge credential.** Rejected: untrusted pull request
  text would steer a credential that can write to the repository.
- **Direct bot merge.** Rejected: it bypasses GitHub's native wait for the
  required checks and turns a bot bug into an immediate merge.
- **Gate on green checks at enable time.** Rejected (decision A): it
  duplicates the ruleset, races with running checks and would disable
  auto-merge while checks are merely pending.
- **Auto-merge for medium risk or for `README.md` and ADRs.** Rejected: those
  files hold policy, and a pull request could loosen the rules that judge it.

## Consequences

- A merge through auto-merge armed with `GITHUB_TOKEN` starts no `push`
  workflow on `main`. Pages is unaffected (its inputs are never low risk); CI
  on `main` runs with the next human push.
- Removing `do-not-merge` re-arms nothing until the next push or a manual
  dispatch.
- The [acceptance record](../agents/pr-review-acceptance.md) holds the live
  evidence: a dry run before the variable is set, then a docs pull request
  that waited for the checks and a non-docs pull request without auto-merge.
