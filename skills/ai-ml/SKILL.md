---
name: ai-ml
category: ai-ml
activation: router
environments: coding
description: "Use when building, debugging, or shipping anything with a trained model: an app on top of an LLM (prompting, RAG/retrieval, agents and tool use, evals and LLM judges, guardrails, fine-tune vs. retrieve) or a classical ML project (framing, baselines, model choice, missing data, deployment, retraining). Routes to a sub-skill."
when_to_use: "Use even when no ML jargon is used: the chatbot makes things up or ignores instructions, should we fine-tune, how do I test prompt changes, the agent loops or calls the wrong tool, how do we know it still works in production, is this model good enough to ship, which model for this tabular or image data, accuracy dropped after launch, when should we retrain. Not for generic data wrangling or plotting."
---

# AI & ML

This is a **router**. The ai-ml category ships several deep sub-skills; this
entry keeps one broad trigger on the surface and hands off to the specific one.
Do not answer an AI or ML engineering question from this file alone.

## When to use

The trigger situations live in this file's frontmatter (`description`, `when_to_use`) — match the request there, then follow How to use below.

## How to use

1. Match the request to a row in the table below.
2. **Read that sub-skill's `SKILL.md` before acting.** Open the file at the
   path in the last column (relative to this router's directory) with your
   file-reading tool. The sub-skills are *not* registered skills of their own:
   invoking one by a namespaced name (for example `<router>:<member>`) fails
   with "unknown skill" in agents that register only top-level skills, and
   wastes a turn. Read the file instead; it carries the real
   workflow, references, and scripts — this router only points the way.
3. If two rows seem to apply, read both; if none fit, use your general knowledge
   and say the catalogue had no dedicated sub-skill.

The sub-skills are nested under this router's `members/` directory, so they load
only when routed to (progressive disclosure) rather than each competing for the
model's trigger surface.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| llm-application-engineering | Engineers LLM applications: fixing bad output (prompting, RAG, finetuning), evals and LLM judges, agents and tools, guardrails, and production monitoring. | `members/llm-application-engineering/SKILL.md` |
| ml-project-lifecycle | Run a classical ML project — training your own model on your own tabular data, not an LLM app: framing, baselines, model choice, missing data, deployment, retraining. | `members/ml-project-lifecycle/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.

Scope: this router covers design and architecture decisions for AI systems,
not SDK/API syntax or MCP server implementation — those go to general knowledge or a dedicated tool skill.
