---
name: llm-application-engineering
category: ai-ml
environments: coding
description: Guide the engineering of a foundation-model application across three linked decisions -- adapting the model when its output is failing, deciding what architectural piece to build next, and monitoring it live -- plus the craft-level conventions underneath them. Use whenever a foundation model's output is wrong and the fix (prompting, retrieval, or finetuning) is unclear, whenever an LLM app's architecture (context, guardrails, routing, caching, agents) is being designed or reviewed, whenever production evaluation metrics or user-feedback signals need defining, or whenever the question is how to implement prompting and prompt management, an evaluation harness or LLM judge, guardrails and security gating, finetuning (LoRA, hyperparameters), or training-data preparation. Draws on Chip Huyen's "AI Engineering" and bundles the adaptation ladder, the architecture build sequence, production monitoring, and an operational conventions sheet.
compatibility: Domain-knowledge skill, not tied to any language, framework, or model provider. Applies to any application built on a foundation model, whether self-hosted or accessed via API.
metadata:
  version: "1.2"
---

# LLM Application Engineering

Building an LLM application is not one decision but three nested ones: how to
adapt the model to the task, how to grow the surrounding system, and how to know
it is still working once users touch it. This skill bundles all three, because
they are usually needed in the same conversation and each guards against the
same failure mode — reaching for the most powerful, most complex tool before the
cheaper one has been ruled out.

For the craft-level rules underneath these three decisions — prompt engineering
and prompt management, evaluation-harness and LLM-judge configuration,
guardrails and security gating, finetuning mechanics, and training-data
preparation — open
[`references/ai-engineering-conventions.md`](references/ai-engineering-conventions.md).
It is a dense, falsifiable conventions sheet meant to be consulted when the
question is *how to implement* one of these steps well, not *which* step to take
next.

When the application is an **agent** — tool loops, orchestration topologies,
multi-agent decomposition, autonomy levels — pair that sheet with
[`references/agent-engineering-conventions.md`](references/agent-engineering-conventions.md),
its agent-specific companion (distilled from Albada, *Building Applications with
AI Agents*). It carries the tool-design, orchestration, agent-evaluation,
agent-memory-scoping, and autonomy-UX rules the general sheet does not, and
defers to the general sheet wherever they overlap.

## Part A — The adaptation ladder

When a foundation model fails at a task, finetuning is almost never the right
first move. There is an ordered ladder of adaptation techniques; each rung adds
complexity, risk, and ongoing cost, so climb only when the current rung cannot
fix the root cause.

### The rungs, in order

| # | Technique | What it is |
|---|---|---|
| 1 | **Prompting** | Structured task description, role, output format — with systematic versioning of prompts. |
| 2 | **Few-shot prompting** | 1–50 examples placed directly in the prompt. Very high leverage for the effort. |
| 3 | **Basic RAG** | Term-based retrieval (e.g. BM25), used when the failure is missing information. |
| 4 | **Advanced RAG** | Embedding-based retrieval, reranking, hybrid search — when basic retrieval is not enough. |
| 5 | **Finetuning** | Used when the problem is *behavior* (irrelevant, malformatted, unsafe responses), not missing knowledge. |
| 6 | **RAG + finetuning combined** | Largest performance boost available, but the highest combined complexity. |

### The diagnosis that gates every step up

Before moving to a higher rung, ask: **what kind of failure is this?**

- **Information failure** — the model simply did not know something → go to RAG.
- **Behavior failure** — the model knew it, but responded wrongly anyway → go to finetuning.

This distinction blocks the single most expensive wrong turn in LLM projects:
finetuning a RAG problem. More training data does not cure knowledge the model
is missing *at inference time*.

### Complexity asymmetry: RAG vs. finetuning

The two paths carry complexity in different places, which matters for where a
team wants to pay the cost:

- **Embedding-based retrieval** raises *inference-time* complexity — vector
  search on every request, added latency, embedding drift.
- **Finetuning** raises *development-time* complexity — a training pipeline,
  eval sets, hyperparameters — but leaves inference unchanged.

Latency-sensitive products with a small ML team tend toward finetuning;
data-rich products with engineering capacity tend toward RAG.

### The sample-size rule of thumb

Every rung-change decision needs an eval that can actually detect whether it
helped. Sample size needed to be 95% confident scales with a simple rule:
**every 3× decrease in the score difference to detect requires roughly 10×
more samples.**

