---
name: review-decisions
category: workflow
activation: command
disable-model-invocation: true
environments: coding
argument-hint: "[<base-ref> | <protocol-file>]"
description: Walks a reviewer through the review decisions in an agent-generated change, the choices only a human can settle, one card per turn, and keeps a protocol outside the repo. Never posts, approves or merges.
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

## Protocol

Every answer goes into a protocol file outside the repository, so no verdict
lands in the working tree. Before the first card, get its path from
`python3 scripts/protocol.py path --repo <repo-root>` (exit 4: the state
directory lies inside the repository; set `XDG_STATE_HOME` elsewhere) and
print the full path to the reviewer.

Write the protocol before showing the first card: a header with the
repository, the base ref, the input files and the line "A defect review was
not run.", then one section per card in queue order, each starting
`## Card <n> of <total>` and holding the card's fields. Record each answer the
turn it is given, as `- Answer: ok`, `- Answer: change` or `- Answer: later`;
add `- Draft comment:` after a `change`, and `- Question:` and `- Reply:`
lines for each question.

To resume, the reviewer passes a protocol file instead of a base ref. Run
`python3 scripts/protocol.py resume <protocol-file>`: its JSON names the first
card without an answer (`next`) and the cards set aside (`later`). Skip
gathering inputs and classifying; continue at `next` with the cards as the
protocol holds them.
Exit 3 means the file is not a protocol this skill wrote; say so and stop.

## Cards

Show one card per turn and wait for the answer. Keep it short enough to read
on a phone screen without scrolling far:

```text
Card <n> of <total>: <file>:<line>
Why queued: <the criterion that put it in the queue>
Chosen: <what the author chose>
Alternatives (reconstructed, not what the author considered):
- <alternative>
- <alternative>
Cost to undo after merge: <one sentence>

Lean: <the skill's lean, and why, in one line>

Answer: ok / change / question / later
```

The alternatives are the classifier's guesses. Never word them as options the
author weighed or rejected: you cannot see what the author considered. Keep
the lean below the finding, so an opinion never reads as a fact.

The reviewer answers with one word, or a word and a note:

- `ok`: the choice stands. Record it and show the next card.
- `change`: draft a review comment that names the location, what to change
  and why, using the reviewer's note when there is one. Show the draft, record
  it under the card, then show the next card.
- `question`: answer the question from the diff, the issue and the
  repository, and say when the answer rests on a guess. Record both. The card
  stays open: show it again and wait for `ok`, `change` or `later`.
- `later`: set the card aside. After the last card, show the cards set aside
  again, once each.

Any other reply is a question about the card.

## Close

When every card has `ok` or `change`, or the reviewer stops, end the protocol
with the line `Review decisions settled, no defect review.` and print its full
path again. If the reviewer stops with cards still open, write the line only
when they confirm; otherwise leave the protocol open for a later run to
resume. Add the line that deviations were not checked when no issue was
supplied.

Nothing else: no verdict on the change and no claim that it is correct.
