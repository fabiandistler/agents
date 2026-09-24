---
name: problem-first-explanation
category: communication
environments: coding, chat
description: Output-form skill for explaining anything that solves a problem — a tool, method, concept, rule, or proposal — by leading with the concrete problem before the solution. For READMEs, docs, tutorials, lessons, talks, proposals, or any "explain X".
---

# Problem-First Explanation

A small, sharp output-form skill: **never explain a solution before the reader knows what problem it solves.** Forces the three-step structure Problem → Solution → Application in any explanation — software, science, a tool in the workshop, a household rule, a proposal to a team.

The test for whether it applies: does the thing being explained exist *because of* a problem? A design pattern, a statistical method, a torque wrench, a tax allowance, a meeting format, a proposed process change — all do. Then the reader needs that problem first.

## When to invoke

- Writing or editing a README, package description, design rationale, or ADR motivation; adding a docstring or roxygen2 `@description` block.
- Explaining a concept, method, tool, or rule from any field — "explain X", "what is X", "why do we use X", "what is X for".
- Preparing a lesson, tutorial, talk, workshop, or onboarding material.
- Writing a proposal, request, or justification — the change being proposed is the solution; the reader needs the problem it removes.
- Reviewing an explanation that feels abstract or hard to follow — the diagnosis is usually a missing problem statement.

Do **not** invoke for:

- Pure reference material (parameter tables, spec sheets, glossaries) and how-to guides whose title already names the problem.
- Content that does not answer a problem — a narrative, a news summary, a description of what happened.
- Answers where the reader is living the problem right now ("my build fails with…", "the wheel nut won't come loose"). Name the problem in one sentence and go straight to the solution; re-staging a pain the reader already feels is padding.

## The three-step structure

### 1. Problem (concrete, not abstract)
Describe the **specific situation** that creates a need. Use a scenario, a symptom, or a pain point — not a category.

- ✗ "When you need to add behaviour to a class..." (abstract, no urgency)
- ✓ "You have an Order class with a `format()` method. Marketing wants to optionally add a gift-wrap note, a discount banner, and a tracking link to a confirmation — in any combination. Subclassing produces an explosion of OrderWithGiftNote, OrderWithBanner, OrderWithGiftNoteAndBanner..." (concrete, the reader feels the pain)
- ✗ "Bolts need to be tightened correctly." (true, but nothing is at stake)
- ✓ "You are putting the winter wheels on. Too loose and a wheel nut can work itself off at speed; too tight and you stretch the stud or warp the brake disc. The manual says a specific number of newton-metres — but you cannot feel newton-metres, and 'tight' differs with every arm and every wrench length." (concrete, both failure directions visible)

### 2. Solution (conceptual, named)
Introduce the concept as a **direct response** to the pain just described. Name it. State what it does in one sentence. Do not yet show the details.

- ✗ "There is a pattern called Decorator that wraps objects..." (definitional, doesn't hook the problem)
- ✓ "The Decorator pattern solves this: instead of subclassing, you wrap the original `Order` in decorators (`GiftNoteDecorator`, `BannerDecorator`) that each add one embellishment around the original `format()`. Any combination is a stack of wrappers, not a new subclass." (links solution to pain)
- ✗ "A torque wrench is a tool that measures the torque applied to a fastener." (definition, no hook)
- ✓ "A torque wrench removes the guesswork: you set the target value from the manual, and the wrench clicks the moment you reach it. 'Tight enough' becomes a number instead of a feeling." (links solution to pain)

### 3. Application (concrete how)
Now show how it is used — whatever form the "how" takes in the domain: code or a signature, a sequence of steps, a worked calculation, a diagram, the exact wording of a request, the decision the reader now has to make. The reader has the mental model already, so this part reads as "of course, that follows".

- Torque wrench: look up the value, set the scale, tighten the nuts in a crosswise pattern until the click, stop at the first click, and turn the scale back down before storing it.

## Why this order works

Two cognitive mechanisms:

- **Anchor before abstraction.** A concrete problem creates a mental model the reader can hang the abstract solution on. Without the anchor, the abstraction floats — readers ask "why?" instead of "ah, so that's why!".
- **Relevance before completeness.** Listing all features of a concept is overwhelming. Showing how it solves a specific problem makes the rest feel optional.

Neither mechanism depends on the subject. A reader meeting a design pattern and a reader meeting a torque wrench face the same gap: without the problem, they cannot tell which details matter.

## Minimum viable check

Before publishing any explanation, the reader should be able to answer **after the first paragraph**:

- [ ] What concrete situation does this solve?
- [ ] What is the solution *called* and what does it do in one sentence?

If either is no, the structure is wrong — restart from step 1.

## Failure modes to refuse

- **Definitional opener.** "X is a pattern / tool / method that..." — definitions before pain. Restart with a concrete scenario.
- **Details-first.** A code dump, step list, or spec table followed by "this does Y." — readers can't parse details without a mental model.
- **Solution before problem.** "Use the Strategy pattern when..." / "You should always use a torque wrench when..." — *when* is a list, not a hook.
- **Generic problem statement.** "Sometimes you need flexibility..." / "Precision matters..." — too vague to anchor.
