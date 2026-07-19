# AI-Agent Engineering Conventions

> Operational rules distilled from Rebecca Albada, *Building Applications with
> AI Agents* (O'Reilly, 2025). This sheet is the **agent-specific** companion to
> `ai-engineering-conventions.md` (Chip Huyen, *AI Engineering*): where that
> sheet and `../SKILL.md` already cover a topic — the adaptation ladder,
> prompt-management, LLM-judge configuration, guardrail input/output basics,
> PII masking before third-party calls, finetuning mechanics, the six monitoring
> metric families — **they are authoritative and it is not repeated here.** This
> sheet carries only what building an *agent* (tool loops, orchestration,
> multi-agent, autonomy) adds on top. References are book chapter numbers
> `(Ch. N)`.
>
> Keep-filter: counter-default, quantitative heuristic, or security-relevant.
> Generic best practice a competent model already follows is omitted.

## Tool Design

_Net-new vs. the Huyen sheet, which covers guardrails and code-sandboxing but
not tool-as-interface design._

- **Register only narrowly scoped operations as tools — never a generic
  "run SQL" / "execute code" endpoint.** (Ch. 4)
  - ✅ `get_user_profile(user_id)`, `cancel_order(order_id)`
  - ❌ `execute_sql(query: str)`   ← likely-default
- **Give a read-only agent no write/delete tools, and give the agent's DB
  account only the privileges its registered tools need.** (Ch. 4)
- **Treat tool metadata as the selection interface: a precise narrow name, a
  description that overlaps with no other tool, one example invocation, and
  explicit type/range constraints.** Overlapping descriptions are the main cause
  of tool misselection. (Ch. 4–5)
  - ✅ `calculate_sum — Returns the sum of two integers x, y in [0, 1000]. E.g. calculate_sum(2, 3) -> 5`
  - ❌ `process_numbers — Handles number operations`   ← likely-default
- **Define a machine-readable schema (JSON Schema / Pydantic / Zod) for every
  tool and validate every proposed call against it before executing; on
  mismatch, prompt the model to correct only the broken portion, then fall back
  (backup model, cached data, safe default).** (Ch. 4, 7)
- **Log every tool invocation with parameters; alert on anomalous patterns**
  (mass deletions, schema-altering calls). (Ch. 4)
- **Set `tool_choice` explicitly (`auto`/`required`/`none`/pinned) per call path
  instead of instructing tool use in the prompt.** (Ch. 4)
- **In production, prefer pre-built, tested tools over agent-generated
  per-invocation code** (no repeatability); any model-generated tool code gets
  human review before entering CI/CD. (Ch. 4)

## Orchestration & Context

- **Default to semantic tool selection (embed descriptions, retrieve top-k from
  a vector index) once the toolset grows;** use two-stage hierarchical selection
  only for large, semantically similar toolsets (it costs latency); plain
  in-prompt selection is fine for small toolsets. (Ch. 5)
- **Choose the simplest topology that meets the requirement, in order: single
  tool → parallel → chain → graph.** Adopt a graph only when you must both
  branch *and* consolidate results. (Ch. 5)
  - ❌ reaching for a multi-node graph framework for a linear prompt→tool→answer flow   ← likely-default
- **Cap chain length and graph depth/branching factor — errors compound per
  step. Unit-test every router function and verify every path reaches a terminal
  node.** (Ch. 5)
- **Place the most relevant context immediately before the end of the prompt;**
  models miss information buried mid-prompt. (Ch. 6)
- **Before splitting into multiple agents, first exhaust single-agent options:
  tool grouping, hierarchical or semantic selection.** Decompose only when tool
  count/responsibilities measurably degrade selection reliability, and add the
  minimum number of agents — each adds coordination overhead, latency, and token
  cost. (Ch. 8)
  - ❌ one agent per "role" from the start   ← likely-default
- **Use an actor–critic loop (generate → score against rubric → regenerate) when
  evaluating is easier than generating and a checklist exists;** it buys quality
  with test-time compute, no training. (Ch. 8)

## Agent Evaluation

_Extends the Huyen sheet's Evaluation section with the trajectory-level
structure agents need; generic judge configuration lives there._

- **Ship the first agent version with eval cases that assert: correct tool
  called, correct parameters, response contains required phrases.** Track tool
  recall, tool precision, parameter accuracy, phrase recall, task success.
  (Ch. 2, 9)
- **Structure each eval example as input state + conversation history + expected
  final state** (expected `tool_calls` with params, `customer_msg_contains`), so
  scoring is automatable. (Ch. 9)
- **Every change that adds a tool or workflow adds matching eval cases in the
  same change** — the eval set is the living spec. (Ch. 9)
- **Export production failures AND exemplary successes (golden paths) as
  regression eval cases;** grow the set by LLM-generating adversarial/
  counterfactual variants with human review before inclusion. (Ch. 9–11)

## Memory & Retrieval

_Escalate-only-on-need is already the SKILL.md Part A principle; these are the
agent-memory deltas._

- **Reach for GraphRAG only when vector retrieval demonstrably fails on
  multi-hop questions** — it prototypes in minutes but productionizing it is a
  major undertaking. (Ch. 6)
- **Don't replace retrieval with long context: for fact-seeking queries and
  freshness-critical data, selective retrieval still outperforms dumping the
  corpus into a million-token window.** (Ch. 6)

## Deployment & Learning

_The Huyen sheet covers finetuning mechanics and the nonparametric-first ladder;
these are the agent-rollout specifics._

- **A/B tests on stateful agents need sticky user/session-level variant
  assignment;** reassignment mid-history corrupts both arms. (Ch. 11)
- **Shadow-deploy risky agent changes (same inputs, outputs logged not served)
  before any canary exposure.** (Ch. 10–11)

## Monitoring

_Extends SKILL.md Part C (the six metric families) with observability-stack
integration and drift triage._

- **Route agent telemetry into the same observability stack as other services —
  no separate agent-monitoring silo.** Tag spans/logs with session ID,
  agent/prompt version, and workflow ID so traces and logs correlate. (Ch. 10)
- **Triage failures with a reproducibility test before reacting: rerun 3–5×;
  ≥80% failure rate = systematic bug for engineering; otherwise check drift
  statistically (PSI > 0.25 major / > 0.1 minor, KS > 0.1)** instead of chasing
  single-sample noise. (Ch. 10)
- **Escalate to a human on low model certainty (self-reported score < ~0.7 or
  >20% divergence across an ensemble of runs) or high consequence;** tune
  thresholds so < ~10% of cases escalate. (Ch. 11)

## Security

_Kept even where obvious — the cost of an agent guessing wrong is high. Input/
output guardrails and PII masking before third-party calls live in the Huyen
sheet; these are the agent/MCP-specific additions._

- **Treat all retrieved external content (web pages, documents, tool outputs) as
  untrusted input — indirect prompt injection arrives through data, not the
  user.** Benchmark defenses with PINT/BIPIA. (Ch. 12)
- **Never log user messages, prompts, or PII in plaintext observability data;**
  scrub/redact at span export, and isolate monitoring backends with RBAC.
  (Ch. 10, 12)
- **MCP does not mandate authentication/authorization — wrap MCP endpoints in
  your own network policy or proxy layer with authn, RBAC, and audit logs.**
  (Ch. 4)
- **Sandbox agent execution and isolate third-party tool dependencies**
  (containers/venvs); rate-limit all agent-facing endpoints; use parameterized
  statements for any DB access. (Ch. 4, 12)
- **Scope agent memory strictly: personal-agent memory is isolated by default,
  an agent never assumes cross-scope access to personal or shared data, and
  memory must be inspectable and deletable by the user.** (Ch. 13)
- **Red-team before AND after every significant model/prompt change** — it's a
  recurring activity, not a launch checkbox (DeepTeam, Garak, PyRIT). (Ch. 12)

## UX

- **Expose autonomy as an explicit user control (Manual / Assist / Auto) with
  defined behavior per level — don't hardcode one autonomy level.** (Ch. 3)
- **Classify each interaction explicitly as synchronous or asynchronous and
  design status communication for the async ones; never leave users watching a
  spinner on a long-running task.** (Ch. 3)
