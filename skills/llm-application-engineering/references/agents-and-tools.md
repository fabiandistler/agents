# Agent and tool conventions

Rules for tool design, orchestration, context engineering, agent memory and autonomy UX.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Tool Design](#tool-design)
- [Agents](#agents)
- [Orchestration & Context](#orchestration--context)
- [Context engineering](#context-engineering)
- [Memory & Retrieval](#memory--retrieval)
- [UX](#ux)

## Tool Design

_Net-new vs. the Huyen sheet, which covers guardrails and code-sandboxing but
not tool-as-interface design._

- **Expose narrow tools by default; expose SQL only through a constrained query
  interface.** Never provide unrestricted `execute_sql(query)` or code execution.
  For read-only database access, limit the connection to approved views with
  database grants (see `security.md`, Guardrails & security). (Albada Ch. 4)
  - ✅ `get_user_profile(user_id)`, `cancel_order(order_id)`
  - ❌ `execute_sql(query: str)` with broad database access   ← likely-default
- **Give a read-only agent no write/delete tools, and grant its account only the
  privileges those tools need.** (Albada Ch. 4)
- **Treat tool metadata as the selection interface: a precise narrow name, a
  description that overlaps with no other tool, one example invocation, and
  explicit type/range constraints.** Overlapping descriptions are the main cause
  of tool misselection. (Albada Ch. 4–5)
  - ✅ `calculate_sum — Returns the sum of two integers x, y in [0, 1000]. E.g. calculate_sum(2, 3) -> 5`
  - ❌ `process_numbers — Handles number operations`   ← likely-default
- **Generate any data-schema text in a tool description — table/field names,
  enum values, example queries — from the live schema or from a fixture
  generated from it and checked in; never hand-write it or copy it from a
  mock. Stamp the fixture with its schema revision, and make every example
  query in the description execute against it.** A wrong name in the
  description reaches the model with the authority of a spec; a runtime guess
  at least looks like a guess.
  - ✅ `description` built from `schema_fixture.json` (rev `2026-10-02`); example queries run in tests
  - ❌ field list hand-typed into the description from a mock schema   ← likely-default
- **Define a machine-readable schema (JSON Schema / Pydantic / Zod) for every
  tool and validate every proposed call against it before executing; on
  mismatch, prompt the model to correct only the broken portion, then fall back
  (backup model, cached data, safe default).** (Albada Ch. 4, 7)
- **Log every tool invocation with parameters; alert on anomalous patterns**
  (mass deletions, schema-altering calls). (Albada Ch. 4)
- **Set `tool_choice` explicitly (`auto`/`required`/`none`/pinned) per call path
  instead of instructing tool use in the prompt.** (Albada Ch. 4)
- **In production, prefer pre-built, tested tools over agent-generated
  per-invocation code** (no repeatability); any model-generated tool code gets
  human review before entering CI/CD. (Albada Ch. 4)
- **Namespace tools by domain so names never collide across groups.**
  - ✅ `orders_cancel`, `users_get_profile`
  - ❌ `cancel`, `get`   ← likely-default
- **Return token-efficient responses by default: paginate lists, accept filters, truncate with a default limit.**
  - ✅ `list_orders(limit=20, status="open") -> page plus next cursor`
  - ❌ `list_orders() -> all 10,000 rows`   ← likely-default
- **When a tool's result can exceed a token budget (~20k tokens), write the full
  result to a file or handle and return only its path, size and a short
  head/tail preview; pair it with a paged read tool (`offset`, `limit`) so the
  agent reads only the slice it needs.** Truncation drops the part the agent may
  need; offloading keeps it reachable without filling the window. This is the
  registered-tool counterpart of the output bound in the "Scripts an agent
  runs" instruction (85).
  - ✅ `export_orders() -> {"path": "results/export_42.json", "tokens": 180000, "head": "...", "tail": "..."}` plus `read_file(path, offset=0, limit=100)`
  - ❌ `export_orders() -> the full 180k-token export inline`   ← likely-default
- **Return high-signal values, not raw IDs — resolve names the agent can act on.**
  - ✅ `{"id": 42, "customer": "Acme GmbH", "status": "open"}`
  - ❌ `{"id": 42, "cid": 7, "s": 1}`   ← likely-default
- **Return actionable errors naming what failed and what to try next.**
  - ✅ `order 42 not found in open orders; check status or create it`
  - ❌ `error 400`   ← likely-default
- **Iterate tools from evals: every tool addition or rename ships with eval cases asserting correct selection and parameters.** (Albada Ch. 9)

## Agents

_Extends SKILL.md Part B step 5._

- **Evaluate agents per failure mode with explicit metrics:** % valid plans,
  invalid-tool calls, valid-tool-with-invalid-params calls, wrong parameter
  values, plus steps and cost per task. (Huyen Ch. 6)
- **If a tool stays error-prone after prompting, examples, and finetuning,
  replace the tool with a simpler interface** — don't keep patching the agent.
  (Huyen Ch. 6)
- **A failed tool or API call is its own outcome class in user-facing agents:
  surface the failure, name what is missing, offer one next step** (retry,
  rephrase, human). Never answer from parametric knowledge as if the tool had
  returned — a silent fallback is worse than a visible failure. Log every such
  failure with tool name and input. (Albada Ch. 3)
  - ❌ falling back to a model-only answer when the tool errors   ← likely-default
- **Treat deadlines as a task constraint:** a correct agent output delivered too
  late is a failure. (Huyen Ch. 6)
- **Expose a corpus to an agent as a query interface — never as one tool per
  document, never as whole documents in the response.** Both the tool list and
  the payload are context cost, paid on every turn. A search or query tool over
  the corpus (SQL over a trace store, search over a knowledge directory) keeps
  both flat as the corpus grows; one tool per document grows the tool list
  linearly. Measured: ~97% fewer input tokens from tool search over large tool
  collections, ~17× cheaper than passing whole traces.
  - ❌ one MCP tool per knowledge file   ← likely-default

## Orchestration & Context

- **Prefer provider-native tool search and deferred loading once the toolset grows;** fall back to DIY embedding top-k selection only where native search is unavailable; plain
  in-prompt selection is fine for small toolsets.
- **Choose the simplest topology that meets the requirement, in order: single
  tool → parallel → chain → graph.** Adopt a graph only when you must both
  branch *and* consolidate results. (Albada Ch. 5)
  - ❌ reaching for a multi-node graph framework for a linear prompt→tool→answer flow   ← likely-default
- **Cap chain length and graph depth/branching factor — errors compound per
  step. Unit-test every router function and verify every path reaches a terminal
  node.** (Albada Ch. 5)
- **Place the most relevant context immediately before the end of the prompt;**
  models miss information buried mid-prompt. (Albada Ch. 6)
- **Before splitting into multiple agents, first exhaust single-agent options:
  tool grouping, hierarchical or semantic selection.** Decompose only when tool
  count/responsibilities measurably degrade selection reliability, and add the
  minimum number of agents — each adds coordination overhead, latency, and token
  cost. (Albada Ch. 8)
  - ❌ one agent per "role" from the start   ← likely-default
- **Use an actor–critic loop (generate → score against rubric → regenerate) when
  evaluating is easier than generating and a checklist exists;** it buys quality
  with test-time compute, no training. (Albada Ch. 8)

## Context engineering

_Extends SKILL.md Part B step 1. Minimize first, then enhance._

- **Keep the smallest high-signal context that solves the task — never fill the window because it fits.** Context rot degrades quality well below documented limits.
  - ❌ dumping the corpus into the window because the model accepts it   ← likely-default
- **Budget operating context well below the documented window**, with headroom for tool outputs and multi-turn growth.
- **Set compaction and clearing thresholds for long agent loops** — compact or clear at a fixed turn or token count, not when the window errors.
- **Keep structured notes outside the window** for persistent state across turns and sessions.
- **Isolate sub-agent context: sub-agents return condensed summaries, never full transcripts.**
  - ❌ forwarding full conversation history between agents   ← likely-default
- **Load identifiers first and fetch content on demand** — just-in-time retrieval over preloaded documents.

## Memory & Retrieval

_Escalate-only-on-need is already the SKILL.md Part A principle; these are the
agent-memory deltas._

- **Reach for GraphRAG only when vector retrieval demonstrably fails on
  multi-hop questions** — it prototypes in minutes but productionizing it is a
  major undertaking. (Albada Ch. 6)
- **Don't replace retrieval with long context: for fact-seeking queries and
  freshness-critical data, selective retrieval still outperforms dumping the
  corpus into a million-token window.** (Albada Ch. 6)

## UX

- **For agents with interactive users, expose autonomy as an explicit user
  control (Manual / Assist / Auto) with defined behavior per level. For
  unattended agents, define autonomy and approval policy in job configuration.**
  (Albada Ch. 3)
- **Classify each interaction explicitly as synchronous or asynchronous and
  design status communication for the async ones; never leave users watching a
  spinner on a long-running task.** (Albada Ch. 3)
