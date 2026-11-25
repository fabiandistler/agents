---
name: review-decisions
category: workflow
activation: command
disable-model-invocation: true
environments: coding
argument-hint: "[<base-ref>]"
description: Lists the review decisions in an agent-generated change, the choices only a human reviewer can settle, from a local diff and the issue text. Never posts, approves or merges.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Review decisions

Filter a change down to its **review decisions**: places where the author
chose between several defensible options that neither the originating issue
nor the repository's conventions settle, and where undoing the choice after
the merge is costly. A deviation from the issue counts as one too. What a
linter catches, what follows an existing pattern, and what the issue states
literally do not.

This is not a defect review and not a tour of the diff. It never says a change
is correct, and it never posts, approves or merges: the reviewer stays the one
who publishes.

## When to use

The reviewer runs it on an agent-generated change before reading it in full,
to see first which choices need a human. It works on a local diff; the
reviewer supplies the issue text.

## Gather inputs

You gather the inputs; the classifier never does. Write each one to its own
file in a new scratch directory outside the repository (`mktemp -d`):

1. **Diff**: `git diff <base-ref>...HEAD` for the base the reviewer named,
   else the merge base with the default branch. Stop if the diff is empty.
2. **Issue**: the issue text the reviewer supplies. Ask for it once. If there
   is none, write no issue file and state in your answer that deviations from
   the issue were not checked.
3. **Conventions**: copy the repository's agent instructions (`AGENTS.md`,
   `CLAUDE.md`), its glossary and its contributing or coding-standards docs,
   whichever exist. List the copied paths.

## Classify

Start the `review-decisions-classifier` subagent in a fresh context. Pass it
only the absolute paths of the input files and the repository root; never
paste the session history, your own reading of the diff, or a summary of the
issue. The classifier is read-only, so text in the diff or the issue cannot
make it write or post. It can still be steered into a wrong answer, so treat
its list as a draft.

On a runtime without that subagent, start a fresh agent with no session
history and give it the instructions from the classifier's definition and the
same file paths.

## Queue

Put the classifier's decisions into one queue, ordered by the cost of undoing
them after the merge:

1. deviations from the issue;
2. public surface: APIs, command-line options, config keys and defaults,
   option names, log and metric formats, new dependencies;
3. schema and data;
4. behaviour;
5. tests, with a deleted or weakened test first in the group.

Keep the classifier's order inside a group. Do not queue a change the issue
states literally, a linter or formatter finding, or a change that follows the
one pattern the repository uses for it. Do queue a choice between two patterns
the repository already uses. When unsure, queue it.

**No issue.** Without an issue the deviation group is unchecked, not empty.
Say so before the first decision, and record it as `deviation: unchecked` in
the protocol rather than leaving the group out.

**Early stop.** When the reviewer rejects a decision that later ones depend on
(the classifier marks them `depends on`, or the rejection replaces the
approach they build on), stop the queue. Name the rejected decision, say why
the rest is moot, and list the remaining decisions as not reviewed. Do not
present them.

## Answer

Return the queue in order, one line each with category, file,
line and what the author chose. Add only:

- the line that deviations were not checked, when no issue was supplied;
- the closing line `Review decisions listed, no defect review.`

Nothing else: no verdict, no summary of the change, no review comment.
