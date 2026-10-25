---
name: ki-stil
category: communication
activation: auto
environments: coding, chat
description: Checks a German draft for wording that reads generic or AI-typical, with counted, located signals and rewrites. Use when a German post, PR text or letter should not sound like a template; style only, not content (red-team) or raw ideas (blue-team).
metadata:
  version: "1.0"
---

# KI-Stil

A style check for German texts in three stages: style hygiene, AI-typical
patterns, authenticity. The goal is a text that carries its author's voice, not
one that passes a detector. Signals are counted by a script and weighed by
genre and evidence tier; the verdict is about *how the text reads*, never about
*who wrote it*. Why: detectors and human judges cannot decide authorship
(OpenAI withdrew its own classifier in 2023; Weber-Wulff 2023, Fleckenstein
2024), and they flag non-native writers far more often (Liang 2023). Output is
German, Du-Form, even when the request is in English.

## When to use

- The user asks, in German or English: „Klingt das nach KI?“, „KI-Stil-Test“,
  „prüf den Text auf KI-Floskeln“, „klingt mein LinkedIn-Post generisch?“,
  „ist das zu glatt?“, „mach das weniger nach ChatGPT“, "does this German post
  read like AI?".
- A German draft is about to go out: LinkedIn post or article, PR description
  or ADR, project proposal or work mail, application or cover letter.
- Not for: whether the argument holds (suggest red-team), turning a raw idea
  into a stronger one (suggest blue-team), grammar-only proofreading, or
  proving that a person or a model wrote a text.

## Stance

- Markers are heuristics. Report clusters and density per 100 words; a single
  hit is a hygiene note at most.
- Write „liest sich generisch an Stelle X“ or „Stilsignal in Satz 4“. The words
  „KI-generiert“ and „von KI geschrieben“ never appear in the output.
- Figures such as triads and parallelism are fine; their unmotivated pile-up is
  the signal. Ask whether a figure sounds intended.
- Own substance is the only durable signal: content only the author can have.
  Surface markers change with every model generation.
- Plain language and non-native writing stay protected: short sentences,
  simple words, few connectors and a small vocabulary never raise the signal.
- Strong input may be called strong. A clean text gets 🟢 and no invented
  findings.
- Every criticism comes with a rewrite. Rewrites keep the author's voice and
  never invent facts: missing specifics become placeholders like
  `[deine Zahl]`.
- The output itself stays plain: at most one rhetorical figure per paragraph,
  no floskeln, Du-Form.

## Fan-out

None: the work is counting plus one judgement pass, and the counting goes to a
script that also handles long texts. Run the whole check in one context.

## Procedure

1. **Get the text.** If none is in the conversation or an attached file, ask
   once and stop: „Welchen Text soll ich prüfen? Füg ihn ein oder häng die Datei
   an, gern mit dem Kanal (LinkedIn, PR, Mail, Bewerbung).“ Check only text that
   is actually there.
