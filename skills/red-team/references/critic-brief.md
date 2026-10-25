# Critic brief

How to hand the artefact to an isolated critic, for the default path and the
several-critics path. The critic sees only what this brief contains.

## Clean the artefact first

Remove from what you pass on:

- Ownership cues: "mein Entwurf", "ich habe geschrieben", "unsere Idee",
  author names in the request.
- Affect and reassurance requests: "gefällt mir", "bin stolz drauf", "ist doch
  gut, oder?", "sei nicht zu streng".
- The conversation: earlier drafts, your own suggestions, the author's
  explanations of what they meant.
- Reasoning outside the artefact. Reasoning inside it stays: an ADR's
  context section, a proposal's business case, a post's argument are part of
  what is judged.

Keep: the artefact verbatim, the audience, the decision it must survive, and
hard facts the user stated that the audience will also know (budget limit,
deadline, role). State such facts neutrally.

## Brief template

Fill the angle brackets; pass nothing else.

```text
You are a red-team critic. Judge the artefact below as its most critical
reader would. You do not know who wrote it.

Audience: <who reads or decides>
Decision it must survive: <what the audience decides on it>
Known constraints: <neutral facts, or "none">
Lenses: <3–5 lenses with their key questions, or one lens set>

Procedure:
1. Steelman: 2–3 sentences on the strongest reading. Attack only that.
2. Key assumptions: list them (incl. unstated); belegt / plausibel / unbelegt.
3. Quality of information: judge the numbers and sources the argument rests on.
4. Per lens: a concrete objection or condition.
5. Pre-mortem, consider-the-opposite with concrete reasons, outside-in forces,
   the three hardest audience questions.
6. Materiality gate: drop any point that could be written without reading
   this text, unless you make it specific. Mark as Feinschliff any point the
   audience would not decide differently on. Report gaps that affect the
   decision; a sound artefact may yield zero critical points.

Write each finding in German:
- Stelle: <quote, section, or number>
- Befund: …
- Beleg: …
- Wirkung auf die Entscheidung: …
- Was ihn widerlegen würde: …
- Linse: …
- Einstufung: kritisch / Feinschliff · gesichert / plausibel / spekulativ

End with:
- Verdikt-Vorschlag: one of Entscheidungsreif / Belastbar mit Restaufgabe /
  Angreifbar / Bedingt tragfähig / Nicht tragfähig, with one sentence why.
  Write "Grenzfall zwischen X und Y" if two adjacent levels both fit.

Verdict anchors: <paste the five anchors from the skill's section 5>

Artefact:
<artefact verbatim>
```

## Several critics

- Same brief for every critic; only the lenses line differs. Give each
  critic one of the lens sets A–D from the lens catalogue, so critics
  differ by perspective, not only by label.
- Start them independently. No critic sees another's findings, and there is
  no debate round: debate adds little beyond independent votes (Choi 2025),
  and interacting critics converge on the same points.
- Merge into a deduplicated union: same place and same mechanism = one
  finding. Note how many critics raised it; convergence is a signal, not
  proof, and a point only one critic found can still be the decisive one.
- Without isolated subagents, walk the lens sets one by one in the main
  context, writing each pass's findings before starting the next, and say in
  the output that the passes were not independent.

## What the main context does with the result

1. Re-apply the materiality gate. Critics told to find gaps usually find
   some; drop what fails either filter.
2. Several critics: merge first, as above.
3. Decide the verdict yourself from the surviving points; the critic's
   proposal is input, not the answer.
4. Write the output in the skill's template.
