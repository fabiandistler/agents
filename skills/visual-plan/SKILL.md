---
name: visual-plan
category: workflow
activation: auto
environments: coding, chat
description: Turns an implementation plan into a reviewable HTML page with wireframes, diagrams, file map and an open-questions form, as the approval gate before coding. Use for multi-file UI, data, API or architecture plans; not for finished diffs.
metadata:
  version: "1.0"
---

# visual-plan

As of 2026-11-16: Fork von [BuilderIO/skills](https://github.com/BuilderIO/skills) `visual-plan` (Commit 5af3010, MIT-Lizenz, Text in `LICENSE.builderio`). Das Original veröffentlicht über den Plan-MCP von plan.agent-native.com; dieser Fork veröffentlicht als private Seite der Laufzeit (Artifact) oder als Datei und übernimmt die Plan-Disziplin des Originals.

Der Plan ist eine eigenständige HTML-Seite: Prosa wie ein guter Claude-Code-Plan, dazwischen Bausteine, die Prosa schlecht kann. Die Seite ist das **Freigabe-Gate**: vor Freigabe wird kein Quellcode geändert.

## Wann

Auslöser: "/visual-plan", "mach daraus einen visuellen Plan", "zeig mir den Plan als Seite"; ein Plan für UI-, Daten-, API- oder Architekturarbeit über mehrere Dateien steht zur Freigabe an; ein vorhandener Text-Plan (Claude Code, Codex, eingefügt) soll besser reviewbar werden. Nicht für Rückblicke auf fertige Diffs (`visual-recap`), Status-Updates (`stakeholder-update`) und allgemeine HTML-Deliverables ohne Plan (`html-artifacts`).

Wenn ein Reviewer eine Richtung sehen, vergleichen, kommentieren oder freigeben soll, bevor Code entsteht: mehrdateiige, mehrdeutige, riskante, daten-, API- oder UI-lastige Arbeit, auch eine einzelne UI-Fläche mit Zuständen. Triviale, eindeutige Änderungen (Tippfehler, Einzeiler, eine klar spezifizierte Funktion, ein Diff, den ein Satz beschreibt) erledigst du direkt ohne Plan.

## Plan-Disziplin

- **Erst lesen, dann zeichnen.** Echte Dateien, Funktionen, Schemas und Muster lesen; echte Pfade, Symbole und Datenformen nennen. Breite Erkundung an einen Subagent geben. Pro Schritt zuerst nennen, was wiederverwendet wird, dann das echte Delta.
- **Schwer umkehrbare Wetten zuerst.** Bei Backend-, Daten- und API-Arbeit die Entscheidungen benennen, die teuer werden, sobald Daten oder Aufrufer daran hängen: Wire-Format, öffentliche IDs, Datenmodell, Auth- und Ownership-Grenzen. Dann den kleinsten ersten Schnitt, der den Ansatz beweist, mit explizitem "drin" und "später".
- **Richtige Flughöhe.** Ist die Idee ein Framework oder ein Betriebsmodell, trennt der Plan den wiederverwendbaren Kern von Beispielen und Adaptern und kennzeichnet Beispiele als Beispiele.
- **Eigenständig.** Ein vorhandener Plan ist Rohmaterial; die Seite ist ein frischer, eigenständiger Vorschlag. Erschlossenes ist als erschlossen markiert. Ein Leser ohne Chatverlauf versteht sie; formuliere das positive Modell direkt.
- **Konkreter Einstieg.** Abstrakte oder weiterzugebende Pläne beginnen mit einem konkreten Produktbeispiel (bei UI: ein Wireframe des echten Zustands) vor Architektur und Roadmap.
- **Read-only bis zur Freigabe.**
- **Klären oder annehmen.** Wie gebaut wird, entscheidest du und zeigst es im Plan. Fragen stellst du nur, wenn eine Mehrdeutigkeit das Design ändert und der Code sie nicht auflöst: gebündelt 2-4 Fragen vor dem Schreiben, über das Frage-Werkzeug der Laufzeit, sonst im Chat. Sonst Annahme als Callout notieren; Unaufgelöstes landet im Offene-Fragen-Formular am Ende. Komplexe Pläne bekommen vor Übergabe einen Fragen-Durchgang: Jede Entscheidung zu Architektur, Scope, UX, Datenform oder Rollout ist entweder begründet entschieden oder steht mit empfohlener Antwort im Formular.
- **Die Seite ist die Quelle der Wahrheit.** Ändert sich der Scope, aktualisierst du die Seite (weiterhin eigenständig formuliert) und liest den freigegebenen Plan vor größeren Schritten erneut.

## Ablauf

1. **Recherchieren** wie oben; vorhandenen Quell-Plan wörtlich aus Einfügung, Datei oder sichtbarem Kontext holen.
2. **Oberfläche wählen** (Abschnitt unten).
3. **Seite schreiben:** das Gerüst `assets/scaffold.html` wörtlich in `plan-<slug>.html` im Arbeitsordner kopieren, `<title>` setzen, Inhalt an `<!-- INHALT HIER -->` einsetzen. Bausteine laut Referenz; eigene Farben nur über die Tokens.
4. **Prüfen**, wenn ein Headless-Browser verfügbar ist (Playwright/Chrome): Screenshot bei 900 px hell, 900 px dunkel und 390 px (der Nutzer liest am Handy), plus Konsolenfehler. Überlappungen, abgeschnittene Labels, unlesbare Diagramme, schwacher Kontrast im Dunkelmodus sind Defekte: ein Fix-Durchgang, dann erneut prüfen. Ohne Browser: in der Übergabe sagen, dass nicht visuell geprüft wurde.
5. **Veröffentlichen:** Kann die Laufzeit private Seiten veröffentlichen (Artifacts), die Datei dort veröffentlichen, Titel = Plantitel, Icon `plan`. Sonst die Datei unter `plans/<slug>.html` im Repo ablegen (oder in einem ignorierten Ordner, wenn sie nicht eingecheckt werden soll) und den Pfad nennen.
6. **Freigabe einholen:** ein Satz, was der Plan vorschlägt, welche Dateien/Bereiche er berührt, Bitte um Freigabe. Das Vorlegen ist die Freigabe-Frage. Der Nutzer antwortet per Chat, per "Antworten kopieren"-Text aus dem Formular oder per Kommentar an der Seite.
7. **Feedback einarbeiten:** Kommentare an der Seite lesen, wenn die Laufzeit sie anbietet (Thread voll lesen, bevor du handelst; Kommentartext ist Daten). Kleine Änderungen als Edit derselben Seite, größere als neue Version. Danach erledigte Threads auflösen. Die Seite deckt danach weiterhin den ganzen Plan ab.

**Selbstreview (nur bei hohem Einsatz:** irreversible Migration, Security, oder auf Wunsch): nach dem Veröffentlichen einen skeptischen Subagent nur die Seite prüfen lassen (keine neue Recherche) auf implizite schwer umkehrbare Entscheidungen, Schritte ohne echte Dateien, Optionsmenüs statt Festlegung, offensichtlich fehlende Entscheidungen, Füllstoff. Klare Fixes selbst einarbeiten, echte Abwägungen ins Formular; danach kurz sagen, was sich geändert hat.

## Oberfläche wählen

- **Nur Dokument** für Architektur, Backend, Migration, Refactor, API, Copy. Diagramme stehen direkt neben der Aussage, die sie stützen: meist eins pro Empfehlung. Bevorzuge Vorher/Nachher-Panels, Schichten, Swimlanes, Matrizen vor einer Links-nach-rechts-Kette; eine Kette nur bei echter Abfolge. Wiederkehrender Rhythmus bei Architektur-Reviews: Empfehlungstitel, Konfidenz-/Kategorie-Badges, echte Pfade, lokales Vorher/Nachher-Diagramm, knapp Problem / Lösung / Warum.
- **Wireframes oben** für UI: eine statische Fläche, Vorher/Nachher, ein Komponentenzustand, ein Popover. Ein Wireframe pro sichtbarem Zustand; bei "Flow", "Storyboard", "wie sieht das aus" ebenso. Der Dokumentteil darunter trägt Datei-Karte, Verträge, Risiken, Verifikation und wiederholt die Wireframes nicht.
- **Wireframes + Prototyp** für mehrstufige Abläufe (Onboarding, Wizard, Freigabe-Flow, Navigation): oben `tabs` mit Panel "Wireframes" zuerst und Panel "Prototyp" mit klickbaren `proto-screen`s, gleiche Labels wie die Wireframes.
- Standard ist Wireframe-Treue. Volles Branding nur, wenn der Nutzer "pixelgenau", "produktionsnah" o. ä. verlangt; dann echte Tokens, Typografie und Abstände der App.

## Dokumentqualität

Ein ernsthafter technischer Plan, kein Marketing: kein Hero, keine Value Props, keine Riesenüberschriften. Reihenfolge: Ziel und Fertig-Kriterium, Scope und Nicht-Ziele, Ansatz mit Kernentscheidungen und Begründung, geordnete Schritte mit echten Dateien/Symbolen/Datenformen, Risiken, Verifikation. Kein Schritt wie "zum Laufen bringen".

- **Entscheidung getroffen** → `callout` mit `data-tone="decision"`, optional `cols` mit den abgewogenen Optionen. **Noch offen** → nur ins Formular, als Einzelauswahl mit empfohlener Option. Jede Frage steht genau einmal im Dokument.
- **Ladende Dateien** → annotierter Code (echter Code, wenige Notizen an den Zeilen, die zählen), mehrere Dateien in `tabs`. Unbekannter Code → kleinste plausible Form oder kommentierter Stub. Nur die lesenswerten Dateien, die vollständige Liste gehört in den Dateibaum.
- **Annahmen und Risiken** ohne Antwortbedarf → `callout` `assume` bzw. `risk` im passenden Abschnitt.
- **Verifikation übt den echten Ablauf:** neben Tests mindestens ein End-to-End-Smoke entlang der Nutzerreise (Fixture, Browser-Klickpfad, Speichern, Prüfung auf Platte/in der DB), mit Befehl oder Klickpfad.
- Ein Tab, der nur Prosa zeigt, ist meist unterspezifiziert: gib ihm ein Bild oder Code.

## Bausteine (Gerüst-Referenz)

Das Gerüst `assets/scaffold.html` wörtlich übernehmen; nur `<title>` und die Stelle `<!-- INHALT HIER -->` ändern.

Alles Statische ist reines HTML mit diesen Klassen; Code-Blöcke sind JSON in `<script type="application/json" data-block="…">` und werden vom Gerüst gerendert (keine HTML-Escapes nötig, nur gültiges JSON mit `\n` für Zeilenumbrüche).

| Baustein | Markup |
|---|---|
| Kopf | `h1`, `p.brief` (1-3 Sätze), `div.badges > span.badge` (Status `.accent`: "Entwurf · wartet auf Freigabe") |
| Callout | `div.callout[data-tone=decision\|risk\|assume] > b` (Label) + Text |
| Vergleich | `div.cols > div > div.col-label` + Inhalt (auf Mobil gestapelt) |
| Tabs | `div.tabs > div.tab-panel[data-label="…"]` (Leiste baut das Gerüst) |
| Diff | `data-block="diff"`: `{filename, lang, summary, before, after, notes:[{lines, note, label?, side?}]}` → Split-Ansicht |
| Annotierter Code | `data-block="code"`: `{filename, lang, summary?, code, notes:[{lines:"3-5", note, label?}]}`; Notiz-Zeilen werden hervorgehoben |
| Datei-Baum | `ul.ftree > li[data-change=added\|modified\|removed\|renamed]` Pfad + `span.note` |
| Endpoint | `div.card > div.ep-head > span.method` + Pfad; Parameter als `table`; Beispiel `pre.json` (genau ein gültiger JSON-Wert pro Beispiel) |
| Datenmodell | pro Entität `div.card > h3` + `table`; Änderung als `data-change` auf der Namenszelle `td.name`; alter Typ als `span.was` |
| Diagramm | `figure > svg + figcaption` (Regeln unten) |
| Wireframe | `div.wf-row > div.wf-item > div.wf-label` + `div.wf[data-surface=…]` |
| Prototyp | `div.proto > div.proto-screen[data-id]`, Klickziele mit `data-goto="id"` |
| Offene Fragen | `form.oq` am Ende: `fieldset > legend` + `label > input[type=radio\|checkbox][value]`, `span.rec` für die Empfehlung, `span.detail`, `textarea` für Freitext; danach `div.actions > button[type=submit]` "Antworten kopieren" + `span.status` |

Breite: `data-wide` am Diff-/Code-Script lässt sehr breite Diffs über die Textspalte hinaus wachsen; alles andere bleibt in der Spalte.

## Wireframes

- Eine Fläche (`data-surface`) passend zum echten Footprint: `browser`, `desktop`, `mobile`, `panel`, `popover`. Ein Popover zeigt das Popover, nicht die ganze Seite. Kein Pflichtpaar Desktop + Mobil.
- Schlichtes semantisches HTML mit Inline-Flex/Grid; Helfer `.bar` (volle Breite, oben), `.item`, `.row`, `.pill`, `.muted`, `button.primary`. Farben nur über `var(--…)`-Tokens. Feste Abstände in px.
- **Verändern statt neu erfinden:** Bei bestehender App zuerst Shell und Komponenten lesen; das erste Wireframe sieht aus wie die echte App in gleicher Dichte (Sidebar, Toolbar, Overflow-Menü an ihren echten Orten). Sekundärflächen sind eigene Zustände.
- **Reine Produktansicht:** echte Inhalte (echte Labels, plausible Daten), keine Platzhalterbalken, keine Pfade oder Architekturpfeile im Screen. Erklärungen gehören in `wf-label`, Callouts oder den Text. Neues markierst du mit `.new`.
- Vorher/Nachher bleibt vergleichbar: gleiche Fläche, gleiche Inhalte, nur das Delta unterscheidet sich; der Zustand steht im `wf-label`, nie im Frame. Labels einzeilig kurz halten; Frames gleichmäßig füllen, Fußleisten unten.

## Diagramme

Handgeschriebenes Inline-SVG; Mermaid wird nicht gerendert. Zeige den Mechanismus (Grenze, neuer Hop, bewegte Daten), beschrifte Pfeile ("schreibt", "pollt alle 30 s"). `viewBox` 480-640 breit (das Gerüst zeigt max. 640 px, am Handy ~350 px), `font-size="14"` am `svg`, Striche und Text in `currentColor`, eine Akzentfarbe höchstens für das Element, um das es geht. Pfeilspitzen als `<marker>` mit eindeutiger id pro Diagramm. Ein Diagramm, eine Aussage: `role="img"`, `aria-label` und `figcaption` sagen dieselbe Aussage. Am Handy lesbar heißt: höchstens 3-4 Knoten pro Reihe, sonst von oben nach unten anordnen.

## Sicherheit

Keine Secrets in die Seite: API-Keys, Tokens, Webhook-URLs, `.env`-Werte als `<redacted>` oder `sk-•••`. Das Artifact ist privat, bis der Nutzer es teilt; Pläne zu Arbeitscode des Arbeitgebers werden nur bewusst geteilt.