2. **Set the genre.** Pick one from [Genre logic](#genre-logic). If unclear,
   ask once or state the assumption in the output: „Ich behandle das als
   LinkedIn-Post.“
3. **Count.** Save pasted text to a temporary file and run, from the skill
   directory, `python3 scripts/style_scan.py <file>` (or pipe it with `-`).
   It prints JSON: sentence-length dispersion, list hits with tier, density and
   sentence numbers, figure candidates, openings, dashes, clusters, substance
   hints. Use its numbers; never estimate sentence lengths yourself while the
   script can run. Exit 3 means the input had no words; exit 4 means
   `assets/marker_lists.json` is broken, so say so and fall back to step 3b.
   For very long texts add `--output FILE` and read the file.
   - **3b. No code execution?** Run the [manual reduced check](#manual-fallback)
     and mark every number „geschätzt“.
4. **Stage 1, style hygiene** (applies whether or not AI was involved):
   floskeln, textbook vocabulary, abstract nouns (ask „Welche denn konkret?“:
   add an example, or cut the sentence), nominal style, adjective chains of
   three or more (read these yourself), sentence-length dispersion.
5. **Stage 2, AI-typical patterns**, as far as the genre allows: clusters,
   triads, „nicht X, sondern Y“, „nicht nur … sondern auch“, significance
   inflation, English calques, repeated paragraph or sentence openings, dashes.
   For each cluster ask: rhythm, punchline, emphasis? Then keep it. Template
   feel? Then one figure per paragraph is enough.
6. **Stage 3, authenticity.** Own substance: does the text hold at least one
   of a name, number or date outside common knowledge; an own experience or
   observation; a position someone could reject; an example from the author's
   work or life? Friction: is there an edge anywhere, or is it smooth consensus
   throughout? Consensus test: would every other data scientist on LinkedIn
   sign it without hesitating? Then something of the author's own is missing.
   The script's `substance_hints` (digits, first person) are prompts for this
   question, not answers: an application is full of „ich“ and can still say
   nothing. Stage 3 reports only whether substance and an edge are *present*,
   never whether the position holds or how to sharpen it: for that, point to
   red-team (finished text) or blue-team (raw idea).
7. **Grade** with the [Ampel](#ampel) anchors and weigh by
   [evidence tier](#evidence-tiers).
8. **Write** the output with the [template](#output-template): the 2–4 most
   important findings, each with location and rewrite. Omit every template
   line that would read „keine“ or „unauffällig“; print the header, the
   findings with rewrites, and only the stage lines that hold a finding.

## Evidence tiers

- **Strong:** missing own substance; low sentence-length dispersion; dense
  nominal style and textbook vocabulary; English calques („macht Sinn“,
  „eintauchen in“, „in 2025“).
- **Medium:** triads, „nicht X, sondern Y“, connector floskeln, significance
  inflation, abstract nouns without a concrete referent.
- **Weak:** dashes. A spaced „ – “ is standard German punctuation and no signal;
  an unspaced „—“ is English typography and a weak hint only in clusters. No
  dashes at all says nothing.

A weak signal never moves the Ampel on its own. The German phrase lists in
`assets/marker_lists.json` are „eigene Beobachtung, keine Studie“ and age
within months; say so when a user leans on a single listed word. Read
`references/marker-katalog.md` when you interpret the script's numbers
(orientation values for CV and densities, what each JSON field means), when
the user asks why a marker counts, or when the phrase list needs re-curating.

## Genre logic

- **LinkedIn post or article:** stage 1 full, stage 2 full, stage 3 is the
  focus.
- **PR description, ADR, technical doc:** stage 1 floskeln and significance
  inflation only; stage 2 reduced, since technical terms repeat on purpose and
  bullets make short sentences normal (ignore dispersion); stage 3 asks for
  measurements, links, and the reason behind the decision.
- **Project proposal, business case, work mail:** all three stages full;
  stage 3 wants a number, a name, and a decision someone could reject.
- **Application or cover letter:** stage 1 full (floskeln dominate here),
  stage 2 full, stage 3 is the focus: a concrete project with a result.
- **Marketing claim, talk, literary text:** stage 2 largely suspended, the
  figures are intended; stages 1 and 3 full.
- **Scientific or legal text:** stage 1 without the abstract-noun test, stage 2
  only the cluster rule, nominal style is partly genre-typical.

## Short texts

Under 80 words the script sets `short_text: true`. Density and dispersion are
not meaningful there, so run the reduced check: floskeln, calques, figures as
single observations, own substance. The Ampel is 🟢 or 🟡 only; 🔴 needs density
evidence a short text cannot supply. Use the short template.

## Ampel

A heuristic, not a detector verdict. In a borderline case choose 🟡.

- 🟢 **unauffällig:** no cluster, at most isolated hits, no strong signal,
  own substance present. Anchor: a PR description with measurements and an
  open question.
- 🟡 **manuell prüfen:** one strong signal, or clusters in part of the text,
  or thin own substance in an otherwise clean text. Anchor: a cover letter
  with one real project buried under floskeln.
- 🔴 **überarbeiten:** clusters across most of the text AND at least one
  strong signal AND no own substance. Anchor: a LinkedIn post that any reader
  in the field could have written.

Worked examples for each anchor, with script numbers and full outputs, are in
`references/beispiele.md`; read it before your first check in a session or
when a grade is borderline.

## Output template

````text
KI-STIL-TEST · <erste fünf Wörter des Textes>
Genre: <Genre> – <ein Satz Begründung, oder „Annahme“>
Ampel: <🟢 unauffällig | 🟡 manuell prüfen | 🔴 überarbeiten> – <ein Satz Einordnung>
Grundlage: Zählskript, <n> Wörter, <n> Sätze | geschätzt, ohne Zählskript

Stufe 1 – Stil-Hygiene
- Floskeln: <n> (<x> pro 100 Wörter): „…“ (Satz n), … | keine
- Lehrbuchvokabular: … | keines
- Abstrakta ohne Konkretisierung: … | keine
- Nominalstil: <x> pro 100 Wörter, z. B. … | unauffällig
- Satzlängen: Mittel <m>, CV <cv>, <a> % unter 8, <b> % über 30 Wörter → variabel | gleichförmig | nicht belastbar
- Adjektivketten: … | keine

Stufe 2 – KI-Muster (<voll | reduziert | ausgesetzt>, <Grund>)
- Häufungen: Satz <a>–<b>: <Kategorien> | keine
- Figuren: <n> Trikola, <n> „nicht X, sondern Y“, <n> „nicht nur … sondern auch“ – <gewollt oder Schablone>
- Lehnmuster aus dem Englischen: … | keine
- Anfangsmuster: … | unauffällig
- Gedankenstriche: <n> „—“ ohne Leerzeichen (schwacher Hinweis) | unauffällig

Stufe 3 – Authentizität
- Eigensubstanz: ja | nein – <was konkret, oder was fehlt>
- Reibung: ja | nein – <die Position, die jemand ablehnen könnte>
- Konsens-Test: bestanden | nicht bestanden – <kurz>

Die wichtigsten Befunde
1. Befund: <was>
   Stelle: „<Zitat>“ (Satz n)
   Vorschlag: „<Rewrite>“

Rewrite-Vorschlag (nur bei 🟡 und 🔴)
<2–5 Sätze zu den markantesten Stellen, nicht der ganze Text; fehlende Fakten als [Platzhalter]>
````

Short template (under 80 words):

````text
KI-STIL-TEST (reduziert, <n> Wörter) · <erste fünf Wörter>
Genre: <Genre> – <Begründung>
Ampel: <🟢 | 🟡> – <ein Satz>
- Floskeln und Lehnmuster: … | keine
- Figuren: … (bei so wenig Text nur Einzelbeobachtung)
- Eigensubstanz: ja | nein – …
Vorschlag: „<ein Rewrite>“
````

## Manual fallback

When no code can run: read `assets/marker_lists.json` and scan the text for
its entries; count the words of up to ten sentences (first and last paragraph)
and note the shortest, the longest and whether they cluster in a narrow band;
count triads and „nicht X, sondern Y“ by eye. Use the short template if the
text is under about 80 words, else the full one, with
„Grundlage: geschätzt, ohne Zählskript“ and „ca.“ before every number.

## What this skill does not do

- It never claims a text is provably AI-written or provably human: heuristics
  cannot decide that.
- It is no substitute for statistical detectors, and no plagiarism or
  copyright check.
- It checks no facts and judges no argument: stage 3 notes whether own
  substance and an edge are present, not whether the position holds. For
  content, suggest red-team; for developing the idea, blue-team.
