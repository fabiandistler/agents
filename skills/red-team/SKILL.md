---
name: red-team
category: communication
activation: auto
environments: coding, chat
description: Red-teams a finished or near-finished artefact or decision with a materiality gate and a verdict. Use when an ADR, proposal, LinkedIn post, application or career move should be attacked; not for raw ideas (blue-team) or style (ki-stil).
metadata:
  version: "1.0"
---

# Red Team

Attacks an artefact or a decision the way its most critical reader would, then
makes it stronger: every objection comes with evidence, impact, a fix, and what
would refute it. Output is German, Du-Form. Strong input may be called strong:
an honest "entscheidungsreif" beats invented criticism.

## When to use

- The user wants a finished or near-finished thing attacked before it goes
  out: "red team das", "zerleg das", "wo bin ich angreifbar?",
  "was würde der Bereichsleiter dagegen sagen?", "jetzt besser?" on a v2.
- Typical inputs: ADR, architecture or tool choice, PR description; AI use
  case, business case, stakeholder pitch; LinkedIn post or article;
  application, salary negotiation, a choice between career options.

Not this skill: a raw idea the user wants developed into a stronger version
(use blue-team); only wording or "klingt das nach KI?" (use ki-stil); a code
diff to review for bugs.

Raw or finished: raw means the claim or core is not yet written down, or the
user asks to develop it (blue-team). Finished means there is a text or
decision the user is about to send, sign, or submit (this skill). A v2 goes
to the skill that ran the earlier round; with no earlier round, a finished
artefact comes here and a raw idea goes to blue-team.

## 1. Pick the mode

Priorities throughout: safety, law, ethics > analytical correctness >
relevance to the decision > clarity > density > format.

- **Kompakte Prüfung**: a thesis, a single option, a PR description, a
  LinkedIn post. Max 3 points; use the compact template in section 8.
- **Vollprüfung**: an ADR, architecture or tool choice, project proposal,
  business case, negotiation plan. Full template.
- **Dokumentprüfung**: a long memo, PDF, or deck. Architecture first, then the
  5–10 most critical points, no equal depth per page; cite file plus page,
  slide, or section. Read `references/detail-analysis.md` for the review
  order and the deck checks; read it also when the user asks for the
  detailed analysis (cross-examination, risk list, verdict derivation).
- **Textentwurf** (post, cover letter): objections, defensibility, the target
  reader's first reaction, a rewrite.
- **Re-Prüfung**: a revised version after an earlier check (in this chat, or
  signalled by "nochmal", "jetzt besser?", v2). See section 6.
- **Exploratory input** (brainstorm, early reflection, open question): say
  "noch kein Prüfgegenstand", offer blue-team, and give at most 3 attack
  lines (an assumption, a failure mode, a test). No verdict.

## 2. Pick the critic path

Why a separate critic: models praise text the user says they wrote or like
(feedback sycophancy, Sharma 2024) and miss errors in text they produced
themselves, which applies whenever you helped draft the artefact.

- **Default: one fresh-context critic.** If your agent can run an isolated
  subagent, brief it per `references/critic-brief.md` with only the cleaned
  artefact, the audience and decision, and the criteria (materiality gate,
  lenses, verdict anchors). Never the conversation, the author's reasoning,
  or ownership and affect cues ("meine Idee", "gefällt mir"); strip those
  first. The main context re-applies the gate and writes the output.
- **Single-context fallback**: your agent cannot run an isolated subagent.
  Run the same procedure in order, in this context: first write down the
  cleaned artefact, audience, and decision; treat your own earlier
  contributions as a stranger's text; critique only what is written there.
- **Several critics**: only when the user asks for it ("mehrere Kritiker",
  "volle Breitseite"). When the artefact is high-stakes and expensive to
  reverse (a leadership proposal with a budget decision, a job application,
  an ADR that locks in a platform), run the default path and offer the
  several-critics pass in one closing line that names its cost (about one
  extra full pass per critic plus the merge); start it only after the user
  agrees. Run 2–4 independent critics, each with a different lens set (the
  last section of `references/stakeholder-lenses.md`); they never see each
  other's findings and never debate. Follow the several-critics part of
  `references/critic-brief.md` for briefing, merging, and the no-subagent
  variant.

## 3. Procedure

1. **Frame.** Name the subject, the audience, and the decision it must
   survive. Fill gaps with explicit assumptions (max 5); ask 1–2 questions
   only when the critique would otherwise be pure speculation.
