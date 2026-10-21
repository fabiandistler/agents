---
managed-by: fabiandistler/agents build_project_claude.py
---

## Decisions / Grilling

- Ask at most 2 questions at a time. Each question should be concrete, with labeled options and a recommended default.
- For any decision involving thresholds, numbers or rule variants, show a simple visual first (HTML heatmap or before/after table), then the question. Keep the visual focused on the decision, not every detail.
- Don't over-engineer. If a question isn't needed to unblock the ticket, propose deferring it.
