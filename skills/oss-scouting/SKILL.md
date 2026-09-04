---
name: oss-scouting
category: workflow
activation: command
disable-model-invocation: true
environments: coding
compatibility: Requires git and the GitHub CLI (`gh`, read-only). Running a candidate's reproduction needs that project's own toolchain.
argument-hint: "<owner>/<repo>"
description: Scout one third-party open-source repository for open issues that suit a small, clean contribution, and write repro, root-cause analysis, fix diff, test, and a submit checklist to a local folder only.
metadata:
  version: "1.0"
---

# OSS Scouting

One run = one library. The result is analysis and drafts in a local folder that
the user fully understands, tests themselves, and submits under their own name.

## When to use

Use this on a request to scout a specific upstream project for contribution
candidates — "scouting run for `<lib>`", "find me issues in `<lib>`", "where
could I contribute to `<lib>`", "candidates for a PR to `<lib>`".

Not for maintaining the user's own repositories, not for debugging their own
code, and not for submitting anything — submission is exclusively the user's
job.

## Non-negotiable rules

1. **Local only.** No fork, no push, no PR, no issue comment, no reaction, no
   new issue. A read-only clone into a throwaway cache folder is allowed.
2. **Policy before search.** If the project rejects AI-assisted contributions,
   the run ends with a report — without reviewing a single issue.
3. **Quality over count.** At most 3 candidates. Zero candidates is a valid
   result and is reported as one. The `good first issue` label is neutral, not
   a filter.
4. **The repro must run.** A candidate without a reproduction confirmed on
   current `main` is not worked up. No "probably reproducible".
5. **Invent nothing.** Unclear cause → mark it open, don't fill it in
   plausibly. No policy statement found → "no explicit policy found", not
   "allowed".

## Procedure

Copy the checklist and work through it:

- [ ] 0 Setup: repo slug, folder, read the LOG
- [ ] 1 Policy gate: contributing docs, AI policy, DCO/CLA, test/NEWS duties
- [ ] 2 Issue review with filters → longlist → shortlist (≤3)
- [ ] 3 Per candidate: repro, analysis, fix diff, test, risk
- [ ] 4 Ranking by value × acceptance × learning
- [ ] 5 Per candidate: submit checklist carrying the project's rules
- [ ] 6 Write README + LOG, report to the user

### 0 Setup

Without a repo slug, ask — one run, one library.

Resolve the artifact root first. It defaults to `~/oss-scouting/` and is
overridden by `OSS_SCOUTING_HOME`. These are documents the user opens, runs, and
copies into a pull request, so they live somewhere visible and stable across
runs — not under `~/.local/share`, and never inside a git work tree, where a
`git add .` would sweep them into an unrelated commit:

```bash
root="${OSS_SCOUTING_HOME:-$HOME/oss-scouting}"
mkdir -p "$root"
if git -C "$root" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "refusing: $root is inside a git work tree" >&2; exit 1
fi
```

Stop on that refusal and ask the user for a root outside any repository. Folder
layout under the resolved root:

```
<root>/<owner>-<repo>/<YYYY-MM-DD>/
  README.md              policy summary, ranking, rejected issues
  01-issue-<nr>/
    repro.<ext>          runnable, minimal, expected vs. actual output
    analysis.md          cause with file:line references into current main
    fix.diff             proposal as a unified diff against main
    test.<ext>           test case in the project's own test framework
    submit-checklist.md  filled in per project
  02-issue-<nr>/ …
<root>/LOG.md            every run: date, repo, issue numbers reviewed, outcome
```

Read `LOG.md` before reviewing: an issue already checked is only revisited if it
has changed since.

### 1 Policy gate

Read: `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE*`,
`.github/ISSUE_TEMPLATE*`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, and doc pages
on "contributing" / "development". Additionally search the repo and the docs
for `AI`, `LLM`, `generative`, `Copilot`, `ChatGPT`, `Claude`,
`machine-generated`, `disclosure`.

Summarize in README.md as a table:

| Rule | Finding | Source |
|---|---|---|
| AI-assisted contributions | allowed / allowed with disclosure / rejected / no explicit policy | file/URL |
| Disclosure wording | quote, if required | |
| DCO / CLA | sign-off needed? CLA bot? | |
| Tests | framework, mandatory?, how to invoke | |
| NEWS/changelog | entry required? format? | |
| Issue-first | PR only with a linked issue? | |
| Branch/commit conventions | | |
| Style/lint | formatter, lint gate | |

**Stop** on "rejected": README with this table, LOG entry, message to the user.
Done. No workaround suggestions.

### 2 Issue review

Tool: `gh` CLI, read-only. Window: the last 6 months.