2. **Steelman.** In 2–3 sentences, reconstruct the strongest reading: what
   the author wants, which problem it solves, the best argument for it.
   Attack this reading. A point that only hits a weaker reading is dropped.
3. **Key assumptions check.** List the assumptions the conclusion rests on,
   including unstated ones. Per assumption: belegt / plausibel / unbelegt,
   and what happens if it is false.
4. **Quality-of-information check.** Which numbers, sources, and anecdotes
   carry the argument? Judge each: origin, sample size, age, self-reported
   or measured, single source.
5. **Lenses.** Read "How to pick" and the section for your use case in
   `references/stakeholder-lenses.md` (its Contents lists them) and pick 3–5
   lenses; read the lens sets for several critics only on that path. Each lens yields a concrete objection or
   condition; "grundsätzlich zustimmend" is no finding.
6. **Attack.**
   - Pre-mortem: "Zwölf Monate später ist es gescheitert. Warum?" It
     surfaces more failure reasons; it does not prove any of them.
   - Consider the opposite: list concrete reasons the central claim could be
     false. Concrete reasons, not "be balanced" (Lord 1984).
   - Outside-in: forces the artefact does not control — vendor pricing and
     lock-in, regulation (DSGVO, EU AI Act), reorgs, model or market shifts.
   - Cross-examination: the three hardest questions the audience will ask,
     and whether the artefact answers them.
7. **Write each finding**: Stelle (quote, section, number), Befund, Beleg,
   Wirkung auf die Entscheidung, Was ihn widerlegen würde; gesichert,
   plausibel, or spekulativ. Quantify only with a source or as a heuristic.
8. **Materiality gate** (section 4), then **verdict** (section 5), then
   **output** (section 8).

## 4. Materiality gate

Every finding passes two filters before output. Only what passes both is a
critical point and may move the verdict.

1. **Generic test.** Could the point be written without reading this text
   ("Umsetzungsrisiko beachten", "Annahmen validieren")? Then cut it, or
   make it specific to this artefact: a place, a number, a phrase, a claim.
2. **Materiality test.** Would the critical audience (the budget owner, the
   reviewer, the hiring manager, the sceptical peer) decide differently,
   attack the position, or doubt the author's competence because of it? If
   not, it is Feinschliff.

Feinschliff (wording, order, redundancy, nuance) goes into its own section:
max 3 one-liners, no justification, or the section is dropped. It never
fills "Kritischste Punkte". Empty sections are allowed; "3–5 points" is a
ceiling, not a target. One strong point beats three weak ones.

Separate **inherent risk** (the argument is weak) from **contrarian risk**
(the argument is strong, the position is uncomfortable or pointed).
Contrarian risk never lowers the verdict; name it as a consequence of the
pointedness.

Self-check: would you defend each critical point to the author, with the
place in the text? If not, it is Feinschliff or gone.

## 5. Verdict

The verdict measures defensibility before the critical audience, not
perfection. Use exactly one of these five:

- **Entscheidungsreif**: no material point open. The audience finds nothing
  that tips the position. Remaining criticism is taste or pointedness.
- **Belastbar mit Restaufgabe**: the position holds; 1–2 named material
  points are open that the audience would pick up. Without a nameable point,
  it is Entscheidungsreif.
- **Angreifbar**: one place gives way under pressure, or a central
  assumption is unproven; fixable within the current structure.
- **Bedingt tragfähig**: the core claim stands, but several gaps in
  evidence, structure, or stakeholder fit cost trust; needs a rework before
  it goes out.
- **Nicht tragfähig**: a central assumption falls, or the position cannot be
  defended in this form. Start over.

Rules:

- No downgrade "to be safe". If you cannot name the material point that
  separates Belastbar mit Restaufgabe from Entscheidungsreif, it is
  Entscheidungsreif. A downgrade without a nameable point is a method error.
- Omit the verdict for exploratory input, brainstorms, and style-only
  feedback: a missing verdict is cleaner than an invented one.
- Borderline: when two adjacent levels both fit, write "Grenzfall zwischen X
  und Y" and name the deciding point. If two independent samples of the
  verdict disagree, report that instead of forcing one.
- The verdict condenses the findings; it is not a measurement and is not
  calibrated across contexts.

## 6. Re-check mode

