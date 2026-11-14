# Closing keyword in quoted text closes the issue

- 2026-11-12: PR #795 (wiki record of the 2026-11-11 factory decisions)
  merged at 08:38 UTC (`fabiandistler/agents@9242f8d`). Its body listed the
  three new factory tasks as Rework, Fix and Retro, each followed directly
  by its issue number, as `docs/wiki/index.md:18` did. GitHub read the word
  "Fix" before "#783" as a closing keyword: at 08:38:37 UTC it set #783
  (Fix task) to closed as completed, although no Fix-task code was on main.
  Found and reopened 2026-11-13 (comment 6863813860).
- Why the implementer would also have stopped (2026-11-13,
  `fabiandistler/agents@0585e8e`): the claim's
  `_pull_request_holding_issue` (`scripts/implementer_claim.py:157-178`)
  returns the first open or merged PR whose body declares that it closes the
  issue, using `closing_references` from `scripts/check_pr_issue_links.py`.
  With #795's body unchanged, an implementer run on the reopened #783 would
  have ended with `pr-exists`.
- Fix (2026-11-13): PR #795's body reworded to "Rework (#782), Fix task
  (#783), Retro (#784)". A scan of all 448 PR bodies with
  `check_pr_issue_links.closing_references` found no other PR declaring a
  close of #783. The same day, `docs/wiki/index.md:18` was reworded the
  same way ("Fix (#783)"), so quoting the index no longer repeats the
  incident.
- Why the links check let it through (2026-11-13): #795's body carried a
  "No issue:" line and a closing keyword. `check_pr_issue_links` accepts
  that combination; the links check passed on #795's head in run
  43184409003, and `issue-links` is not a required check. Filed as #802
  (`bug`, `needs-triage`). Fixed for #802: a body that states "no issue"
  and declares any closing now fails the check, naming each issue GitHub
  would close. A closing keyword quoted behind a real `Closes` line still
  passes (option 2 of #802, not adopted).
- Practice (2026-11-13): in PR bodies, and in wiki text that may be quoted
  into one, put an issue number after a task name in parentheses, and do not
  let close/fix/resolve or their inflected forms stand directly before an
  issue reference.

Related: [unlinked PRs](unlinked-prs.md), the opposite failure;
[triage decisions](../decisions/2026-11-13-triage-decisions.md).
