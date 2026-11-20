---
name: llm-application-engineering
category: ai-ml
environments: coding
description: "Engineers LLM applications: fixing bad output (prompting, RAG, finetuning), evals and LLM judges, agents and tools, guardrails, and production monitoring. Use when building or debugging an app on top of an LLM."
metadata:
  version: "1.2"
---

# LLM Application Engineering

## When to use

- Model output is wrong and the fix (prompting, retrieval, finetuning) is unclear.
- An LLM app's architecture (context, guardrails, routing, caching, agents) is designed or reviewed.
- Production metrics or user-feedback signals need defining.
- A step needs implementing: prompts, an eval harness or judge, guardrails, finetuning, training data, or a UI that shows model output.

All three parts below guard against one failure: reaching for the more complex
tool before the cheaper one is ruled out.

## References

Open the file for the topic you are implementing:

- [`references/evaluation.md`](references/evaluation.md): eval harness, LLM judges, agent evaluation, rollout experiments, production metrics and implicit feedback.
- [`references/agents-and-tools.md`](references/agents-and-tools.md): tool design, orchestration, context and retrieval, autonomy and escalation.
- [`references/security.md`](references/security.md): guardrails, context authorization, database scope, agent security.
- [`references/adaptation-and-serving.md`](references/adaptation-and-serving.md): prompting, finetuning, training data, serving, cost caps.
- [`references/result-surface.md`](references/result-surface.md): any UI that shows model output; list the unmet rules in the change description or review notes.
- [`references/agent-pipelines.md`](references/agent-pipelines.md): multi-stage or unattended pipelines; grader separation, code-review meta-grading, controlled external writes.

## Part A — The adaptation ladder

When a model fails at a task, climb this ladder one rung at a time, and only
when the current rung cannot fix the root cause: each rung adds complexity,
risk, and ongoing cost.

### The rungs, in order

| # | Technique | What it is |
|---|---|---|
| 1 | **Prompting** | Zero-shot task description first on reasoning models, with systematic versioning of prompts. |
| 2 | **Structured outputs** | Schema-constrained outputs or tool schemas for format failures — fix format without training. |
| 3 | **Few-shot prompting** | A few diverse canonical examples; skip step-by-step scaffolds on reasoning models. |
| 4 | **Stronger model** | A stronger model or enabled reasoning when the failure is capability, not knowledge. |
| 5 | **Cached long context** | Whole knowledge base in a cached prompt that fits the model's context window (check the provider's current limits); still prefer retrieval for fact-seeking or freshness-critical data. |
| 6 | **Retrieval** | Hybrid plus contextual chunks plus rerank as the default, or agentic search, when the failure is missing information. |
| 7 | **Finetuning** | Used when the problem is *behavior* (irrelevant, unsafe responses), not missing knowledge or format. Largest boost combined with retrieval, at the highest complexity. |

### The diagnosis that gates every step up

Before moving to a higher rung, ask: **what kind of failure is this?**

- **Information failure** — the model simply did not know something → go to retrieval or cached long context.
- **Format failure** — the content is right but the shape is wrong → go to structured outputs.
- **Behavior failure** — the model knew it, but responded wrongly anyway → go to finetuning.

This distinction blocks the single most expensive wrong turn in LLM projects:
finetuning a RAG problem. More training data does not cure knowledge the model
is missing *at inference time*.

### The sample-size rule of thumb

Every rung change needs an eval that can detect whether it helped. At 95%
confidence, **every 3× decrease in the score difference to detect needs
roughly 10× more samples.**

| Difference to detect | Samples needed |
|---|---|
| 30% | ~10 |
| 10% | ~100 |
| 3% | ~1,000 |
| 1% | ~10,000 |

Estimate the expected effect size before climbing. If it is small (~1%),
budget a much larger eval set or compare on a more variance-rich indirect
metric (e.g. confidence calibration, latency) instead of end accuracy.

### Error analysis first

Climb no rung without an eval in place. Start it from outputs, not from
metrics:

1. Sample about 100 traces from current behavior.
2. Take free-form notes on each trace (open coding).
3. Group the notes into a failure taxonomy (axial coding).
4. Count traces per category.
5. Fix cheap failures directly; write code checks or binary judges only for persistent categories.
6. Re-run the set on every change (CI).

## Part B — Progressive architecture: five build steps

Add each step only when its trigger is present, never preemptively. The
numbers give the usual order; the "Add it when" line decides each step.

- **1. Enhance and minimize context**
  - What it adds: Retrieval from text/image/tabular sources, tool outputs (web search, APIs); keep the smallest high-signal context — see Context engineering in `references/agents-and-tools.md`
  - Add it when: Always first — poor context is the most common cause of poor output
- **2. Put in guardrails**
  - What it adds: Input protection (prompt-injection detection, PII filtering) and output protection (hallucination/toxicity filters)
  - Add it when: As soon as real users can reach the system
- **3. Add router and gateway**
  - What it adds: Router sends each request to the right model (e.g. cheap model for simple queries); gateway unifies the interface across self-hosted models and APIs, centralizing load balancing, logging, caching, guardrails
  - Add it when: As soon as more than one model or provider is in use
- **4. Reduce latency with caches**
  - What it adds: Prompt cache for shared prefixes first; then exact cache for identical requests, semantic cache for similar ones; pick an eviction policy (LRU/LFU/FIFO). Order prompts static-first — system, tools, documents — dynamic content last; never interpolate timestamps or IDs into the prefix
  - Add it when: As soon as requests repeat, or individual calls are expensive
- **5a. Add predefined workflows**
  - What it adds: Chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer — fixed paths where generated output feeds back into the system
  - Add it when: When the path through the system can be predefined
- **5b. Add autonomous agents**
  - What it adds: The model plans its own path and the system may take write actions
  - Add it when: Last: only when the path cannot be predefined, and only once eval, context (step 1) and guardrails (step 2) exist — agentic loops carry the most complexity, the biggest security risk, and the hardest evaluation

### Dependencies between the steps

A step whose trigger is absent is skipped, even if a later one applies: a
single-model app needs no router before prompt caching. Only these
dependencies hold, each when both steps are present:

- Output checks for hallucination compare the answer against the retrieved
  context, so they need the context layer of step 1.
- When a router or gateway is added, enforce guardrails in front of it or in
  the gateway, so every model it can route to is covered, including the
  cheaper ones.
- An exact or semantic cache sits behind the input guardrails and is scoped to
  whatever changes the answer (user or tenant permissions, model); otherwise it
  skips the checks or serves one user's answer to another.
- Autonomous agents need guardrails on every write action before real users
  can reach them.

## Part C — Production monitoring and feedback

Track six metric families on top of classic service monitoring: latency
(TTFT, TPOT), quality, security and guardrails, user behavior, cost, and
drift. What each family measures, the patterns that signal trouble, and the
five implicit-feedback signals are in
[`references/evaluation.md`](references/evaluation.md#production-metrics-and-feedback).

All six rest on append-only logs (endpoint, sampling settings, full prompts as
sent, tool-call intermediate outputs, crashes) and on traces that reconstruct
each request. Redact PII before the logs leave the service
(`references/security.md`).

### Baseline checklist before calling anything deployment-worthy

For classifiers, use the five-baseline gate in `members/ml-project-lifecycle/SKILL.md` Part A, read via the `ai-ml` router. For generative apps, compare against these four instead: the current prompt and model version as the regression baseline, the strongest available model as the ceiling, a simple non-LLM heuristic or template, and a human expert. Ship only when the candidate beats the regression baseline and the heuristic, and the gap to the ceiling and the expert is acceptable for the use case.
