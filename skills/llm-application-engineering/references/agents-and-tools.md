# Agent and tool conventions

Rules for tool design, orchestration, context and retrieval, and autonomy and escalation.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Tool design](#tool-design)
- [Orchestration](#orchestration)
- [Context and retrieval](#context-and-retrieval)
- [Autonomy and escalation](#autonomy-and-escalation)

## Tool design

- **Expose narrow tools by default; expose SQL only through a constrained query
  interface. Give a read-only agent no write/delete tools, and grant its
  account only the privileges those tools need.** Never provide unrestricted
  `execute_sql(query)` or code execution. Database grants enforce the scope
  (`security.md`, Access and authorization). (Albada Ch. 4)
  - ✅ `get_user_profile(user_id)`, `cancel_order(order_id)`
  - ❌ `execute_sql(query: str)` with broad database access
- **Treat tool metadata as the selection interface: a precise narrow name, a
  description that overlaps with no other tool, one example invocation, and
  explicit type/range constraints.** Overlapping descriptions are the main cause
  of tool misselection. (Albada Ch. 4–5)
  - ✅ `calculate_sum — Returns the sum of two integers x, y in [0, 1000]. E.g. calculate_sum(2, 3) -> 5`
  - ❌ `process_numbers — Handles number operations`
- **Generate any data-schema text in a tool description — table/field names,
  enum values, example queries — from the live schema or from a fixture
  generated from it and checked in; never hand-write it or copy it from a
  mock. Stamp the fixture with its schema revision, and make every example
  query in the description execute against it.** A wrong name in the
  description reaches the model with the authority of a spec; a runtime guess
  at least looks like a guess.
- **Define a machine-readable schema (JSON Schema / Pydantic / Zod) for every
  tool and turn on the provider's strict tool use (`strict: true`), which
  constrains sampling to the schema. Where strict mode is unavailable, validate
  every proposed call before executing it; on mismatch, prompt the model to
  correct only the broken portion, then fall back (backup model, cached data,
  safe default).** (Albada Ch. 4, 7; Anthropic strict tool use, OpenAI structured outputs)
- **Log every tool invocation with parameters; alert on anomalous patterns**
  (mass deletions, schema-altering calls). (Albada Ch. 4)
- **Set `tool_choice` explicitly (`auto`/`required`/`none`/pinned) per call path
  instead of instructing tool use in the prompt.** (Albada Ch. 4)
- **Model-generated code that becomes a registered tool gets human review
  before it enters CI/CD.** (Albada Ch. 4)
- **If a tool stays error-prone after prompting, examples, and finetuning,
  replace the tool with a simpler interface** — don't keep patching the agent.
  (Huyen Ch. 6)
- **Namespace tools by domain so names never collide across groups.**
  - ✅ `orders_cancel`, `users_get_profile`
  - ❌ `cancel`, `get`
- **Return token-efficient responses by default: paginate lists, accept filters, truncate with a default limit.**
  - ✅ `list_orders(limit=20, status="open") -> page plus next cursor`
  - ❌ `list_orders() -> all 10,000 rows`
- **When a tool's result can exceed a token budget (~20k tokens), write the full
  result to a file or handle and return only its path, size and a short
  head/tail preview; pair it with a paged read tool (`offset`, `limit`) so the
  agent reads only the slice it needs.** Truncation drops the part the agent may
  need; offloading keeps it reachable without filling the window.
  - ✅ `export_orders() -> {"path": "results/export_42.json", "tokens": 180000, "head": "...", "tail": "..."}` plus `read_file(path, offset=0, limit=100)`
  - ❌ `export_orders() -> the full 180k-token export inline`
- **Return high-signal values, not raw IDs — resolve names the agent can act on.**
  - ✅ `{"id": 42, "customer": "Acme GmbH", "status": "open"}`
  - ❌ `{"id": 42, "cid": 7, "s": 1}`
- **Return actionable errors naming what failed and what to try next.**
  - ✅ `order 42 not found in open orders; check status or create it`
  - ❌ `error 400`

## Orchestration

- **Choose the simplest topology that meets the requirement, in order: single
  tool → parallel → chain → graph.** Adopt a graph only when you must both
  branch *and* consolidate results. (Albada Ch. 5)
- **Cap chain length and graph depth/branching factor — errors compound per
  step. Unit-test every router function and verify every path reaches a terminal
  node.** (Albada Ch. 5)
- **Before splitting into multiple agents, first exhaust single-agent options:
  tool grouping, hierarchical or semantic selection.** Decompose only when tool
  count/responsibilities measurably degrade selection reliability, and add the
  minimum number of agents — each adds coordination overhead, latency, and token
  cost. (Albada Ch. 8)
- **Use an evaluator-optimizer loop (generate → score against rubric →
  regenerate) when evaluating is easier than generating and a checklist
  exists;** it buys quality with test-time compute, no training. (Albada Ch. 8)

## Context and retrieval

- **Keep the smallest high-signal context that solves the task, and budget
  operating context well below the documented window, with headroom for tool
  outputs and multi-turn growth.** Context rot degrades quality well below
  documented limits.
- **Set compaction and clearing thresholds for long agent loops** — compact or clear at a fixed turn or token count, not when the window errors.
- **Keep structured notes outside the window** for persistent state across turns and sessions.
- **Isolate sub-agent context: sub-agents return condensed summaries, never full transcripts.**
- **Expose a corpus to an agent as a query interface — never as one tool per
  document, never as whole documents in the response — and load identifiers
  first, fetching content on demand.** Both the tool list and the payload are
  context cost, paid on every turn. A search or query tool over the corpus
  (SQL over a trace store, search over a knowledge directory) keeps both flat
  as the corpus grows; one tool per document grows the tool list linearly.
- **Prefer provider-native tool search and deferred loading once the toolset grows;** fall back to DIY embedding top-k selection only where native search is unavailable; plain
  in-prompt selection is fine for small toolsets.
- **Reach for GraphRAG only when vector retrieval demonstrably fails on
  multi-hop questions** — it prototypes in minutes but productionizing it is a
  major undertaking. (Albada Ch. 6)

## Autonomy and escalation

- **For agents with interactive users, expose autonomy as an explicit user
  control (Manual / Assist / Auto) with defined behavior per level. For
  unattended agents, define autonomy and approval policy in job configuration.**
  (Albada Ch. 3)
- **Classify each interaction explicitly as synchronous or asynchronous and
  design status communication for the async ones; never leave users watching a
  spinner on a long-running task.** (Albada Ch. 3)
- **A failed tool or API call is its own outcome class in user-facing agents:
  surface the failure, name what is missing, offer one next step** (retry,
  rephrase, human). Never answer from parametric knowledge as if the tool had
  returned — a silent fallback is worse than a visible failure. Log every such
  failure with tool name and input. (Albada Ch. 3)
- **Escalate to a human on low model certainty (>20% divergence across an
  ensemble of runs, or low mean token logprobs) or high consequence;** a
  self-reported confidence score is a weak tiebreaker only, since verbalized
  confidence is poorly calibrated. Tune thresholds so < ~10% of cases
  escalate. (Albada Ch. 11; Xiong et al., ICLR 2024)