| Difference to detect | Samples needed |
|---|---|
| 30% | ~10 |
| 10% | ~100 |
| 3% | ~1,000 |
| 1% | ~10,000 |

Practical consequences:

- **Large improvements are cheap to prove.** A few dozen examples can confirm a
  30-point win — but such wins get rarer after the first easy iterations.
- **Small improvements are expensive to prove.** Detecting a 1% gain needs
  ~10,000 eval examples *per comparison*. Monthly iteration across five
  comparison dimensions can mean 50,000+ quality annotations a month.
- **The cost curve is superlinear**, not linear: each ~3× reduction in the
  detectable effect costs roughly 9–10× more data (the rule is a mnemonic form
  of the general power-analysis result that detecting an effect of size ε
  needs a sample ∝ 1/ε²). Teams routinely underestimate this and draw
  conclusions from eval sets that are far too small.

Before climbing a rung: estimate the expected effect size first. If it is
small (~1%), either budget for a much larger eval set or reframe the
comparison around a more variance-rich indirect metric (e.g. confidence
calibration, latency) instead of end accuracy.

### Evaluation is the constant underneath every rung

None of the rungs above should be climbed without evaluation criteria and a
pipeline already in place. Without eval, every step up is a gamble — there is
no way to tell whether it helped or introduced a regression.

## Part B — Progressive architecture: five build steps

LLM applications grow more complex in a deliberate sequence, not all at once.
Each of the five steps below solves one concrete problem and should be added
only when that problem is actually present — none of them should be built
preemptively.

| Step | Name | What it adds | Add it when |
|---|---|---|---|
| 1 | **Enhance context** | Retrieval from text/image/tabular sources, tool outputs (web search, APIs) | Always first — poor context is the most common cause of poor output |
| 2 | **Put in guardrails** | Input protection (prompt-injection detection, PII filtering) and output protection (hallucination/toxicity filters) | As soon as real users can reach the system |
| 3 | **Add router and gateway** | Router sends each request to the right model (e.g. cheap model for simple queries); gateway unifies the interface across self-hosted models and APIs, centralizing load balancing, logging, caching, guardrails | As soon as more than one model or provider is in use |
| 4 | **Reduce latency with caches** | Exact cache for identical requests, semantic cache for similar ones; pick an eviction policy (LRU/LFU/FIFO) | As soon as requests repeat, or individual calls are expensive |
| 5 | **Add agent patterns** | Generated output feeds back into the system; the system may take write actions | Last, because agentic loops carry the most complexity, the biggest security risk, and the hardest evaluation |

### Why the order is not optional

Each step assumes the previous one is in place:

- Guardrails without a context layer are blind.
- A router without guardrails can send dangerous requests to a cheaper,
  less-protected model.
- Caching without a router caches the wrong answers.
- Agents without caches and guardrails are expensive, uncontrolled loops.

### Anti-pattern: building agents first

The recurring mistake is building agents (step 5) before eval, context (step
1), and guardrails (step 2) exist. This produces impressive demos and
unusable products. Treat the pattern as a maturity model: move up only once
the current step is fully exploited, not because a higher step sounds more
capable.

## Part C — Production monitoring and feedback

Classic software monitoring (MTTD, MTTR, CFR) is necessary but not sufficient
for LLM systems — it says nothing about quality, security, or drift, the
dimensions where LLMs develop their own failure modes. Production
observability for an LLM application needs two additional taxonomies on top
of the classic trio.

### Six metric families

| Family | Key metrics | Notes |
|---|---|---|
| **Latency** | TTFT (time to first token), TPOT (time per output token), total response latency | LLMs stream; a single request/response total misses the experience. High TTFT + low TPOT often signals routing/cold-start issues; low TTFT + high TPOT signals a throughput bottleneck. |
| **Quality** | Format validity (valid JSON, required fields), factual consistency / hallucination rate (via AI judges or ground truth), conciseness, creativity | The most expensive family — needs either a second model call or human labeling; sampling strategy is mandatory. |
| **Security / guardrails** | Toxicity rate, PII-detection rate, guardrail-trigger frequency, refusal rate | A rising guardrail-trigger trend is an early warning of adversarial traffic; a sudden refusal-rate jump often means a provider silently changed the model's refusal behavior. |
| **User behavior** | Early-termination rate, turns per conversation, input/output token distribution, prompt complexity | Implicit signals that need no user annotation — see the feedback signals below. |
| **Cost** | Input/output token volume, tokens per second (TPS), rate-limit hits | Rate-limit hits should trigger scaling or routing decisions. |
| **Drift** | System-prompt drift, user-behavior drift, provider-model drift | The most underestimated family. The first two have no classic-software equivalent; provider drift (silent model updates behind an API) is detectable only through periodic probing with fixed reference inputs. |

