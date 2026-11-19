# 2026-11-19 audit of the tools gallery

Scope: the 13 HTML files in `fabiandistler/tools` at `bee5a8f`, audited by four
parallel subagents in a real browser (desktop and phone width) and against the
skill that fits each file: html-tool-builder for 5 tools, html-artifacts for 8
explainers. Requested by the user on 2026-11-19 ("alle Tools auf Fehler durch und
skill adherence").

- Totals: 104 bugs (3 high, 27 med, 74 low), 94 rule violations.
- Fixed before the issues were filed: the `tool-pattern.html` XSS (high) and the
  `data-workflow.html` crash, both in PR tools#10 (merged 2026-11-19 18:56 UTC).
- Open high and med bugs, filed per file on 2026-11-19 as tools#11 to tools#16;
  these issues are the durable source for the findings. The full subagent
  reports lived in a session scratchpad and are not kept.
- Cross-cutting bug classes (2026-11-19):
  - untrusted text into HTML, YAML or Python (5 files);
  - number parsing of German formats and NaN/∞ results (5 files);
  - phone layout and touch (6 files).

  A first-load smoke test catches none of them; most are silently wrong
  results after interaction.
- Rules nearly every file broke (2026-11-19): touch targets ≥ 44 px (5/5 tools),
  CSS tokens for every color (5/5), the ~400-line limit (4/5), serif body and
  "AI default look" (8/8 explainers), landmarks, labels, keyboard and contrast
  (6/8). The audit read these as unenforced or conflicting rules, not as bad
  tools. Outcome: [2026-11-19 decisions](../decisions/2026-11-19-tools-decisions.md).
- Size and bugs (2026-11-19): the four files with 1435–2173 lines carried 12–16
  bugs each, the other nine 3–10.
- Skill follow-up: html-artifacts rule 9 and the 390 px rule 3 in agents#901;
  paste-ready html-tool-builder changes given to the user.

Related: [tools gallery had no checks](../problems/tools-no-checks.md).
