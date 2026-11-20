# Security conventions

Rules for guardrails, context authorization, database scope and agent security.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Guardrails & security](#guardrails--security)
- [Security](#security)

## Guardrails & security

_Extends SKILL.md Part B step 2. Security rules are kept even where they read as
obvious — the cost of guessing wrong is high._

- **Guardrail inputs AND outputs** — harmless inputs can still produce harmful
  outputs. (Huyen Ch. 5, 10)
- **Track the false-refusal rate alongside the catch rate.** An over-blocking
  system is also a failure. (Huyen Ch. 10)
- **Mask PII/sensitive data before any third-party API call; restore it via a
  reverse mapping after generation.** (Huyen Ch. 10)
- **Execute generated code only in an isolated sandbox/VM.** (Huyen Ch. 5)
- **Set approval gates by consequence and reversibility. Require explicit human
  approval for high-impact or hard-to-reverse mutations**, such as destructive
  SQL, external messages, or transactions. (Huyen Ch. 5, 10)
- **Whatever enters the context, the requesting user can extract — authorize
  before context construction, never with an instruction.** Filter retrieved
  documents, tool results and memory by the end user's permissions before they
  reach the prompt; keep credentials and other users' data out of the system
  prompt and write it as if it will be published. "Do not reveal X" is not an
  access control: models disclose context they were told to withhold. The
  DB-scope rule below is the database case of this rule. (Huyen Ch. 5; OWASP LLM07,
  https://genai.owasp.org/llmrisk/llm072025-system-prompt-leakage/)
  - ❌ every client's salary benchmarks in context plus "only discuss the user's own client"   ← likely-default
- **Enforce an agent's database scope with database grants, never with the
  prompt or a query filter: connect it as a dedicated user with SELECT on
  approved views only — never through the developer's or an admin connection.
  Treat free-text metadata (table/column comments, extended properties,
  description fields) as untrusted input and keep it out of the agent's
  context unless a human curated it.** A regex "read-only mode" is a blocklist
  the agent can be talked around; a GRANT is not. Tool-scoped DB privileges:
  `agents-and-tools.md`, Tool Design. (Rehberger; CVE-2026-65669,
  https://nvd.nist.gov/vuln/detail/CVE-2026-65669)
  - ✅ `agent_ro` user, `GRANT SELECT ON v_*`, schema text from a curated fixture
  - ❌ agent runs on the analyst's connection, read-only via a SQL keyword filter   ← likely-default
- **Streaming emits tokens before output guardrails can run** — make that
  trade-off an explicit decision, not an inherited default. (Huyen Ch. 10)
- **Audit third-party default prompt templates for missing safety instructions
  before use** — permissive defaults have shown 100% prompt-injection success in
  studies. (Huyen Ch. 5)

## Security

_Kept even where obvious — the cost of an agent guessing wrong is high. Input/
output guardrails and PII masking before third-party calls live in the Huyen
sheet; these are the agent/MCP-specific additions._

- **Treat all retrieved external content (web pages, documents, tool outputs) as
  untrusted input — indirect prompt injection arrives through data, not the
  user.** Benchmark defenses with PINT/BIPIA. (Albada Ch. 12)
- **Never log user messages, prompts, or PII in plaintext observability data;**
  scrub/redact at span export, and isolate monitoring backends with RBAC.
  (Albada Ch. 10, 12)
- **For remote (HTTP) MCP servers implement the spec's OAuth 2.1 authorization
  (PKCE, protected-resource metadata); stdio servers read credentials from the
  environment. Add RBAC, audit logs, and network policy on top — authorization
  alone does not scope tool permissions.** (Albada Ch. 4)
- **Sandbox agent execution and isolate third-party tool dependencies**
  (containers/venvs); rate-limit all agent-facing endpoints; use parameterized
  statements for any DB access. (Albada Ch. 4, 12)
- **Scope agent memory strictly: personal-agent memory is isolated by default,
  an agent never assumes cross-scope access to personal or shared data, and
  memory must be inspectable and deletable by the user.** (Albada Ch. 13)
- **Red-team before AND after every significant model/prompt change** — it's a
  recurring activity, not a launch checkbox (DeepTeam, Garak, PyRIT). (Albada Ch. 12)
