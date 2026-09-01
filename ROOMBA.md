# ROOMBA - Wartungs-Katalog

<!--
Quelle: Prompt-Idee Fabian Distler, 2026-09-01, verarbeitet mit Skill `idee-zu-artefakt`.
Ausfuehrung: Plugin `roomba`, Skill `roomba-run`.
Pruefdatum: 2026-12-01 - siehe Abbaubedingung unten.
-->

## Status

| Feld | Wert |
|---|---|
| Letzter Lauf | *(noch keiner unter diesem Katalog)* |
| Letzter Job | - |
| Naechster faelliger Job | `deps-audit` (kein Job je gelaufen -> Katalogreihenfolge) |
| Offene roomba-PRs | #86 `test-flakiness`, #88 `perf-quickwins` (beide werden uebersprungen), #87 `security-footguns` (Job ist retired, siehe unten) |

## Regeln

1. **Genau ein Job pro Lauf.**
2. **Jobauswahl nach relativer Ueberfaelligkeit:** `score = (heute - zuletzt) / cooldown`.
   Hoechster Score gewinnt, `-` zaehlt als unendlich, Gleichstand nach Katalogreihenfolge.
   Grund: ein 7-Tage-Job wuerde bei Auswahl nach absolutem Datum alle Slots fressen.
3. **Job mit offenem roomba-PR wird uebersprungen** und gilt als in Arbeit.
4. **Jeder Lauf endet in genau einem PR** auf `roomba/<job>-<YYYY-MM-DD>`, auch reine
   Report-Jobs. Kein Commit auf den Default-Branch.
5. **Diff-Budget < 300 Zeilen.** Rest unter *Backlog*.
6. **Verhalten wird nie geaendert.** Aenderungen nur an Doku, toten Exporten und
   Testinfrastruktur - und nur bei identischem Check-Status vor und nach dem Lauf.

## Was NICHT in diesen Katalog gehoert

Alles, was ein Werkzeug abschliessend beantwortet, gehoert ins CI-Gate, nicht in einen
Agentenlauf. Ein Job, der bei gruenem CI regelmaessig nichts findet, verbrennt nur
Rotationsslots.

| Frueher als Job gedacht | Laeuft stattdessen im CI |
|---|---|
| security-footguns | gitleaks, semgrep, bandit + pre-commit |
| dead-code (lokale Vars/Imports) | `ruff F401/F841`, `lintr::object_usage_linter` |

Im Katalog bleibt nur die Rest-Frage: `dead-exports` (Export ueber die Paketgrenze).

## Vorbedingungen je Lauf

- Working Tree sauber, auf dem Default-Branch, `git fetch` gelaufen.
- Baseline erfasst: `R CMD check` / `pytest` **vor** dem Lauf.
- Rote oder fehlende Baseline -> nur Report-Jobs.

## Jobs

| # | Job | Vorstufe | Output | Cooldown | Zuletzt gelaufen |
|---|---|---|---|---|---|
| 1 | `deps-audit` | ja | Report | 7d | - |
| 2 | `doc-drift` | nein | PR | 14d | - |
| 3 | `dead-exports` | ja | PR | 14d | - |
| 4 | `error-edges` | nein | Report | 14d | - |
| 5 | `test-flakiness` | ja | PR | 30d | - |
| 6 | `perf-quickwins` | nein | Report | 30d | - |

Rest-Frage je Job (Details im Skill unter `references/jobs.md`):

1. **deps-audit** - Machen mich diese Updates kaputt? Scanner liefert die Liste, der Lauf
   liefert Breaking-Change-Risiko aus gelesenen Changelogs und eine Empfehlung.
2. **doc-drift** - Beschreibt die Doku noch, was der Code tut? Belegt durch Ausfuehren der
   Beispiele. Nur Doku wird angefasst.
3. **dead-exports** - Ist dieser Export ueber die Paketgrenze wirklich tot? Nachweis pro
   Streichung: git grep, NAMESPACE/`__all__`, Vignetten, Reverse-Deps, `git log -S`.
4. **error-edges** - Wo schluckt der Code einen Fehler still? Report, kein PR.
5. **test-flakiness** - Ist die Zeit-/Zufalls-/Netzabhaengigkeit Absicht? Nur die Quelle
   des Nichtdeterminismus wird ersetzt, nie die Assertion.
6. **perf-quickwins** - Messbar langsam oder nur unschoen? Ohne Messung kein Befund.

## Backlog

*(leer)*

## Lauf-Historie

| Datum | Job | Output | PR |
|---|---|---|---|
| - | - | - | - |

## Abbaubedingung

Stichtag 2026-12-01. Weniger als vier Laeufe oder kein einziger gemergter roomba-PR ->
zurueckbauen auf eine manuelle Checkliste, Plugin deinstallieren.
