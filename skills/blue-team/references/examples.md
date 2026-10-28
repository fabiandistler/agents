# Blue team examples

Two illustrative outputs. Tone, length and structure are binding; the subject matter is not. Numbers the user has not supplied stay as marked gaps in square brackets.

## Kurzform

Input: „Was hältst du davon, spontan: Ich poste auf LinkedIn, dass Prompt Engineering tot ist – Evals sind das neue Prompt Engineering.“

Output:

> Der Kern ist eine Verschiebung: Qualität entsteht nicht mehr beim Formulieren des Prompts, sondern beim Messen (Adressat: AI Engineers und Tech Leads in deinem Netzwerk – Annahme). Wo es nachgibt: „tot“ ist mit einem Satz widerlegt – jeder, der gerade einen System-Prompt debuggt, antwortet mit einem Gegenbeispiel, und die Diskussion dreht sich um das Wort statt um deine These. Verstärkung: Behaupte die Reihenfolge, nicht den Tod, und stütze sie mit einem eigenen Fall. Gehärtete Formulierung: „Prompt Engineering ohne Eval ist Raten. Seit wir [Anlass: dein Projekt] zuerst [Zahl] gelabelte Fälle gebaut haben, ändern wir einen Prompt nur noch, wenn sich eine Zahl bewegt – und [Anteil] unserer Prompt-Ideen haben keine bewegt.“ Gehärtet; offen sind Anlass und Zahlen – ohne einen echten Fall aus deinem Projekt fällt der Beleg, dann den zweiten Satz streichen. Block auf Wunsch.

## Block (Schnellhärtung)

Input: „Härte das: Wir ersetzen das R-Shiny-Dashboard für den Vertrieb durch einen LLM-Chat auf dem Data Warehouse. Dann kann jeder seine Fragen selbst stellen, und wir müssen nicht jede neue Kennzahl einbauen. Außerdem ist Shiny eh veraltet.“

Output:

```text
BLUE TEAM | Shiny-Dashboard → LLM-Chat

KERN
Das Team ist der Engpass für Ad-hoc-Auswertungen im Vertrieb; ein Text-to-SQL-Chat auf dem Warehouse verlagert einfache Fragen zum Fachbereich und entlastet das Team (Adressat: Architekturrunde und Teamlead – Annahme).
Beiwerk: „Shiny ist eh veraltet“ – ein Geschmacksurteil, das die R-Nutzer gegen dich aufbringt, ohne dass der Kern es braucht.

BELASTUNG
#1 „ersetzen“ | Architekturrunde: Wer verantwortet eine falsche Umsatzzahl, wenn das Modell einen Join falsch baut? Das Dashboard liefert geprüfte Kennzahlen, der Chat nicht. | Verstärkung: ergänzen statt ersetzen – das Dashboard bleibt Quelle der Wahrheit für die Kern-KPIs, der Chat beantwortet Einzelfragen und zeigt zu jeder Antwort das erzeugte SQL.
#2 „jeder seine Fragen“ | Teamlead: Entlastung ohne Messgröße ist nicht prüfbar. | Verstärkung: Pilot mit Abbruchkriterium, gemessen an einem Eval-Set aus echten Tickets.

GEHÄRTETE FASSUNG
Unser Team ist der Engpass für Ad-hoc-Auswertungen im Vertrieb. Wir ergänzen das Shiny-Dashboard um einen Text-to-SQL-Chat auf dem Warehouse: Das Dashboard bleibt Quelle der Wahrheit für die Kern-KPIs, der Chat beantwortet Einzelfragen und zeigt zu jeder Antwort das SQL. Vier Wochen Pilot mit einem Eval-Set aus [Zahl] echten Tickets; weiter geht es nur, wenn der Chat mindestens [Schwelle] davon korrekt beantwortet.

HÄRTEGRAD
Gehärtet | Hält vor der Architekturrunde. Offen: die Schwelle – ohne Zahlen aus den Tickets der letzten Monate ist das Abbruchkriterium gesetzt, nicht begründet.
```

What the examples show: Beiwerk is named and removed, every load point is tied to a phrase and carries a reinforcement, the version is more pointed than the input, and an evidence gap stays marked instead of being papered over.