Supporting layer: all six families depend on high-granularity, append-only
logs (endpoint, sampling settings, full prompt templates — not just user
input, tool-call intermediate outputs, crashes) and tracing that reconstructs
request timelines. Without traces, debugging a multi-step agent is guesswork.

### Five implicit-feedback signals

Explicit feedback (thumbs up/down, stars) is rare and biased in conversational
AI — only frustrated or delighted users bother. Implicit feedback is
generated by every conversation automatically: it is proprietary, continuous,
and honest (behavior shows what a rating hides).

| Signal | What it looks like | Read as |
|---|---|---|
| **Early termination** | User stops generation mid-stream, closes the app, ignores the answer | Practically always negative — one of the best chat-app health metrics |
| **Error correction** | Follow-up starts with "No…", "I meant…", "That's not what I wanted…" | Retroactively marks the previous assistant message as a failure; detectable with a narrow classifier |
| **Complaints / sentiment drops** | Direct criticism, unspecific frustration ("ugh", "nope"), a shift from polite to curt phrasing | Aggregate with a sentiment tracker on the user side of the dialogue |
| **Regeneration requests** | User clicks "regenerate" or re-asks the same question | The clearest signal — the first answer was bad enough that the user actively requested a second try; regeneration rate is a direct A/B metric |
| **Implicit follow-up (downstream action)** | e.g. a recommended product gets purchased | Positive signal without an explicit click, but requires telemetry/identity mapping to observe the downstream action at all |

Aggregate these on two loops: short-term (hours — dashboards, spike alerts on
termination/regeneration rate, fast rollback) and long-term (days to weeks —
training and eval data for the next model iteration; error-correction
patterns become negative examples, corrected follow-ups become positive
examples). Because this is behavioral data, disclose its use and offer an
opt-out — lost trust costs more than the data is worth.

### Baseline checklist before calling anything deployment-worthy

Independent of the metric families above, compare a model against five
baseline types before considering it fit to deploy — this guards against "a
good model with good metrics that is still not good enough":

1. **Random baseline** — random predictions (the floor).
2. **Simple heuristic** — a domain rule (e.g. "spam if >5 links").
3. **Zero-rule baseline** — always predict the most frequent class.
4. **Human baseline** — expert human performance on the same task.
5. **Existing solution** — whatever system is currently in production.

The model must clearly beat the random, simple-heuristic, and zero-rule
baselines, and beat the existing production solution if one exists. The human
baseline is a reference ceiling rather than a pass/fail gate: measure the gap
to expert performance and decide whether that gap is acceptable for the use
case.

## Applying the three parts together

The parts compose: Part A decides *what adaptation to apply* when output
quality is the problem. Part B decides *what to build next* when the
application's surrounding system is the problem — and its step 1 (Enhance
Context) is exactly where basic/advanced RAG from Part A gets implemented
in practice; context construction is the same discipline as feature
engineering was for classical ML, just with retrieved information standing
in for engineered columns. Part C decides *how to know* whether either
change actually helped once it reaches users, and feeds new failure evidence
back into Part A's diagnosis step.

## Common pitfalls to avoid

- Reaching for finetuning when the eval shows an information failure, not a
  behavior failure.
- Climbing an adaptation rung on an eval set too small to detect the effect
  size actually at stake.
- Building a router, cache, or agent loop before the step beneath it
  (context, guardrails) is solid — each skipped step becomes blind or unsafe.
- Building agents first because they demo well, before eval, context, and
  guardrails exist.
- Monitoring only classic DevOps metrics (MTTD/MTTR/CFR) and missing
  quality, security, and drift entirely.
- Treating explicit feedback (thumbs up/down) as the whole feedback picture
  and ignoring the richer, continuous implicit signals.
- Declaring a model deployment-worthy without checking it against all five
  baseline types.
