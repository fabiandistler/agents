---
name: pr-description
category: workflow
environments: coding
compatibility: Requires git. Reads linked issues and an existing PR body with whatever tool the session has for the forge; works without one.
description: Write a pull request title and body in plain German — executed before/after output, the change in the smallest fitting visual, reading order, risks, checks run, linked issues — to a file. Use whenever a PR description is written or updated.
metadata:
  version: "1.1"
---

# PR Description

Write the title and body of a pull request so a reviewer knows what changed,
where to start reading, and what could break, before opening a single file.
Output is German; this file is in English.

Forked from Matt Pocock's `pr` (mattpocock/skills at commit `49dd158`, MIT; see
`UPSTREAM-LICENSE`), whose visual catalogue comes from Dex Horthy's `show-me`
(humanlayer/skills, MIT; see `UPSTREAM-LICENSE-HUMANLAYER`). The reviewer
guidance follows the tidyverse code review principles
(code-review.tidyverse.org, chapters "Submitting a PR" and "Focused PRs").

## When to use

- An agent or the user is about to open a pull request and needs its title and
  body ("schreib die PR-Beschreibung", "write the PR description").
- An existing PR got new commits and its body no longer matches the diff.

Not for a release PR (version bump, changelog, publish steps): suggest the user
run `release-pr` instead. Not for opening or updating the PR on the forge: this
skill only writes a file.

## Output contract

- **Language.** German, always. Write English only when the user explicitly
  asks for it; then translate the headings too.
- **File, not PR.** Write the title on line 1, an empty line, then the body, to
  the path the user names, otherwise to `<run>/pr-description.md`, where `<run>`
  is the directory a fresh `mktemp -d /tmp/pr-description-XXXXXX` printed. Never
  write it into the repository. Report the path and the title in chat. Never
  open, edit or comment on the PR yourself; whoever opens it uses the file.
- **Title.** Under 72 characters, says what the change does, and stands alone
  in the history. Never "Fix bug", "Fixes #123", a phase name or a copy of the
  issue title: describe the change made, not the problem it fixes.
- **Body.** The sections below, in this order, under exactly these headings.
  Drop a section that has nothing to say; never write "n/a" or "keine".

| Slot | Heading |
|---|---|
| 1 | `## Worum geht's` |
| 2 | `## Vorher / Nachher` |
| 3 | `## Was genau geändert wurde` |
| 4 | `## Review-Reihenfolge` |
| 5 | `## Risiko & Schwächen` |
| 6 | `## Verknüpfungen` |
| 7 | `## Geprüft` |

Sections 2 and 7 are evidence: output you ran, pasted verbatim. Never write
output you did not run; when you could not run it, say so (see below).

## Workflow

1. **Find the diff.** The base is the branch the PR targets; default to the
   remote's default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`;
   when that ref is missing, `git ls-remote --symref origin HEAD`). Read `git log --oneline <base>..HEAD`, `git diff --stat <base>...HEAD` and
   the diff itself.
2. **Read the context.** Read the target repo's `GLOSSARY.md`; if it has
   several, `GLOSSARY-MAP.md` names the right one. Find linked issues in the
   branch name, the commit messages and the user's request, and read each one
   with its comments, using the tool the session has for the forge. Without
   one, drop the summary of the issue discussion from section 6 and say so in
   chat.
3. **Sort the changed files.** Mark every generated file (list below). Count
   only the rest. Note every export change.
4. **Check focus.** If the diff mixes refactoring (moves, renames,
   restructuring without behaviour change) with a behaviour change or bug fix,
   warn in chat and propose a split: which commits or files go into a separate
   refactoring PR first. Still write the description for the diff as it is. The
   warning never goes into the description.
5. **Collect the evidence.** Run the before/after example on the base and on
   the PR branch (section 2), then the repo's checks on the PR branch
   (section 7). Read `references/evidence.md` for how to run the example on
   both sides without touching the user's working tree.
6. **Write** title and body to the file, following the sections and the style
   below.
7. **Re-read** the file against the diff once: every claim matches the code,
   every dropped section really had nothing to say. Count the title's
   characters (`head -1 <file> | wc -m` counts the newline too) rather than
   estimating them.

### Updating an existing body

Read the PR's current body with the session's forge tool, or ask the user to
paste it. Regenerate the contract sections from the current diff, but carry
every human-written paragraph (extra headings, decisions, reviewer notes,
mentions, screenshots) verbatim into its matching section; when unsure,
keep it and say so in chat. Rerun the evidence on the new head.

## Sections

### 1 Worum geht's

Three short parts, context first:

- the problem or the reason for the change, in one or two sentences;
- what is different now;
- the review depth the author wants: "Ein Review auf Architekturebene reicht"
  or "Bitte Zeile für Zeile prüfen, vor allem …". Name the part that needs the
  closest look.

