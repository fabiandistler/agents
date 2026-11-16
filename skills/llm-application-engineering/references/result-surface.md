# Result surface

_How a model result is shown to the person who acts on it. Source: Apple HIG
"Machine Learning", consumer-app guidance re-cut for expert/B2B tools._

As of 2026-09-24, distilled from the HIG revision of 2026-06-08.

- **Show a confidence value only after its correlation with result quality is
  verified across several thresholds and re-checked per model version.
  Unverified → do not show it at all.** (Apple HIG, Confidence)
  - ❌ surfacing the model's score because the API returns one   ← likely-default
- **Set a floor below which no result is offered — stricter for proactive
  features (unbidden suggestions). Above the floor, bands drive presentation:
  low → ask for confirmation or show a range; high → show directly.** Pairs
  with the repeat-stability rule in
  [`ai-engineering-conventions.md`, Evaluation](ai-engineering-conventions.md#evaluation):
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
