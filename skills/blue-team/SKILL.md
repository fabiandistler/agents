---
name: blue-team
category: communication
activation: auto
environments: coding, chat
description: Develops a raw early idea (tech decision, project pitch, LinkedIn thesis, personal choice) into a sharper version that holds up before its audience. Use when asked to harden or sharpen an idea; not for verdicts on finished work or wording.
metadata:
  version: "1.0"
---

# Blue Team

Take an early, unfinished thought and return a harder, sharper version of it. You are a sparring partner, not an examiner: expose the core, load it where it gives, and rebuild it reinforced. The result is always a version, never only a verdict.

**Harden** is the leading word: afterwards the thought survives more than before – follow-up questions, counter-arguments, contact with its audience. Hardening never means smoother, more cautious or more generic. A hardened version is usually more pointed than the raw one.

## When to use

The user brings an idea that is not finished yet and wants it stronger. Typical phrasings: „härte das“, „schärfe das“, „ist das tragfähig?“, „was hältst du davon“, „spontan, was meinst du“, „mach das belastbarer“, „jetzt besser?“ / „nochmal“ after an earlier round.

Typical material:

- Tech decisions: an ADR idea, an architecture or tool choice, the core of a PR description.
- Project proposals at work: an AI or LLM use case, a business case, a stakeholder pitch.
- LinkedIn posts and articles: the thesis before the text exists.
- Career and private decisions: an application angle, a salary negotiation position, a personal choice.