### 2 Vorher / Nachher

Show the behaviour change as real output, executed on the base (the merge-base
of the PR) and on the PR branch. Write it for a bug fix, a behaviour change or
a performance change; drop it for a pure refactoring, docs or CI change.

- **R:** one `reprex` of the same example, rendered once per branch.
- **Python:** one minimal script, run once per branch, its output pasted under
  the code.
- **Performance:** the same benchmark on both branches, numbers verbatim, plus
  the machine it ran on.

Two subheadings, `### Vorher (<base>)` and `### Nachher (<branch>)`, each with
the code and its output. Keep the example minimal: only what shows the change.

When the example cannot be run here (runtime or package missing, needs
credentials, network, a database or data you do not have), write one line
instead: `Nicht ausgeführt, weil <Grund>.` Add the example code as a block the
reviewer can run, with no output under it. Never write output you expect,
remember or reconstructed.

### 3 Was genau geändert wurde

Show the shape of the change in the smallest view that makes the point:
pseudocode, call tree, component tree, shallow file tree, Mermaid, a `diff`
shaped like the topic, or a whole block when most of it is new. Read
`references/visuals.md` for the catalogue with an example of each and the
placement rules. Usually one or two visuals, each next to the sentence it
supports; never all of them.

### 4 Review-Reihenfolge

Write it when at least four non-generated files changed, or when tests or
examples explain the purpose better than the implementation. Otherwise drop it.

- A numbered list. Each step: path, then a half-sentence reason
  ("`tests/test_parse.py` — zeigt das gewünschte Verhalten").
- Start with tests or examples when they explain the intent; then the core
  change; then callers; then docs.
- Group files that are read together into one step.
- End with one line naming the generated files:
  `Generiert, nicht reviewen: <path>, <path>`. Drop the line when there are
  none. When generated files changed but this section is dropped, put the
  line at the end of section 3 instead, so the reviewer still knows to skip
  them.

**Generated files** (lockfiles such as `uv.lock` or `renv.lock`, roxygen
output in `man/*.Rd` and `NAMESPACE`, testthat snapshots under `_snaps/`, files
marked `linguist-generated` in `.gitattributes` or whose header says
"generated, do not edit", and files the repo's own docs say a script
regenerates) stay out of the reading order and the four-file count.

### 5 Risiko & Schwächen

- **Tür:** einweg or zweiweg. A two-way door can be walked back cheaply; a
  change with destructive or hard-to-reverse effects (data migration, deleted
  data, published API, sent messages) is a one-way door. One sentence why.
- **Reichweite:** the blast radius: what could break if the change is wrong,
  and for whom (callers, consumers of an API, a CLI flag, a config key, a
  layout). Consider all of them; name the ones that apply.
- **Schwächen:** known shortcomings of the approach, alternatives not taken,
  cases not covered.
- **Exporte:** every export change, always, even though `NAMESPACE` is
  generated: added, removed or renamed names in `NAMESPACE` or `__all__`. A
  removal or rename is a breaking change; say so.

### 6 Verknüpfungen

- `Closes #<n>` for each issue the PR resolves completely.
- `Teil von #<n>` for an issue or spec the PR advances without resolving.
- When an issue's discussion is long or weighed several approaches, add two to
  four sentences on its outcome: which approach was chosen and why, so the
  reviewer does not have to read the thread.

### 7 Geprüft

The quality gates you ran locally on the PR branch head, one line each: the
command in backticks, an em dash, the one-line result as the tool printed it
(`` `pytest` — 142 passed `` or `` `devtools::check()` — 0 errors, 0 warnings,
1 note ``). Take the checks from the repo's CI workflow, `AGENTS.md`,
`CONTRIBUTING.md` or `Makefile`. A failing check stays in the list with its
failure; never drop it, skip it or loosen a threshold to make it pass.

End with a `### Nicht geprüft` sublist naming each gap as
`<what>: <why, or where it is covered>`, such as an OS matrix that only CI
runs, a check whose tool is not installed here, or an integration test that
needs credentials. Drop the sublist only when every check ran.

Section 2 shows behaviour; section 7 shows quality gates. Test or lint output
never goes into section 2, and the before/after example never goes into
section 7.

## Style

- Short active sentences, one thought per sentence. Context before detail.
- No preamble, no closing summary, no "Diese PR …"-style throat clearing.
- One word per concept. Use the target repo's `GLOSSARY.md` terms verbatim and
  do not translate them.
- Technical terms (merge, branch, commit, reprex, diff) and every identifier,
  path, command and error message stay in English, in backticks where they are
  code.
- Prefer a visual or a list over a paragraph when it carries the point.
