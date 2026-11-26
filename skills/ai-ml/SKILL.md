---
name: ai-ml
category: ai-ml
activation: router
environments: coding
description: "Routes work on trained-model systems to the right sub-skill: LLM apps (prompting, RAG/retrieval, agents and tool use, evals and LLM judges, guardrails, fine-tuning) or classical ML projects (framing, baselines, model choice, missing data, deployment, retraining)."
when_to_use: "Use even when no ML jargon is used: the chatbot makes things up or ignores instructions, should we fine-tune, how do I test prompt changes, the agent loops or calls the wrong tool, how do we know it still works in production, is this model good enough to ship, which model for this tabular or image data, accuracy dropped after launch, when should we retrain. Not for generic data wrangling or plotting, SDK/API syntax, or MCP server implementation."
---

# AI & ML

## How to use

1. Match the request against the frontmatter, then select its row below.
2. **Read that sub-skill's `SKILL.md` before acting.** Open the path in the
   last column relative to this router, even if your agent lists the member
   separately. Follow the member's workflow, references, and scripts.
3. If two rows apply, read both. If none fits, use general knowledge or a
   dedicated tool skill, and say the catalogue had no dedicated sub-skill.
   SDK/API syntax, MCP server implementation, and generic data wrangling or
   plotting fall outside this router's AI systems design and architecture scope.

<!-- BEGIN generated:members -->
| Sub-skill | When to use | Read before acting |
|---|---|---|
| llm-application-engineering | Engineers LLM applications: fixing bad output (prompting, RAG, finetuning), evals and LLM judges, agents and tools, guardrails, and production monitoring. | `members/llm-application-engineering/SKILL.md` |
| ml-project-lifecycle | Guides a classical ML project — framing, baselines, model choice, missing data, deployment, retraining. | `members/ml-project-lifecycle/SKILL.md` |
<!-- END generated:members -->

The table above is generated from `skills.json` by
`scripts/build_routers.py`; edit the manifest, not this region.
