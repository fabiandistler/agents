---
name: problem-first-explanation
category: communication
environments: coding, chat
description: Output-form skill for technical explanations. Forces every explanation to start with the concrete problem the concept solves, before introducing the abstract solution or implementation. Use when writing documentation, README files, tutorials, code comments, design rationale, ADR motivation sections, or when the user asks Claude to "explain X". Triggers on "explain", "document", "tutorial", "README", "what is X", "why does X exist".
---

# Problem-First Explanation

A small, sharp output-form skill: **never explain a concept before the reader knows what problem it solves.** Forces the three-step structure Problem → Solution → Implementation in any technical writing.

## When to invoke

- Writing or editing a README, package description, design rationale, or ADR motivation.
- Adding a docstring or roxygen2 `@description` block.
- Explaining a design pattern, library, framework, or architectural choice.
- The user asks "explain X" or "what is X" or "why do we use X".
- Reviewing an explanation that feels abstract or hard to follow — the diagnosis is usually a missing problem statement.

Do **not** invoke for: pure reference docs (API parameter tables), already-concrete how-to guides where the problem is obvious from the title.

## The three-step structure

### 1. Problem (concrete, not abstract)
Describe the **specific situation** that creates a need. Use a scenario, a code smell, or a pain point — not a category.

- ✗ "When you need to add behaviour to a class..." (abstract, no urgency)
- ✓ "You have an Order class with a `format()` method. Marketing wants to optionally add a gift-wrap note, a discount banner, and a tracking link to a confirmation — in any combination. Subclassing produces an explosion of OrderWithGiftNote, OrderWithBanner, OrderWithGiftNoteAndBanner..." (concrete, the reader feels the pain)

### 2. Solution (conceptual, named)
Introduce the concept as a **direct response** to the pain just described. Name it. State what it does in one sentence. Do not yet show code.

- ✗ "There is a pattern called Decorator that wraps objects..." (definitional, doesn't hook the problem)
- ✓ "The Decorator pattern solves this: instead of subclassing, you wrap the original `Order` in decorators (`GiftNoteDecorator`, `BannerDecorator`) that each add one embellishment around the original `format()`. Any combination is a stack of wrappers, not a new subclass." (links solution to pain)

### 3. Implementation (concrete code)
Now show how. Code, signature, sequence diagram, whatever fits. The reader has the mental model already, so the implementation reads as "of course, that follows".

## Why this order works

Two cognitive mechanisms:

- **Anchor before abstraction.** A concrete problem creates a mental model the reader can hang the abstract solution on. Without the anchor, the abstraction floats — readers ask "why?" instead of "ah, so that's why!".
- **Relevance before completeness.** Listing all features of a concept is overwhelming. Showing how it solves a specific problem makes the rest feel optional.

This is universal — it shows up in `Domain-Driven Design` teaching, in good API docs, in Ousterhout's writing, in tracer-bullet tutorials. It is the same principle behind problem-oriented design as a universal principle: solutions emerge from problem understanding, not from abstract first principles.

## Minimum viable check

Before publishing any explanation, the reader should be able to answer **after the first paragraph**:

- [ ] What concrete situation does this solve?
- [ ] What is the concept *called* and what does it do in one sentence?

If either is no, the structure is wrong — restart from step 1.

## Failure modes to refuse

- **Definitional opener.** "X is a pattern that..." — definitions before pain. Restart with a concrete scenario.
- **Implementation-first.** Code dump followed by "this does Y." — readers can't parse code without a mental model.
- **Solution before problem.** "Use the Strategy pattern when..." — when is a list, not a hook.
- **Generic problem statement.** "Sometimes you need flexibility..." — too vague to anchor.
