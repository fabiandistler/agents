# Security conventions

Rules for guardrails, access and authorization, and execution and operations.

Citations: Huyen = Chip Huyen, *AI Engineering* (O'Reilly, 2025); Albada = Michael Albada, *Building Applications with AI Agents* (O'Reilly, 2025).

## Contents

- [Guardrails](#guardrails)
- [Access and authorization](#access-and-authorization)
- [Execution and operations](#execution-and-operations)

## Guardrails

- **Track the false-refusal rate alongside the catch rate.** An over-blocking
  system is also a failure. (Huyen Ch. 10)
- **Mask PII/sensitive data before any third-party API call; restore it via a
  reverse mapping after generation.** (Huyen Ch. 10)
- **Treat all retrieved external content (web pages, documents, tool outputs) as
  untrusted input — indirect prompt injection arrives through data, not the
  user.** Benchmark defenses with PINT/BIPIA. (Albada Ch. 12)
- **Streaming emits tokens before output guardrails can run** — make that
  trade-off an explicit decision, not an inherited default. (Huyen Ch. 10)
- **Audit third-party default prompt templates for missing safety instructions
  before use.** (Huyen Ch. 5)

## Access and authorization

- **Whatever enters the context, the requesting user can extract — authorize
  before context construction, never with an instruction.** Filter retrieved
  documents, tool results and memory by the end user's permissions before they
  reach the prompt; keep credentials and other users' data out of the system
  prompt and write it as if it will be published. "Do not reveal X" is not an
  access control: models disclose context they were told to withhold. The
  DB-scope rule below is the database case of this rule. (Huyen Ch. 5; OWASP LLM07,
  https://genai.owasp.org/llmrisk/llm072025-system-prompt-leakage/)
- **Enforce an agent's database scope with database grants, never with the
  prompt or a query filter: connect it as a dedicated user with SELECT on
  approved views only — never through the developer's or an admin connection.
  Treat free-text metadata (table/column comments, extended properties,
  description fields) as untrusted input and keep it out of the agent's
  context unless a human curated it.** A regex "read-only mode" is a blocklist
  the agent can be talked around; a GRANT is not. (Rehberger; CVE-2026-65669,
  https://nvd.nist.gov/vuln/detail/CVE-2026-65669)
  - ✅ `agent_ro` user, `GRANT SELECT ON v_*`, schema text from a curated fixture
  - ❌ `connect(ANALYST_DSN)` with a `^\s*SELECT` regex as the read-only guard
- **Set approval gates by consequence and reversibility. Require explicit human
  approval for high-impact or hard-to-reverse mutations**, such as destructive
  SQL, external messages, or transactions. (Huyen Ch. 5, 10)
- **Scope agent memory strictly: personal-agent memory is isolated by default,
  an agent never assumes cross-scope access to personal or shared data, and
  memory must be inspectable and deletable by the user.** (Albada Ch. 13)

## Execution and operations

- **Run generated code and agent execution only in an isolated sandbox
  (container or VM), isolate third-party tool dependencies (containers/venvs),
  and rate-limit all agent-facing endpoints.** (Huyen Ch. 5; Albada Ch. 4, 12)
- **Redact PII from prompts, user messages and tool payloads before any log or
  telemetry leaves the service (span export, log shipping, crash reports): full
  prompts stay only in in-service logs with restricted access and a retention
  limit. Isolate monitoring backends with RBAC.** (Albada Ch. 10, 12)
- **Red-team before AND after every significant model/prompt change** — it's a
  recurring activity, not a launch checkbox (DeepTeam, Garak, PyRIT). (Albada Ch. 12)