```bash
gh issue list -R <owner>/<repo> --state open --limit 200 \
  --search "created:>=$(date -d '6 months ago' +%F) no:assignee" \
  --json number,title,labels,comments,createdAt,updatedAt,author,url
```

Check each issue with `gh issue view <nr> --comments`:

**In:** reproducibly described (code + versions) or a demonstrable
documentation error; narrowly scoped; at least one maintainer response
(`authorAssociation` OWNER, MEMBER, COLLABORATOR) confirming the problem or
setting a direction; no assignee; no open PR linked (cross-check with
`gh pr list --search "<nr>"`).

**Out:** design or architecture discussion; labels such as `needs-decision`,
`discussion`, `wontfix`, `breaking`, `RFC`, `blocked`; a maintainer has voiced a
differing opinion; feature requests without maintainer buy-in; issues whose fix
changes the public API; issues where the maintainer says they will do it
themselves.

**Preferred:** bugs with a repro, wrong or missing documentation with
demonstrable behavior, missing tests for confirmed behavior, error messages that
mislead.

Longlist (every issue reviewed, with a one-sentence reason) into README.md;
shortlist ≤3. If nothing survives an honest review, report that — don't relax
the criteria to fill the list.

### 3 Working up each candidate

Read-only clone (`git clone --depth 50`), current `main`. The clone is
regenerable, so it belongs in cache rather than in the artifact tree — use
`mktemp -d` or `${XDG_CACHE_HOME:-$HOME/.cache}/oss-scouting/<owner>-<repo>/`.
Keeping the two apart means deleting the clone never risks the analysis, and the
upstream repo's own tooling never sees the notes.

1. **repro**: minimal, runnable, with version information, expected vs. actual
   output as a comment. Run it. If it doesn't reproduce → drop the candidate and
   record it in README under "rejected after repro" with the finding.
2. **analysis.md**: cause with `path:line` references; the call path from user
   code to the faulty spot; why exactly there; what the author probably
   intended; related spots with the same pattern (a note, not a scope
   extension).
3. **fix.diff**: the smallest diff that repairs the repro; style of the
   surrounding code; no reformatting; no "while I was in there" changes.
4. **test**: in the project's test framework, in the place the project keeps
   comparable tests; fails without the fix, passes with it — run both and record
   the result.
5. **Risk** (in analysis.md): affected callers (`grep` / `gh search code`), API
   surface, performance, edge behavior (NA/NULL/None, empty inputs, encoding,
   platform), backward compatibility. Rate low/medium/high with a reason.

Known project quirks (verify in the repo when in doubt rather than adopting
blindly): data.table tests through its own `test()` mechanism in
`inst/tests/tests.Rraw` (numbered tests, not testthat) and requires a NEWS
entry; polars has a Rust core — only take candidates whose cause sits in the
Python layer, the docs, or the tests, unless the user explicitly wants Rust;
plumber and most R packages use testthat + NEWS.md; FastAPI uses pytest and its
docs are multilingual (translations follow their own process).

### 4 Ranking

| Candidate | Community value (1–5) | Acceptance likelihood (1–5) | Learning value (1–5) | Product | Reason |

Acceptance likelihood drops with: a maintainer response older than 3 months,
more than ~40 diff lines, touching core paths, a missing issue-first link.
Learning value rises with contact with internals the user reuses directly in
their own work.

### 5 Submit checklist per candidate

`submit-checklist.md`, filled in from phase 1 — never a generic template:

```
- [ ] I have read analysis.md and can explain the cause without the file
- [ ] Ran repro and test myself (red without fix, green with fix): <command>
- [ ] Full test suite green locally: <command from CONTRIBUTING>
- [ ] Lint/format gate: <command>
- [ ] NEWS/changelog entry: <required yes/no, format>
- [ ] Issue reference in the PR: <"Closes #nr" or project convention>
- [ ] DCO sign-off / CLA: <yes/no, how>
- [ ] AI disclosure: <required yes/no; proposed wording, if yes>
- [ ] PR template fields: <list>
- [ ] Scope: this fix only, no side changes
```

Proposed disclosure wording, where required or customary: honest, short,
responsibility with the user — "Analysis and draft assisted by an AI tool; I
reproduced, reviewed and tested the change myself."

### 6 Wrap-up

README.md: policy table, longlist with reasons, ranking, rejected candidates.
Append to LOG.md. Report to the user: the ranking table, three sentences per
candidate (problem, cause, fix), and what they have to do next themselves.
Do not offer to submit.

## Provenance and teardown

Written 2026-09-02. The guardrails come from the 2026 AI-slop debate in open
source (curl, Ghostty, tldraw; GitHub's PR throttle): unreviewed
machine-generated contributions cost maintainers more than they give, so this
skill produces material for the user to verify and submit, never a submission.

Teardown 2027-03-01 — if no contribution from a scouting run has been submitted
by then, delete the skill.