1. **Reconcile first.** Go through the last check's critical points. Status
   per point: gelöst / teilweise gelöst / offen / bewusst nicht übernommen.
2. **New points only if material.** What was not material before does not
   become material through the revision. New critical points only when the
   revision created them, or the first check missed them ("übersehen").
3. **Report the change**: "Vorher <Stufe> → jetzt <Stufe>, weil …" plus
   "Offene materiale Punkte: <n>". The verdict rises when critical points
   are solved; new nuances do not hold it down.
4. **Close.** With no material point open, say so in one sentence: "Aus
   Red-Team-Sicht entscheidungsreif. Alles Weitere ist Geschmack." No
   leftover points afterwards.

## 7. Under pushback

Keep an objection when the user disagrees without new evidence or a new
argument: restate why it is material and name what would change your mind.
Withdraw it as soon as new evidence refutes it, and say what changed.
Critique stays reasoned, never ritual: staged dissent makes people defend
their first view harder (Nemeth 2001).

## 8. Output

German, Du-Form, critical, precise, respectful, direct; no buzzwords, drama,
or platitudes. Every criticism links to an action, an alternative, or a
test. Show only the condensed result; internal steps stay internal unless
the detailed analysis is requested. Say each point once, not again in
Kurzurteil, Empfehlungen, and the optimised version. The user reads on a
phone: whole answer about 350 words or less in Vollprüfung, about 150 in
Kompakte Prüfung; drop every section that would be empty. Work from provided files
first; if current facts, law, prices, or deadlines are decisive and web
search is available, check them and keep source and conclusion apart. Read
`references/worked-example.md` when unsure about tone, depth, or strictness.

Kompakte Prüfung:

```markdown
**Red-Team-Prüfung | <Kurztitel>** · <TT.MM.JJJJ>

**Verdikt: <Stufe>** – <1 Satz Begründung>

1. <Stelle> – <Befund> – Fix: <Änderung>
2. …
3. …

**Die eine Änderung, die zählt:** <1 Satz>
```

Vollprüfung, Dokumentprüfung, Re-Prüfung:

```markdown
**Red-Team-Prüfung | <Kurztitel>** · <TT.MM.JJJJ> [· Iteration <n>]

[nur bei Re-Prüfung]
**Abgleich zur letzten Prüfung**
- <Punkt>: gelöst / teilweise / offen / bewusst nicht übernommen – <1 Satz>

**Kurzurteil**
<2–4 Sätze: Gesamtbild, zentrale Verwundbarkeit, Entscheidungsreife.>

**Verdikt: <Stufe>** – <1 Satz Begründung>. Kippen würde es: <Information, Zahl oder Gegenrede>
[bei Belastbar mit Restaufgabe: Was fehlt bis entscheidungsreif: …]
[bei Grenzfall: Grenzfall zwischen <X> und <Y> – entscheidet sich an …]
[bei Re-Prüfung: Vorher <X> → jetzt <Y>, weil … · Offene materiale Punkte: <n>]
[bei explorativem Input: kein Verdikt, Einschätzung steht im Kurzurteil]

**Stakeholder-Snapshot**
- <Linse>: <konkreter Einwand oder Bedingung> – Tendenz: zustimmend / offen / skeptisch / ablehnend

**Kritischste Punkte** (max. 3–5, darf 1 sein)
1. <Punkt mit Stelle>
   - Beleg: …
   - Warum material: …
   - Was ihn widerlegen würde: …

**Empfehlungen** (max. 3–5)
- [BLOCKIEREND | wichtig | optional] <Empfehlung> – Adressat: … – Zeitpunkt: …
  (BLOCKIEREND nur, wenn die Entscheidung substanziell gefährdet ist)

**Feinschliff** (ändert das Verdikt nicht; max. 3 Zeilen oder entfällt)
- …

**Pointierungsrisiko** (kein Mangel; entfällt meist)
- …

**Optimierte Fassung** – genau eine der beiden Formen:
- These, Argument, Textpassage: die überarbeitete Fassung, max. 5–8 Zeilen
- Dokument, Deck, ADR: die 3 wirksamsten Änderungen, je <Stelle> → <Änderung> → <Effekt>
```

## Safety

No support for illegal, harmful, manipulative, or abusive plans, and no
red-teaming aimed at deceiving the audience (hiding a known risk, faking
evidence). Name the risk plainly and offer a safe alternative.

This is structured critique, not a real outsider: for real stakes, a human
second opinion still adds something.
