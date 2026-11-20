# Result surface

_How a model result is shown to the person who acts on it. Source: Apple HIG
"Machine Learning" and "Generative AI", consumer-app guidance re-cut for
expert/B2B tools. When you build or change a UI that shows model output,
check every rule below and list the unmet ones in the change description or
review notes.
Confirmation before irreversible actions: the approval-gate rule in
[`security.md`, Guardrails & security](security.md#guardrails--security)._

As of 2026-09-24 (Machine Learning rules) and 2026-11-16 (Generative AI
rules): the dates when each rule set was added here, both distilled from the
HIG revision of 2026-06-08. Art. 50 of Regulation (EU) 2024/1689 (AI Act) sets
the transparency duties; check its current application date.

- **Show a confidence value only after its correlation with result quality is
  verified across several thresholds and re-checked per model version.
  Unverified → do not show it at all.** (Apple HIG, Confidence)
  - ❌ surfacing the model's score because the API returns one   ← likely-default
- **Set a floor below which no result is offered — stricter for proactive
  features (unbidden suggestions). Above the floor, bands drive presentation:
  low → ask for confirmation or show a range; high → show directly.** Pairs
  with the repeat-stability rule in
  [`evaluation.md`, Evaluation](evaluation.md#evaluation):
  that one measures, this one decides what the user sees. (Apple HIG,
  Confidence)
  - ❌ one presentation for every confidence level   ← likely-default
- **Percentages and statistical jargon only where the domain is statistical
  (compensation ranges, intervals, forecasts). For ratings and categories,
  rank or use semantic bands ("high / low chance") and phrase confidence as
  the action it implies.** (Apple HIG, Confidence)
  - ❌ "97 % match" on a grade or level   ← likely-default
- **An attribution names the input facts the result rests on, in domain
  terms — one per option when several are shown; factual, never emotional
  ("because the role carries budget responsibility X", not "match 0.91",
  not "because you love …"). Neither so specific it reads as surveillance nor
  so general it says nothing.** (Apple HIG, Attribution)
  - ❌ a raw score as the only explanation   ← likely-default
- **Put edit, undo and retry next to the generated result, and make
  discarding it as cheap as accepting it.** The correction rule in
  [`evaluation.md`, Evaluation](evaluation.md#evaluation)
  logs the edit; this one makes it reachable. (Apple HIG, Generative AI:
  Outputs)
  - ❌ accept is one click, editing sits in a menu or on another page   ← likely-default
- **Confirm at the result that a user's correction took effect.** A silent
  re-render leaves people unsure whether their input counted. (Apple HIG,
  Generative AI: Outputs)
  - ❌ re-rendering after a correction without any signal   ← likely-default
- **Decide the non-AI path to the same goal before release: model down,
  quota exhausted, user opts out. If there is none, record that as a
  decision.** (Apple HIG, Generative AI: Best practices)
  - ❌ the task behind the feature is blocked whenever the model call fails   ← likely-default
- **Mark generated content as AI-generated where it is read, exports
  included, and say it may contain errors. Settle the feature's EU AI Act
  Art. 50 transparency duties before release.** (Apple HIG,
  Generative AI: Transparency, Inputs; Regulation (EU) 2024/1689)
  - ❌ generated text lands in a client deliverable without a marker   ← likely-default
- **State known limits up front and offer example inputs for every open
  prompt field; explain why weak results occur.** (Apple HIG, Generative AI:
  Transparency, Inputs)
  - ❌ a blank free-text box as the only entry point   ← likely-default
- **Place an optional feedback control (thumbs up/down plus a path for
  detail) at a fixed spot on the output, never as an interruption, and route
  it to someone who reads it.** Implicit signals:
  [`evaluation.md`, Production metrics and feedback](evaluation.md#production-metrics-and-feedback).
  (Apple HIG, Generative AI: Continuous improvement)
  - ❌ a feedback modal after each result, or ratings in a log nobody reads   ← likely-default
- **When output is blocked or out of scope, say so and show how to ask
  better, ideally with an example request — never return an empty result
  silently.** Complements the floor rule above. (Apple HIG, Generative AI:
  Outputs)
  - ❌ an empty result or a generic error when a guardrail or the floor suppresses output   ← likely-default
