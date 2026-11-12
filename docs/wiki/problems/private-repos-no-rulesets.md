# Private target repos cannot have rulesets

- 2026-11-11: fabiandistler/dotfiles and fabiandistler/repo-maintenance
  are private; on the current plan their rulesets API answers "Upgrade to
  GitHub Pro or make this repository public". Neither can have a ruleset, a
  required check or branch protection. Sources: #786 ("Facts checked on
  2026-11-11"), #789, dotfiles#61, repo-maintenance#153.
- Consequence (2026-11-11): the factory's brakes are weaker there than in
  agents. CI and the automated review cannot be required; the human merge
  is the only brake that enforces. Nothing but the prompt stops the
  implementer's App token from pushing to `main`.
- 2026-11-11: push guard filed as #789 (sub-issue of #786) to close the
  push gap.
- Open choice for the maintainer (2026-11-11): GitHub Pro, make the
  targets public, or accept the weaker brakes. #786 lists plan and
  visibility changes as maintainer decisions, out of the spec's scope.
- Note (2026-11-11, per #786 and the onboarding issues): while private, the
  `pull_request_target` default block does not apply to the targets, so no
  event policy is needed there.

Related: [rollout](../decisions/2026-11-11-factory-rollout.md),
[Dependabot on private repos](dependabot-private-repos.md).