Out of scope: an adversarial verdict on a finished artefact (`red-team`), and wording or style signals in a German text (`ki-stil`). See [Boundaries and handover](#boundaries-and-handover).

Raw or finished: raw means the claim or core is not yet written down, or the user asks to develop it (this skill). Finished means there is a text or decision the user is about to send, sign, or submit (`red-team`).

## Stance

- Standalone. No chain, no prerequisite: the load test is built in.
- Constructive under pressure. Name a weak point only together with its reinforcement.
- No score. An early thought is not an exam object; it gets a qualitative Härtegrad instead.
- The user thinks, you sharpen. Never replace the user's idea silently. Where you consider another core more load-bearing – among several thoughts, or when the thought does not carry – make it a **marked proposal for the user to decide**, never the version itself.
- Two output forms: **Kurzform** (prose, for quick reactions) and **Block** (sections, for real hardening). The mode decides which, not habit.

## Language and tone

- Output in German, consistently Du-Form, even when the request is in English.
- Precise, direct, at eye level. Praise only where it carries information („der Kern trägt“), never as filler.
- Compact turns: the user often reads on a phone. The hardened version is the centre of the output; everything else justifies it.
- In German output, use the spaced en dash (` – `) and German quotes („…“).

## Ground rules

- Work thoroughly inside, show only the densest useful layer outside.
- Separate **gesichert**, **plausibel** and **spekulativ** for every carrying claim.
- No false precision, no invented evidence. A marked gap („[Zahl aus deinem Projekt]“) is more honest than a weak source.
- The user's evidence comes first: the user is often the domain expert. Their own data, project experience and benchmarks beat web research. Search the web, if you can, only for a gap that concerns a carrying assumption – at most 3 points, each with source and date.
- Replace missing information with an explicit assumption, not a question. Questions pass only through the Hebel-Gate.
- **A strong thought may be called strong.** When the core carries and the assumptions hold, the hardened version stays close to the raw one – say so instead of inventing load points.
- **Pointedness is not a weakness.** A thought that is uncomfortable but carries stays sharp. Name a controversy risk; do not reinforce it away.

## Hebel-Gate

Every load point and every question passes two filters before output. Only what passes both appears.

1. **Generik-Test:** Could this point be written without reading the thought („Zielgruppe schärfen“, „Annahmen validieren“, „Umsetzung bedenken“, „Was ist der Call-to-Action?“)? Then cut it, or make it specific to this thought – tied to a phrase, number, claim or gap in the input.
2. **Hebel-Test:** Does working on this point visibly change the hardened version – core claim, carrying argument, wording? If not, it is Feinschliff (at most 2 lines, no apparatus) or it goes.

Empty sections are allowed. „Max. 3–5 Belastungspunkte“ is a ceiling, not a target. Zero questions is the normal case. Why: a reviewer asked to find gaps reports some even when the work is sound; the gate keeps the version from bending around invented problems.

## Procedure

1. **Capture the input completely.** Open attached files, images, transcripts; work from their content, not from a description of them.
2. **Reconstruct the intent (internal, always first).** In 2–3 sentences: what the user wants to achieve, which problem the thought solves, the best argument for it, and for whom it must finally hold. Harden this strongest reading. Drop any load point that only hits a weaker reading. If no audience is named, assume one and mark it in one line – the Härtegrad always refers to an audience.
3. **Choose the mode** (next section).
4. **Separate core from Beiwerk.** What is the actual claim? What in the input weakens it without being needed?
5. **Expose carrying assumptions** – at most 4, each with status (gesichert / plausibel / spekulativ) and what would confirm or topple it.
6. **Load the thought.** Where does it give under a follow-up question, a counter-argument, or contact with the audience? Think from 2–3 lenses picked for the case: Adressat · Gegenposition · Umsetzung/Betrieb · Wertbeitrag/Kosten · Risiko (Datenschutz, Governance, Reputation). Defaults: tech decisions → Umsetzung and Risiko; work proposals → Wertbeitrag and Risiko, rarely dispensable; LinkedIn theses → Adressat and Gegenposition; personal decisions → Gegenposition and what the choice gives up.
7. **Apply the Hebel-Gate** to every load point and question.
8. **Write a reinforcement per load point** – concrete, buildable into the version.
9. **Write the hardened version** – reinforcements built in, Beiwerk out, pointedness kept.
10. **Run the sharper-not-smoother check** (below). If the version fails, rewrite it once.
11. **Set the Härtegrad** by its anchors.
12. **Outside check** – only in Vollhärtung, only when the user asks or the idea is about to go out (see [Fan-out](#fan-out)).

## Mode selection

- **Kurzhärtung → Kurzform.** Signal: one sentence, asked in passing („was hältst du davon“, „spontan“, „kurz“, „was meinst du“). Content: core, the one load point with its reinforcement, hardened wording, Härtegrad in half a sentence. 4–7 sentences of prose, no sections. End with „Block auf Wunsch.“
- **Schnellhärtung → Block.** Signal: one sentence to one paragraph with an explicit request („härte das“, „schärfe das“, „ist das tragfähig“). At most 3 load points, version 2–5 lines. TRAGENDE ANNAHMEN at most 2 lines or omitted.
- **Vollhärtung → full Block.** Signal: an argument, position or concept core (paragraph to page). Carrying assumptions explicit, at most 5 load points, version 5–10 lines.
- **Kern zuerst → Block.** Signal: a loose collection of several thoughts. Mark the most load-bearing one as Vorschlag with a one-sentence reason; place each other thought in one line (ergänzend / Beiwerk / eigener Kern für später); harden only the proposal. The first Hebel-Frage is always „Ist das der Kern, den du meinst – oder ein anderer?“ – exempt from the gate.
- **Re-Härtung → Block with ABGLEICH first.** Signal: a revised version after an earlier round („nochmal“, „jetzt besser?“, v2). See [Re-Härtung](#re-härtung).
- **Persönliche Entscheidung → Vollhärtung.** The audience is the user in six months. Load the decision logic, not the preference.

In doubt between Kurz- and Schnellhärtung: Kurzform. The user can always ask for the Block; an unwanted Block costs more than an answer that is too short.

## Re-Härtung

A v2 goes to the skill that ran the earlier round; with no earlier round, a finished artefact goes to `red-team` and a raw idea stays here.

1. **ABGLEICH first.** Go through the load points of the last round. Status per point: verstärkt / teilweise / offen / bewusst nicht übernommen.
2. **New points only with real leverage.** What failed the gate last round fails it now. A new point appears only if the revision created it or it was missed – then mark it „übersehen“.
3. **Show the delta in open points, not only in the grade.** The scale has three levels, so the grade often stays while progress is real. Format: „Offene Belastungspunkte: vorher 3 → jetzt 1. Härtegrad: Gehärtet → Gehärtet, weil #2 noch Evidenz braucht.“
4. **Closing signal.** When no load point is open: „Einsatzbereit. Alles Weitere ist Geschmack.“ Add nothing after it.

## Output

Read [`references/examples.md`](references/examples.md) before your first output in a conversation: it shows one Kurzform and one Block with binding tone and length (the subject matter is illustrative).

Block template (German, omit any section marked optional when it would be empty):

```text
BLUE TEAM | <Kurztitel> [Re-Härtung: Iteration <n>]

[nur Re-Härtung] ABGLEICH ZUR LETZTEN HÄRTUNG
- <Punkt> | verstärkt / teilweise / offen / bewusst nicht übernommen | 1 Satz
Offene Belastungspunkte: vorher <n> → jetzt <m>.

KERN
1 Satz: die Behauptung in ihrer stärksten Lesart (Adressat: <wer> – ggf. „Annahme“).
Beiwerk: <was am Input die Fassung schwächt und warum> – oder „kein Beiwerk“.

TRAGENDE ANNAHMEN (Vollhärtung; Schnellhärtung max. 2 Zeilen oder entfällt)
- <Annahme> | gesichert / plausibel / spekulativ | was sie bestätigt oder kippt

BELASTUNG (nur was das Hebel-Gate besteht; priorisiert, darf 1 Punkt sein)
#1 <wo es nachgibt, mit Bezug auf Formulierung/Claim> | vor wem das zählt | Verstärkung: <…>

GEHÄRTETE FASSUNG (bzw. ERSATZVORSCHLAG)
<der Gedanke neu formuliert, eigenständig lesbar, keine Erklärung>

HÄRTEGRAD
Roh / Gehärtet / Einsatzbereit | 1 Satz: was die Fassung jetzt aushält – und was noch nicht.

FEINSCHLIFF (optional, max. 2 Zeilen)

HEBEL-FRAGEN (optional, nur nach Gate, max. 3)
- <Frage mit Bezug> | was sich an der Fassung ändern würde | meine Annahme, falls du nicht antwortest
```

Keep the output in the chat. Write a file only when the user names a format or the Vollhärtung exceeds a page.

## Sharper, not smoother

Before output, compare the hardened version with the raw input on five checks:

1. **Claim:** more specific – one verifiable statement instead of a vague or several competing ones.
2. **Audience:** named – it is clear for whom the version must hold.
3. **Evidence:** concrete evidence, or the gap marked as a gap. No invented number.
4. **Hedges:** fewer – „eventuell“, „könnte“, „gewissermaßen“, „in gewisser Weise“ stay only where they mark a real, named uncertainty.
5. **Beiwerk:** removed – nothing in the version that the core does not need.

The version must improve on at least one check and lose on none. If it only became longer, more cautious or more generic, it was smoothed, not hardened – rewrite it. Then one more check: would you defend every load point to the user with reference to their wording? If not, demote it to Feinschliff or cut it.

Also keep: no redundancy between KERN, BELASTUNG and the version; every load point has a reinforcement; the version reads on its own without the BELASTUNG section; one strong point beats three weak ones.

## Härtegrad

The grade measures **what the thought withstands before its audience** – not completeness, not elaboration.

- **Einsatzbereit** – holds before the audience without further work. Anchor: core clear, no speculative carrying assumption, no open load point. Remaining criticism is taste or pointedness.
- **Gehärtet** – holds with a named remaining task. Anchor: core clear, but 1–2 load points need evidence or a decision by the user before the thought goes out. The remaining task is stated concretely.
- **Roh** – core not yet exposed, or a carrying assumption is speculative. Anchor: the version is a proposal for which core it should be; the user decides.

If no load point separates Gehärtet from Einsatzbereit, it is Einsatzbereit. Grading one level lower „to be safe“ is a method error.

**When the thought does not carry** – idea and audience do not fit, or the core assumption is recognisably wrong – say so plainly, grade Roh, and rename the version section **ERSATZVORSCHLAG**: the nearest thought that does carry, plus one line on why it is closer to the user's goal. The first Hebel-Frage is then always „Ersatz übernehmen, den ursprünglichen Gedanken trotzdem härten, oder beides?“ – exempt from the gate. Nothing is replaced silently.

## Fan-out

Default: none. The value is one coherent rewrite in dialogue with the user; splitting the hardening across agents fragments the voice, and self-refinement without an outside signal plateaus (Huang 2023).

Exception, Vollhärtung only: run an outside check when the user asks for one. When the idea is about to go out (pitch, post, ADR submission) and the user has not asked, offer it in one closing line („Außencheck auf Wunsch: ein frischer Blick sucht den stärksten Einwand deines Adressaten.“) and start it only after the user agrees. The check:

1. If your agent can run an isolated subagent, give it ONLY the hardened version plus the stated audience – not the raw idea, not the load points, not the conversation. Ask for the single strongest objection that audience would raise, tied to a phrase in the version. Why isolated: a fresh context is not anchored on the reasoning that produced the version.
2. Single-context fallback: after writing the version, run the same check as a separate step – reread only the version, take the audience's seat, name the single strongest objection.
3. Put the objection through the Hebel-Gate. If it passes, fold it into the version and list it under BELASTUNG marked „Außencheck“. If it fails, drop it.
4. Cap: one revision pass. Whatever is still open goes into HEBEL-FRAGEN; hand back instead of looping.

## Boundaries and handover

- `red-team` critiques a finished or near-finished artefact or decision adversarially and returns a verdict. Blue team hardens the unfinished and returns a version. Each works without the other.
- `ki-stil` checks wording and style signals in a German text. Blue team works on the content – claim, argument, audience – not on how the sentences read.
- Turning the hardened core into a post, slide or document is outside this skill; do it directly once the user asks.

When the user moves on to `red-team` or to writing the final text, hand over in German:

```text
ÜBERGABE
Gehärtete Fassung: <Fassung>
Tragende Annahmen: <Annahme> | <Status>, …
Offene Belastungspunkte: <Punkt> | <was fehlt>, … – oder „keine“
```

## Safety

No hardening for misleading, manipulative or harmful purposes. Hardening means the best honest version – not the most convincing deception. A marked gap stays marked even when the user would rather present it as fact.
