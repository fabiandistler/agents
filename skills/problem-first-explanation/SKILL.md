---
name: problem-first-explanation
category: communication
environments: coding, chat
description: Output-form skill for explaining anything that solves a problem — a tool, method, concept, rule, or proposal — by leading with the concrete problem before the solution. For READMEs, docs, tutorials, lessons, talks, proposals, or any "explain X".
metadata:
  version: "1.0"
---

# Problem-First Explanation

Never explain a solution before the reader knows what problem it solves: Problem → Solution → Application.

The test for whether it applies: does the thing being explained exist *because of* a problem? A design pattern, a statistical method, a torque wrench, a tax allowance, a meeting format, a proposed process change — all do. Then the reader needs that problem first.

## When to use

- Writing or editing a README, package description, design rationale, or ADR motivation.
- Explaining a concept, method, tool, or rule from any field — "explain X", "what is X", "why do we use X", "what is X for".
- Preparing a lesson, tutorial, talk, workshop, or onboarding material.
- Writing a proposal, request, or justification — the change being proposed is the solution; the reader needs the problem it removes.
- Reviewing an explanation that feels abstract or hard to follow — the diagnosis is usually a missing problem statement.

Do **not** invoke for:

- Pure reference material (parameter tables, spec sheets, glossaries, API docstrings and roxygen blocks) and how-to guides whose title already names the problem.
- Content that does not answer a problem — a narrative, a news summary, a description of what happened.
- Answers where the reader is living the problem right now ("my build fails with…", "the wheel nut won't come loose"). Name the problem in one sentence and go straight to the solution; re-staging a pain the reader already feels is padding.

API docstrings and roxygen blocks stay reference-first: at most a one-clause why in `@details` or the long description when the reader cannot infer it.

## The three-step structure

### 1. Problem (concrete, not abstract)
Describe the **specific situation** that creates a need. Use a scenario, a symptom, or a pain point — not a category.

- ✗ "When you need to add behaviour to a class..." (abstract, no urgency)
- ✓ "You have an Order class with a `format()` method. Marketing wants to optionally add a gift-wrap note, a discount banner, and a tracking link to a confirmation — in any combination. Subclassing produces an explosion of OrderWithGiftNote, OrderWithBanner, OrderWithGiftNoteAndBanner..." (concrete, the reader feels the pain)

### 2. Solution (conceptual, named)
Introduce the concept as a **direct response** to the pain just described. Name it. State what it does in one sentence. Do not yet show the details.

- ✗ "There is a pattern called Decorator that wraps objects..." (definitional, doesn't hook the problem)
- ✓ "The Decorator pattern solves this: instead of subclassing, you wrap the original `Order` in decorators (`GiftNoteDecorator`, `BannerDecorator`) that each add one embellishment around the original `format()`. Any combination is a stack of wrappers, not a new subclass." (links solution to pain)

### 3. Application (concrete how)
Now show how it is used — whatever form the "how" takes in the domain: code or a signature, a sequence of steps, a worked calculation, a diagram, the exact wording of a request, the decision the reader now has to make. The reader has the mental model already, so this part reads as "of course, that follows".

- Torque wrench: look up the value, set the scale, tighten the nuts in a crosswise pattern until the click, stop at the first click, and turn the scale back down before storing it.

## Before / after

Question: "What is a torque wrench?"

Before (definitional): "A torque wrench measures applied torque in newton-metres. It has a scale, a ratchet head, and an audible click mechanism. Calibration matters."

After (problem-first): "You are putting the winter wheels on. Too loose and a nut works itself off at speed; too tight and you stretch the stud. You cannot feel newton-metres. A torque wrench removes the guesswork: set the manual's value and it clicks the moment you reach it. Look up the value, set the scale, tighten crosswise until the click, stop at the first click."

## Why this order works

Attempting a problem before instruction improves later application of the concept (http://aaalab.stanford.edu/assets/papers/earlier/A_time_for_telling.pdf), with the strongest effects for conceptual material, transfer tasks, and novices (https://journals.sagepub.com/doi/10.3102/00346543211019105).

## Minimum viable check

After the first paragraph the reader can answer: what concrete situation does this solve, and what the solution is called plus what it does in one sentence. If either is no, restart from step 1.

## Failure modes to refuse

- **Definitional opener.** "X is a pattern / tool / method that..." — definitions before pain. Restart with a concrete scenario.
- **Solution before problem.** A code dump or spec table followed by "this does Y", or "use X when..." — readers cannot parse details without a mental model; *when* is a list, not a hook.
- **Generic problem statement.** "Sometimes you need flexibility..." / "Precision matters..." — too vague to anchor.
