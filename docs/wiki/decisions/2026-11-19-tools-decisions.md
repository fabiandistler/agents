# 2026-11-19 decisions: the tools gallery

Decided by the user on 2026-11-19 in a chief-of-staff session that took on
`fabiandistler/tools` (see [goal](../goal.md)):

- Retire `spielwahrscheinlichkeiten.html`, `haushalt.html` and
  `review-pyramid.html` (`fabiandistler/tools@bee5a8f`, PR tools#10).
- Infrastructure, "deploy gate first": one PR with a pytest-playwright smoke
  suite that the Pages deploy waits for, uploading `_site/` instead of the repo
  root. prek hooks, gitleaks, Dependabot and `AGENTS.md` follow in a second PR.
  Python (uv) over Node, because every standard installer and gate keys on
  Python, R or shell: `prek-hooks`' `setup-hooks.sh` exits 5 on an HTML-only
  repo (2026-11-19 probe).
- Line limits: exempt the existing tools by name from the 5000-token hook;
  reframe html-tool-builder core rule 4 from "cut scope past ~400 lines" to
  "past ~400 lines, ship tests". Evidence: the four largest files carried 12–16
  bugs each, the other nine 3–10 ([audit](../snapshots/2026-11-19-tools-audit.md)).
- Fix all high and med audit bugs (30), grouped by bug class, each with a test.
- Skills: html-artifacts by PR (agents#901); html-tool-builder is a
  claude.ai-synced personal skill, so the session wrote paste-ready old/new
  text for the user.
- Defaults the session set and the user did not object to (2026-11-19): no
  ruleset requiring PRs (web-UI uploads to `main` stay possible; the deploy gate
  brakes direct pushes too); English for code and comments, German UI; no
  factory for tools.
- Branches: one branch per work package (`claude/tools-infra`,
  `claude/tools-fix-<issue>`, `claude/wiki-…`) instead of stacking everything
  on the session branch (user, 2026-11-19).
- The user agreed on 2026-11-19 to paste the html-tool-builder changes in
  claude.ai; not confirmed as done.
- Resulting work (2026-11-19): infra PR tools#17; fix issues tools#11 to tools#16,
  each fixed on its own branch and PR.
- Whitespace (user, 2026-11-19): one formatting pass (option b) instead of
  excluding 5 tools from the whitespace hooks; intentional trailing spaces in
  `<pre>` kept as `&#32;` (tools#26).
- Behaviour changes in fixes, reported to the user 2026-11-19, no objection:
  evo-algo spawns more food and reproduces at a lower threshold (tools#20);
  dfbetas treats a column as numeric at a majority of cells instead of 95 %
  (tools#19).
- Open (2026-11-19): tool-pattern's clipboard inspector has no paste target on a
  phone after tools#23; the user was asked whether to file an issue.
- Open (2026-11-19): touch targets ≥ 44 px, CSS tokens for canvas/SVG, the
  gallery's house style vs. "serif body", axe-core in the suite.

Related: [tools gallery had no checks](../problems/tools-no-checks.md).
