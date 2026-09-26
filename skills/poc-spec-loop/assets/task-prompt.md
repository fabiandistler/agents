You are executing exactly one task of a production-readiness loop. Your context is intentionally fresh: everything you need is below. Other tasks exist; ignore them.

## Spec
{{SPEC_MD}}

## Task
id: {{ID}}
title: {{TITLE}}
detail: {{DETAIL}}
check (run by the harness after you finish, exit 0 = done): `{{CHECK}}`
attempt: {{ATTEMPT}} of 3
{{#LAST_FAILURE}}
previous failure output:
```
{{LAST_FAILURE}}
```
{{/LAST_FAILURE}}

## How to work
Use the `mattpocock-skills:tdd` skill if it is available in this session; if not, follow the same red-green-refactor cycle as described here: write the failing test first, commit it as `test({{ID}}): …`; make it pass, commit as `feat({{ID}}): …`; refactor only if there is something to refactor, commit as `refactor({{ID}}): …`. Language commands are in `{{TOOLCHAINS_MD}}` — use those, do not invent alternatives.

Hard rules:
- Production code contains no placeholders, no `TODO`, no mocks or fakes. Mocks live in tests only.
- Touch only what this task needs. Do not edit `plans/`.
- Do not run the check yourself as a substitute for tests; the harness runs it.
- When the task cannot be completed as specified, write the reason to stdout on a line starting with `BLOCKED:` and stop without committing partial production code.

Finish when the three commits (or two, if refactor was empty) exist on the current branch and the working tree is clean.
