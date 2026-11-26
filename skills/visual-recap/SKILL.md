---
name: visual-recap
category: workflow
activation: auto
environments: coding, chat
description: Turns finished work (PR, branch, commit, diff, session changes) into a visual HTML recap with wireframes, diagrams, schema and API changes, file tree and annotated diffs. Use when a reviewer should see the shape before the line diff.
metadata:
  version: "1.0"
---

# visual-recap

As of 2026-11-16: Fork von [BuilderIO/skills](https://github.com/BuilderIO/skills) `visual-recap` (Commit 5af3010, MIT-Lizenz, Text in `LICENSE.builderio`). Das Original veröffentlicht über den Plan-MCP von plan.agent-native.com; dieser Fork veröffentlicht als private Seite der Laufzeit (Artifact) oder als Datei.

Ein Recap ist ein Plan in Rückwärtsrichtung: Er beschreibt eine Änderung, die existiert, eine Flughöhe über dem Zeilen-Review. Schema-, API-, Datei- und Architekturänderungen werden zu denselben Bausteinen wie im Plan. Der Reviewer sieht zuerst die Form, dann die ladenden Zeilen.

## Wann

Auslöser: "/visual-recap", "recap diesen PR", "zeig mir, was der Branch geändert hat", "fass die Änderungen visuell zusammen". Nicht für Pläne vor dem Coden (`visual-plan`), Review gegen Standards oder Spec und Status-Updates für Stakeholder (`stakeholder-update`).

Bei großen, mehrdateiigen Änderungen oder solchen, die Schema, API-Verträge, Architektur oder UI berühren. Kleine, einzelne oder offensichtliche Diffs reviewt man schneller als Diff: dann kurz sagen und keinen Recap bauen.

## Ablauf

1. **Scope bestimmen.** Gegebene Referenz (PR, Branch, Commit, Range) oder, in einer laufenden Session, die **ganze Arbeitseinheit** dieser Session: ursprüngliche Umsetzung, spätere Fixes, UI-Nachbesserungen, Tests, Changesets, Skill-/Doku-Änderungen. Fremde, schon vorher vorhandene Änderungen bleiben draußen. Ist der Scope nicht ableitbar: Annahme nennen oder kurz fragen.
2. **Diff in einem Durchgang lesen** (`git diff --stat`, dann die Dateien; bei PRs den PR-Diff lesen: Use the GitHub MCP tools if the session has them; otherwise `gh api repos/<owner>/<repo>/pulls/<n> -H 'Accept: application/vnd.github.diff'`) und dabei Notizen führen: Inventar der geänderten Routen, Komponenten, Popover/Dialoge, Rollen-/Zugriffszustände, Leer-/Fehlerzustände, Schema-, API- und geteilten Abstraktionen. Danach arbeitest du aus den Notizen, ohne den Diff erneut ganz zu lesen.
3. **Skill `visual-plan` laden** und daraus übernehmen: das Gerüst (`assets/scaffold.html` dort), die Bausteine, die Wireframe- und Diagrammregeln sowie Prüfen und Veröffentlichen (Schritte 4-5 dort). Diese Teile gelten hier unverändert.
4. **Seite in `recap-<slug>.html` schreiben** nach Kanon und Zuordnung unten. Jedes Inventar-Element ist entweder durch einen Baustein vertreten oder bewusst weggelassen (winzig, redundant, nicht sichtbar).
5. **Prüfen und veröffentlichen** wie in visual-plan; Badge-Status "Recap", Icon `review`.
6. **Übergeben:** ein Satz zur Kernaussage der Änderung. Feedback per Chat oder Kommentar an der Seite fließt zurück in den Code (Kommentar → Agent → Diff); danach den Recap so aktualisieren, dass er weiter die ganze Arbeitseinheit plus Korrektur abdeckt.

## Kanon und Budgets

Von oben nach unten:

1. **UI-Schlagzeile:** Wireframes zuerst, wenn der Diff gerenderte UI ändert.
2. **Ergebnis-Erzählung:** 1-3 Absätze, was sich geändert hat und warum.
3. **Datenmodell / Endpoint** für Schema- und Vertragsänderungen, Vorher/Nachher in `cols`.
4. **Datei-Baum** mit `data-change` je Datei.
5. **`## Key changes`:** genau ein `tabs`-Block mit Diff bzw. annotiertem Code, ein Tab pro Schlüsseldatei (Label = Pfad oder kurzer Name mit Ordner-Hinweis).

Budgets, zugleich die Kostenobergrenze: 3-8 Key-Change-Tabs; pro Tab unter ~150 Zeilen, den Rest einer langen Datei zusammenfassen; Titel ≤ 70 Zeichen; Brief 1-3 Sätze.

**Schlank, aber substanziell.** Kein Prosa-Block, der nur sagt, dass der Recap eine Hilfe ist, wie viele Dateien sich geändert haben oder aus welchem Ref er stammt: Titel, Brief und Datei-Baum tragen das. Prosa nur für Ziel, echtes Kompatibilitätsrisiko, sichtbare Entscheidung oder fundierte Review-Notiz. Ein großer Diff braucht trotzdem Datei-Baum und Key-Change-Diffs; ein Wireframe plus ein Satz für 40 Dateien schickt den Reviewer zurück in den Rohdiff.

Gut: 25-Dateien-Auth-Änderung mit Vorher/Nachher-Wireframes der Login-Fläche, zwei Absätzen Erzählung, Datenmodell der Session-Tabelle mit Änderungsflags, Endpoint der neuen Refresh-Route, Datei-Baum und fünf fokussierten Key-Change-Tabs mit je einer Zusammenfassung und wenigen Notizen.

## Zuordnung Diff → Baustein

- **Schema/Migration** → Datenmodell der resultierenden Entitäten; pro Feld `data-change` (added/modified/removed/renamed), geänderter Typ mit `span.was`. Das ist die Schlagzeile; SQL-Diff nur, wenn das exakte Statement zählt.
- **API/Route/Action** → Endpoint im Zustand nach der Änderung; geänderte Parameter/Antworten mit `data-change` und `span.was`; ganz neue oder entfernte Route mit `data-change` im Kopf, entfernte zusätzlich in Prosa erklärt. Jedes Beispiel genau ein gültiger JSON-Wert; mehrere Nachrichtenformen (Erfolg vs. Fehler, Frame-Typen) als je eigenes beschriftetes Beispiel. Mehrere Endpoints untereinander, außer bei echtem Vorher/Nachher-Vertrag.
- **Kompatibilitätskritisch** → kurzer `callout` `risk` neben dem Baustein: welches Feld/Endpoint/Verhalten, breaking / riskant / nicht breaking.
- **Bedeutsamer Code-Hunk** → Diff (Split) mit echtem `before`/`after`, `filename`, `lang` und einer Ein-Satz-`summary` (was und warum). Schlüsseldateien bekommen wenige Notizen an den Zeilen, die zählen (Nachher-Zeilennummern; `side:"before"` für entfernte Zeilen).
- **Neue Datei / großer neuer Block ohne sinnvolles Vorher** → annotierter Code statt einseitigem Diff.
- **Dateien neu/entfernt/umbenannt** → Datei-Baum mit `data-change` und kurzer Notiz.
- **Architektur-/Datenfluss-Verschiebung** → Diagramm als Vorher/Nachher-Panels, Schichten oder Swimlanes. UI-Steuerelemente zeigst du als Wireframe, nicht als Diagramm.

## UI-Änderungen brauchen Wireframes

Ändert der Diff Layout, Dichte, sichtbaren Zustand, Bedienelemente, Navigation, Menüs, Dialoge oder Design-Tokens, enthält der Recap Wireframes. Abdeckung aus dem Diff ableiten:

- **Einstieg:** wo die Änderung erscheint (Header, Listenzeile, Toolbar, Menü-Trigger).
- **Interaktionsfläche:** was sich öffnet oder ändert (Popover, Dialog, Tab, Sheet, Inline-Editor, Toast).
- **Ergebnis:** Zielzustand (Seite, Read-only, Leer-, Fehler-, Lade-, Kein-Zugriff-, Gespeichert-Zustand).
- **Rollen:** bei Rechteänderungen Owner/Admin vs. Viewer als Paar oder Matrix.

Bei UI-lastigen PRs alle drei Stufen Einstieg → Fläche → Ergebnis zeigen. Kleinste klare Form wählen: Vorher/Nachher bei direktem Vergleich; nur Nachher bei rein Additivem; Zustandsfolge bei Flows. Kleine Flächen mit passendem `data-surface`. Wireframes stützen sich auf Komponentennamen und diff-sichtbare Labels; Erschlossenes markierst du im `wf-label` als "erschlossen".

## Wahr durch Konstruktion

Diff, Datenmodell, Endpoint und Datei-Baum entstehen mechanisch aus den echten geänderten Zeilen: echte Pfade, Felder, Methoden, Vorher/Nachher-Text. Du schreibst frei nur die Prosa: Warum, Erzählung, Risikoeinschätzung. Was der Diff nicht enthält, bleibt draußen; Erschlossenes ist als erschlossen markiert. Ein selbstbewusst falscher Recap verleitet den Reviewer, genau die falsch zusammengefasste Zeile zu überspringen.

## Sicherheit

Secrets aus dem Diff (API-Keys, Tokens, Webhook-URLs, Signing-Secrets, `.env`-Werte) erscheinen in keinem Baustein, keiner Notiz und keiner Bildunterschrift: `<redacted>` oder `sk-•••`. Ein Recap legt unveröffentlichtes Schema und interne Endpoints offen; behandle ihn wie den Quellcode. Das Artifact ist privat, bis der Nutzer es teilt.
