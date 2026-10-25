# Worked example

Read when unsure about tone, depth, or how strict the materiality gate is.
Three short cases: a first check, its re-check, and a strong input.

## Contents

- [First check: ADR](#first-check-adr)
- [Re-check of the same ADR](#re-check-of-the-same-adr)
- [Strong input: LinkedIn post](#strong-input-linkedin-post)

## First check: ADR

Input: an ADR, "Batch-Pipelines von Airflow auf Dagster migrieren", for the
team lead who signs off the migration quarter. Its claim: Dagster's asset
model halves debugging time. Evidence: one PoC pipeline, two weeks.

```markdown
**Red-Team-Prüfung | ADR Airflow → Dagster** · 14.03.2027

**Kurzurteil**
Die Begründung für Dagster ist stark, wo es um Lineage und lokales Testen geht.
Die zentrale Verwundbarkeit ist der Aufwand: Die Migration von 40 DAGs ist mit
einer PoC-Pipeline geschätzt, und ein Rückweg fehlt. So unterschreibt die
Teamleitung ein Quartal ohne belastbare Zahl.

**Verdikt: Angreifbar** – die Aufwandsschätzung trägt die Entscheidung, ist aber
aus einem Einzelfall hochgerechnet.

**Stakeholder-Snapshot**
- Teamleitung: unterschreibt nur mit Aufwand pro DAG-Typ und Abbruchkriterium – Tendenz: skeptisch
- On-Call: will wissen, wer während der Parallelphase für Alerts in beiden Systemen zuständig ist – Tendenz: offen
- Künftige Maintainerin: Lineage im Asset-Graph spricht klar für Dagster – Tendenz: zustimmend

**Kritischste Punkte**
1. „Migration in 6 Wochen" (Abschnitt Aufwand)
   - Beleg: Schätzung aus einer PoC-Pipeline ohne Sensoren und ohne dynamische Tasks; 11 der 40 DAGs nutzen beides.
   - Warum material: Die Teamleitung entscheidet über ein Quartal; ein Faktor 2 beim Aufwand kippt die Abwägung.
   - Was ihn widerlegen würde: eine zweite PoC mit dem komplexesten DAG im selben Zeitrahmen.
   - Verbesserung: Aufwand je DAG-Typ schätzen, den schwersten DAG zuerst migrieren.
2. Kein Rückweg (fehlt im ADR)
   - Beleg: Abschnitt „Konsequenzen" nennt nur Vorteile.
   - Warum material: Ohne Abbruchkriterium wird eine halbe Migration zum Dauerzustand mit zwei Orchestratoren.
   - Was ihn widerlegen würde: ein definierter Abbruchpunkt mit Kosten des Zurückgehens.
   - Verbesserung: Abbruchkriterium nach dem schwersten DAG festlegen.

**Empfehlungen**
- [BLOCKIEREND] Zweite PoC mit dem komplexesten DAG vor der Freigabe – Adressat: Autor – Zeitpunkt: vor dem Review
- [wichtig] Parallelbetrieb und On-Call-Zuständigkeit regeln – Adressat: Ops – Zeitpunkt: vor Start

**Feinschliff**
- „Halbiert die Debugging-Zeit" als PoC-Beobachtung kennzeichnen, nicht als Messwert.

**Was mein Urteil kippen würde**
Wenn der komplexeste DAG in der geschätzten Zeit migriert, ist das ADR belastbar.

**Die 3 wirksamsten Änderungen**
- Abschnitt Aufwand → Schätzung je DAG-Typ → Teamleitung kann das Quartal planen
- Konsequenzen → Abbruchkriterium und Rückwegkosten → Risiko wird begrenzbar
- Alternativen → warum nicht Airflow 2 mit Datasets → stärkster Einwand ist vorweggenommen
```

Not reported, because it failed the gate: "Teamakzeptanz unklar" (generic),
"Dagster ist jünger als Airflow" (the audience knows it and it does not tip
the decision).

## Re-check of the same ADR

The v2 adds a second PoC (the heaviest DAG took 4 days) and an abort
criterion, but leaves on-call open.

```markdown
**Abgleich zur letzten Prüfung**
- Aufwandsschätzung: gelöst – zweite PoC belegt die Hochrechnung.
- Rückweg: gelöst – Abbruch nach drei DAGs mit Kosten beziffert.
- On-Call in der Parallelphase: offen – weiterhin keine Zuständigkeit.

**Verdikt: Belastbar mit Restaufgabe** – Vorher Angreifbar → jetzt Belastbar mit
Restaufgabe, weil beide kritischen Punkte gelöst sind. Offene materiale Punkte: 1.
Was fehlt bis entscheidungsreif: On-Call-Zuständigkeit für die Parallelphase.
```

## Strong input: LinkedIn post

Input: a post on why the author's team dropped an LLM judge for binary
pass/fail checks, with the before/after agreement numbers and their limits.

```markdown
**Kurzurteil**
Der Post hält: Er nennt die Zahl, die Stichprobe und die Grenze der Aussage
selbst. Ein skeptischer Kollege findet keinen Claim, der über die Daten
hinausgeht.

**Verdikt: Entscheidungsreif** – kein materialer Punkt offen.

**Pointierungsrisiko**
- „LLM-Judges mit 1–10-Skala sind Zeitverschwendung" wird Widerspruch erzeugen;
  das ist eine Folge der Pointierung, kein Mangel.
```

Kritischste Punkte and Empfehlungen are dropped: nothing passed the gate.
