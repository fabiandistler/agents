---
name: apology-review
description: Analyze the structure of an apology (spoken or written) against Lewicki's peer-reviewed six-component model, reporting which components are present or missing ranked by importance, and optionally drafting a structurally improved version. Use whenever a user shares an apology (their own draft, one they received, or one they're planning to give) and asks whether it is complete, effective, or how to improve it — but only on explicit request, since this touches interpersonal and emotional territory.
compatibility: Works on any apology text in any language the reviewer can read; no tools or dependencies required. Structural analysis only — it cannot assess sincerity.
metadata:
  version: "1.0"
---

# Apology Review

This skill checks an apology against a specific, peer-reviewed structural
model — not personal opinion about what "sounds sincere." Given an apology
text, it identifies which of six known components are present, which are
missing, ranks the gaps by how much they matter, and — if asked — offers a
structurally more complete version. It does not judge whether the apology is
felt, and it does not replace judgment about the relationship or situation
the apology sits in.

## Scope and disclaimer

This is educational, structural feedback grounded in one research model — not
psychological, medical, or therapeutic advice. Apologies are personal and
context-dependent; the six components below are a validated pattern, not a
universal script, and individual and cultural variation is real. Apply this
skill only when a user explicitly asks for apology feedback; do not volunteer
an unsolicited critique of someone's apology. If the situation involves
ongoing harm, abuse, or a relationship in crisis, say plainly that this is
outside what a structural checklist can address and that professional
support (e.g., a therapist or counselor) is more appropriate than a text
review.

## The six components (Lewicki, Ohio State)

Roy Lewicki (Ohio State University, Fisher College of Business) identified
six components of an effective apology and found them not equally important:
some carry far more weight than others. Rank order in the table below is
from most to least critical.

| # | Component | Example phrasing | Essence |
|---|-----------|-------------------|---------|
| 1 | **Acknowledgment of responsibility** *(most critical)* | "It was **my** fault" | Full self-attribution of blame; no externalizing, no "but" |
| 2 | **Offer of repair** | "I want to make this right, and I suggest…" | Concrete, proactive steps to fix the harm |
| 3 | **Expression of regret** | "I'm sorry" | Genuine emotional concern for the other person |
| 4 | **Explanation** | (transparent account of what caused it) | Context, given without shifting blame away from oneself |
| 5 | **Declaration of repentance** | "I don't understand how I could do that" | Self-critical reflection and a commitment to change behavior |
| 6 | **Request for forgiveness** | "Can you forgive me?" | An explicit ask that respects the other person's autonomy to decide |

Components 1 and 2 do the most work; missing them is the most serious gap.
Components 5 and 6 matter but are the least load-bearing — an apology
missing only these is still largely functional if 1–4 are solid.

## Workflow

1. **Read the apology text once, in full**, before scoring anything.
2. **Check each of the six components against the text.** For each, mark:
   present / partially present / missing, with the specific phrase (if any)
   that supports the call. Don't infer a component from tone alone — require
   something in the text that actually does that job.
3. **Watch for a common false positive**: an "explanation" that quietly
   externalizes blame (e.g., "I did it because you…") does not count as
   component 4 — it undercuts component 1 instead. Flag this explicitly if
   present, since it is worse than an apology that simply omits the
   explanation.
4. **Rank the findings** by the importance order in the table above, not by
   the order components appear in the text. Lead with responsibility and
   repair; treat regret/explanation as secondary; treat repentance/forgiveness
   as minor.
5. **Ask about repetition context** (see below): is this the first apology
   for this issue, or a repeat? If the user mentions or implies this is a
   repeat, factor in the credibility-erosion rule before recommending "just
   apologize better."
6. **Report findings** using the output format below.
7. **Only if asked**, draft an improved version that fills the highest-ranked
   gaps first, using language close to the original voice rather than a
   generic template. Do not offer this unprompted.

## The credibility-erosion rule

A structurally perfect apology is not always the right recommendation.
Repeated apologies for the *same* underlying issue lose effectiveness over
time: past roughly **four to five** apologies for one recurring problem, the
apology stops working — the recipient no longer believes real behavioral
change will follow, and the relationship absorbs damage regardless of how
well-formed the words are. The mechanism: the apology reads as an empty
gesture, signals a lack of commitment to change, and the recipient feels
disrespected ("words without action").

If the text or context indicates this is a repeat apology for a known,
recurring issue, say so directly and note that the constructive next step at
that point is a root-cause analysis and a systematic change in behavior, not
a better-worded apology. Reviewing apology structure is still useful
diagnostically, but frame the wording feedback as necessary, not sufficient.

## Output format

Report in this order — most important finding first:

```
Present:  <components found, with supporting phrase>
Missing:  <components absent, ranked most → least critical>
Flags:    <e.g., explanation that externalizes blame; signs of repeat apology>
Erosion check: <first-time / repeat — and the implication if repeat>
Improved version: <only if explicitly requested>
```

Keep the report proportional to the text: a two-line message needs a few
lines back, not an exhaustive breakdown.

## Limitations

- **Structure is checkable; sincerity is not.** This review can confirm
  whether the six components are present in the text. It cannot confirm
  whether the person means them. Lewicki's model itself warns that
  mechanical application of the components without genuine emotional
  sincerity is recognized as manipulative and makes the situation worse —
  say this explicitly if a user seems to be assembling an apology as a
  checklist exercise rather than an honest one.
- This is not a substitute for professional relationship, therapeutic, or
  conflict-mediation advice.
- The model describes a general pattern from published research; it does not
  account for every cultural or relational context an apology might occur in.
