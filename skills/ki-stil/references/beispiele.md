# Worked examples

Four checks, one per Ampel anchor plus a genre exception. The numbers are real
`style_scan.py` output for the input shown. Outputs are shortened where marked.

## Contents

- [1. LinkedIn post: red](#1-linkedin-post-red)
- [2. Cover letter: yellow](#2-cover-letter-yellow)
- [3. PR description: green](#3-pr-description-green)
- [4. Marketing claim: genre decides](#4-marketing-claim-genre-decides)

## 1. LinkedIn post: red

Input:

> In der heutigen Zeit ist es wichtiger denn je, dass Data Scientists nicht nur
> technisch versiert, sondern auch kommunikativ, neugierig und
> geschäftsorientiert sind.
>
> Darüber hinaus spielt die Fähigkeit, komplexe Sachverhalte verständlich zu
> erklären, eine maßgebliche Rolle. Modelle allein schaffen keinen Mehrwert,
> sondern erst ihre nahtlose Integration in bestehende Prozesse.
>
> Letztlich entscheidet die Kombination dieser Faktoren über den Erfolg
> datengetriebener Organisationen. Es geht nicht um Tools. Es geht um Haltung,
> Kommunikation und Verantwortung.
>
> Zusammenfassend lässt sich sagen: Wer diese Herausforderungen ganzheitlich
> angeht, wird auf dieser Reise einen echten Unterschied machen.

Script, in short: 89 words, 7 sentences, CV 0.48; floskeln 4.5, Lehnmuster 3.4,
Lehrbuchvokabular 2.2 per 100 words; nominal style 9.0; one cluster over
sentences 1–7 with 18 hits from 8 categories; no digits, no first person.

Output:

```text
KI-STIL-TEST · In der heutigen Zeit ist
Genre: LinkedIn-Post – Kanal genannt, persönliche Meinung zu einem Berufsbild.
Ampel: 🔴 überarbeiten – Häufung über den ganzen Text, starke Signale, keine Eigensubstanz.
Grundlage: Zählskript, 89 Wörter, 7 Sätze

Stufe 1 – Stil-Hygiene
- Floskeln: 4 (4,5 pro 100 Wörter): „In der heutigen Zeit“ (Satz 1), „Darüber hinaus“ (2), „Letztlich“ (4), „Zusammenfassend lässt sich sagen“ (7)
- Lehrbuchvokabular: „maßgebliche“ (2), „ganzheitlich“ (7)
- Abstrakta ohne Konkretisierung: „Mehrwert“ (3), „Faktoren“ (4), „Herausforderungen“ (7)
- Nominalstil: 9 pro 100 Wörter, z. B. „Fähigkeit“, „Integration“, „Kombination“
- Satzlängen: Mittel 12,7, CV 0,48 → variabel, hier kein Signal
- Adjektivketten: „kommunikativ, neugierig und geschäftsorientiert“ (1)

Stufe 2 – KI-Muster (voll)
- Häufungen: Satz 1–7: Floskeln, Lehrbuchvokabular, Lehnmuster, Signifikanz, Figuren
- Figuren: 2 Trikola, 2 „nicht X, sondern Y“, 1 „nicht nur … sondern auch“ – in sieben Sätzen wirkt das wie Schablone
- Lehnmuster aus dem Englischen: „nahtlose“ (3), „auf dieser Reise“, „einen echten Unterschied machen“ (7)

Stufe 3 – Authentizität
- Eigensubstanz: nein – kein Projekt, keine Zahl, kein Name, keine eigene Beobachtung
- Reibung: nein – jede Aussage ist Konsens
- Konsens-Test: nicht bestanden – jede zweite Data Scientistin würde das sofort unterschreiben

Die wichtigsten Befunde
1. Befund: keine Eigensubstanz
   Stelle: „Modelle allein schaffen keinen Mehrwert, sondern erst ihre nahtlose Integration in bestehende Prozesse.“ (Satz 3)
   Vorschlag: „Unser Churn-Modell hat im Shadow-Betrieb [X %] der Kündigungen [Y Wochen] vor dem Vertrieb erkannt. Angerufen hat trotzdem niemand, weil der Score in keinem CRM-Feld stand.“
2. Befund: Rahmen aus Floskeln
   Stelle: „In der heutigen Zeit ist es wichtiger denn je, dass …“ (Satz 1)
   Vorschlag: direkt mit der Beobachtung einsteigen; Satz 1 und Satz 7 streichen.
3. Befund: Figuren-Häufung
   Stelle: „Es geht nicht um Tools. Es geht um Haltung, Kommunikation und Verantwortung.“ (Satz 5–6)
   Vorschlag: eine Figur behalten, die anderen durch eine Aussage ersetzen, die jemand ablehnen könnte: „Ich würde lieber ein schwächeres Modell ausrollen, das im CRM sichtbar ist, als ein starkes im Notebook.“

Rewrite-Vorschlag
Unser Churn-Modell hat im Shadow-Betrieb [X %] der Kündigungen [Y Wochen] vor dem Vertrieb erkannt. Angerufen hat trotzdem niemand: Der Score stand in keinem CRM-Feld. Seitdem frage ich vor jedem Projekt zuerst, wo das Ergebnis am Ende angezeigt wird.
```

The placeholders stay: the numbers must come from the author.

## 2. Cover letter: yellow

Input:

> Mit großer Begeisterung habe ich Ihre Stellenausschreibung als Senior Data
> Scientist gelesen. Ihre innovative Ausrichtung und Ihr ganzheitlicher Ansatz
> im Bereich künstliche Intelligenz sprechen mich sehr an. In meiner bisherigen
> Tätigkeit konnte ich fundierte Kenntnisse in Python, R und Machine Learning
> aufbauen. Bei den Stadtwerken habe ich ein Prognosemodell für den Gasbedarf
> gebaut, das den Fehler im Einkauf um 12 Prozent gesenkt hat. Darüber hinaus
> bringe ich ausgeprägte analytische Fähigkeiten, Teamfähigkeit und
> Kommunikationsstärke mit. Zudem reizt mich die Möglichkeit, an
> zukunftsweisenden Projekten mitzuwirken und mich kontinuierlich
> weiterzuentwickeln. Über eine Einladung zu einem persönlichen Gespräch freue
> ich mich sehr.

Script, in short: 98 words, 7 sentences, CV 0.25 with every sentence between
11 and 21 words; floskeln 3.1, Lehrbuchvokabular 3.1, Abstrakta 3.1 per 100
words; nominal style 9.2; one cluster over sentences 1–7; one digit token, ten
first-person pronouns.

Output (shortened to Ampel and findings):

```text
Ampel: 🟡 manuell prüfen – gleichförmiger Rhythmus und dichte Bewerbungsfloskeln, aber ein echtes Projekt mit Ergebnis ist da.

Die wichtigsten Befunde
1. Befund: Die Substanz steht in Satz 4 und geht unter.
   Stelle: „Bei den Stadtwerken habe ich ein Prognosemodell für den Gasbedarf gebaut …“ (Satz 4)
   Vorschlag: mit diesem Satz anfangen und ihn ausbauen: Welche Daten, welche Entscheidung hat sich dadurch geändert?
2. Befund: gleichförmige Satzlängen (CV 0,25, alle Sätze 11–21 Wörter)
   Stelle: Sätze 1–7
   Vorschlag: einen Satz radikal kürzen („Der Einkauf hat das Modell nach drei Monaten übernommen.“), einen ausbauen.
3. Befund: Eigenschaftsliste statt Beleg
   Stelle: „ausgeprägte analytische Fähigkeiten, Teamfähigkeit und Kommunikationsstärke“ (Satz 5)
   Vorschlag: streichen; zeigen statt behaupten: „Die Einkäufer haben das Modell erst genutzt, nachdem ich ihnen die Fehlerfälle einzeln erklärt hatte.“
```

The many „ich“ did not count as substance: an application is first person by
nature.

## 3. PR description: green

Input (Markdown, as pasted):

```markdown
## Was

Der Feature-Store cached jetzt die Kundensegmente pro Tag statt pro Anfrage.

## Warum

Die Scoring-API hat im Lasttest vom Dienstag bei 200 parallelen Anfragen 1,8 s p95 gebraucht, 70 % davon im Segment-Join. Mit Cache sind es 240 ms.

## Wie getestet

- `pytest tests/feature_store` grün, zwei neue Tests für den Cache-Ablauf um Mitternacht
- Lasttest wiederholt, Ergebnis im Ticket DS-412

## Offen

Der Cache wird nicht invalidiert, wenn jemand Segmente tagsüber nachpflegt. Das passiert laut Vertrieb etwa einmal im Monat; ich halte das für vertretbar, Sophie sieht es kritischer. Bitte im Review entscheiden.
```

Script, in short: 83 words after masking four headings and one inline code
span; no list hits, no figures, no cluster; nominal style 1.2; five digit
tokens.

Output (shortened):

```text
Ampel: 🟢 unauffällig – konkret, gemessen, mit offener Entscheidung.
- Eigensubstanz: ja – Lasttestwerte, Ticket, benannte Gegenposition
- Reibung: ja – „ich halte das für vertretbar, Sophie sieht es kritischer“
Kein Überarbeitungsbedarf. Der offene Punkt ist gut formuliert; lass ihn so.
```

Strong input gets called strong; no finding is invented to fill the template.

## 4. Marketing claim: genre decides

Input: „Wir bauen keine Software. Wir bauen Vertrauen. Schnell, sicher,
skalierbar.“

Script, in short: 10 words, `short_text: true`; one „nicht X, sondern Y“
candidate (sentences 1–2), one bare triad (sentence 3); no cluster.

Output:

```text
KI-STIL-TEST (reduziert, 10 Wörter) · Wir bauen keine Software. Wir
Genre: Marketing-Claim – drei Kurzsätze, offensichtlich als Slogan gebaut.
Ampel: 🟢 – die Figuren sind hier gewollt und tragen.
- Figuren: Kontrast „keine Software … Vertrauen“ und Trikolon „Schnell, sicher, skalierbar“ (bei so wenig Text nur Einzelbeobachtung)
- Eigensubstanz: ja – „Vertrauen statt Software“ ist eine These, die man ablehnen kann
Vorschlag: keiner nötig. Als Satz in einem Memo oder einer PR-Beschreibung wäre dieselbe Konstruktion Schablone.
```
