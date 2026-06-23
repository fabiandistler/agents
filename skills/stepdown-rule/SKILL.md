---
name: stepdown-rule
description: 'Write, refactor, or review functions using the stepdown rule: make code read top-down, keep each function at one level of abstraction, and extract helpers so the reader can move from orchestration to detail without jumping around. Use this skill whenever the user asks you to write functions, untangle a long function, extract helpers, follow a top-down or one-level-of-abstraction style, or make code easier to read with clean-code decomposition, even if they do not explicitly mention "stepdown".'
compatibility: Works with function-writing tasks in any language. No special dependencies.
---

# Stepdown Rule

Use this skill when code should read like a story from high-level intent to low-level detail. The reader should be able to start at the main function and descend through helpers without crossing abstraction levels inside a single block.

## Core idea

Follow one level of abstraction per function.

- Put orchestration in the top-level function.
- Push implementation details into helpers below it.
- Keep function order aligned with the call flow so the file reads naturally from top to bottom.
- Name helpers after the action they perform, not after incidental implementation details.
- Extract a helper only when it gives a clearer conceptual step; do not split code just to create more functions.

## How to apply it

1. State the main job in one sentence, usually as a "to ..." summary.
2. Write the top-level function to express that summary at a high level.
3. Break each distinct subtask into a helper at the next lower level of abstraction.
4. Keep the helpers in the same order the reader would need them.
5. Check each function for mixed concerns. If a function mixes setup, business logic, and formatting, move one of those concerns downward.
6. Prefer a clear narrative over clever reuse. If a shared helper makes the code harder to read, inline the small repeated logic instead.

## What good stepdown looks like

The top-level function should answer "what happens?" while the helpers answer "how do we do that step?"

```python
def build_monthly_report(data):
    metrics = compute_metrics(data)
    chart = render_chart(metrics)
    return assemble_report(metrics, chart)


def compute_metrics(data):
    normalized = normalize_data(data)
    return aggregate_metrics(normalized)
```

This works because the reader can scan the file once and follow the story downward: build the report, compute metrics, normalize data, aggregate metrics.

## What to avoid

- Do not mix high-level intent and low-level details in the same function.
- Do not force extra helpers when the function is already short and clear.
- Do not create wrappers that merely rename one line without adding a new conceptual step.
- Do not reorder helpers in a way that breaks the reader's sense of progression.

## When refactoring existing code

- Look for long functions that do several conceptually different things.
- Split by purpose, not by line count.
- Preserve the original story of the code when you extract helpers.
- If a function is already readable, keep it intact.

## Response format

When applying this skill to a refactor or code-generation task, write the code first and then give a brief rationale explaining how the function breakdown follows the stepdown rule. If the user only wants a review, explain where the code mixes abstraction levels and suggest the refactor instead of rewriting everything.
