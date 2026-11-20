# Result surface

How a model result is shown to the person who acts on it. Source: Apple HIG
"Machine Learning" and "Generative AI", consumer-app guidance re-cut for
expert/B2B tools. When you build or change a UI that shows model output,
check every rule below and list the unmet ones in the change description or
review notes. Confirmation before irreversible actions: the approval-gate rule
in [`security.md`, Access and authorization](security.md#access-and-authorization).

As of 2026-11-16: distilled from the HIG revision of 2026-06-08. Art. 50 of
Regulation (EU) 2024/1689 (AI Act) sets the transparency duties; check its
current application date.

- **Show a confidence value only after its correlation with result quality is
  verified across several thresholds and re-checked per model version.
  Unverified → do not show it at all.** (Apple HIG, Confidence)
- **Set a floor below which no result is offered — stricter for proactive
  features (unbidden suggestions). Above the floor, bands drive presentation:
  low → ask for confirmation or show a range; high → show directly.** (Apple
  HIG, Confidence)
- **Percentages and statistical jargon only where the domain is statistical
  (compensation ranges, intervals, forecasts). For ratings and categories,
  rank or use semantic bands ("high / low chance") and phrase confidence as
  the action it implies.** (Apple HIG, Confidence)
- **An attribution names the input facts the result rests on, in domain
  terms — one per option when several are shown; factual, never emotional
  ("because the role carries budget responsibility X", not "match 0.91",
  not "because you love …"). Neither so specific it reads as surveillance nor
  so general it says nothing.** (Apple HIG, Attribution)
- **Put edit, undo and retry next to the generated result, and make
  discarding it as cheap as accepting it. Where users can override a result,
  offer guided alternatives before free-form editing, confirm at the result
  that the correction took effect, persist it and log it as a labelled
  example.** Report correction rate per output field as a quality metric with
  a ceiling. If correcting costs more than doing the task by hand, the feature
  has failed — corrections never compensate for low base quality. (Apple HIG,
  Generative AI: Outputs; Corrections)
- **Decide the non-AI path to the same goal before release: model down,
  quota exhausted, user opts out. If there is none, record that as a
  decision.** (Apple HIG, Generative AI: Best practices)
- **Mark generated content as AI-generated where it is read, exports
  included, and say it may contain errors. Settle the feature's EU AI Act
  Art. 50 transparency duties before release.** (Apple HIG,
  Generative AI: Transparency, Inputs; Regulation (EU) 2024/1689)
- **State known limits up front and offer example inputs for every open
  prompt field; explain why weak results occur.** (Apple HIG, Generative AI:
  Transparency, Inputs)
- **Place an optional feedback control (thumbs up/down plus a path for
  detail) at a fixed spot on the output, never as an interruption, and route
  it to someone who reads it.** (Apple HIG, Generative AI: Continuous
  improvement)
- **When output is blocked or out of scope, say so and show how to ask
  better, ideally with an example request — never return an empty result
  silently.** (Apple HIG, Generative AI: Outputs)
