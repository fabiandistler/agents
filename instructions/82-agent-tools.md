---
title: Agent tools calling external APIs
targets: all
---

## Agent tools calling external APIs

- Decide explicitly which tool exceptions go back to the model. The LangGraph default only catches argument-validation errors and re-raises everything else, which kills the run (e.g. a 200 with invalid JSON). With `langgraph.prebuilt.ToolNode` / `create_react_agent`, set `handle_tool_errors`; `langchain.agents.create_agent` has no such parameter, so add `ToolErrorMiddleware(on_error=...)`.
- A tool's error text says whether a retry can help: timeout, connection error, 429, 5xx → "retryable"; other 4xx and auth → "not retryable" plus what the caller must change.
