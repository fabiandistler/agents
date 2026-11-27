---
name: was
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
description: Re-pitching a short message that was read but not understood, in plain German — only the context the point needs, in a fixed three-part shape, glossary terms kept verbatim.
metadata:
  version: "1.2"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

Moment, ich komme nicht mit. Erklär deine letzte Nachricht noch einmal neu, auf Deutsch – auch wenn der Chat bisher in einer anderen Sprache lief.

Mir fehlt Kontext, nicht Kürze. Mehr Kontext heißt aber nicht mehr Text: Nimm nur den Kontext dazu, ohne den ich den Kernpunkt nicht verstehe. Lass alles weg, was ich dafür nicht brauche. Die neue Erklärung ist höchstens so lang wie deine letzte Nachricht.

Antworte in genau dieser Form:

**Worum es geht.** Ein bis zwei Sätze: Wo stehen wir, und warum ist das wichtig?

**Der Punkt.** Was deine letzte Nachricht sagen wollte, in höchstens drei kurzen Spiegelstrichen.

**Was du jetzt tun musst.** Ein Satz: die Entscheidung, der nächste Schritt oder „Nichts – nur zur Info“.

Schreib in Einfacher Sprache:

- Ein Wort, eine Bedeutung. Nenn dasselbe Ding immer gleich.
- Kurze Sätze im Aktiv. Ein Gedanke pro Satz.
- Keine Nominalketten wie „Durchführung der Überprüfung der Konfiguration“. Schreib „prüf die Konfiguration“.

Falls vorhanden: Übernimm die Begriffe aus `GLOSSARY.md` wörtlich und übersetze sie nicht (hat das Repo mehrere, führt `GLOSSARY-MAP.md` zum richtigen). Bezeichner, Pfade und Fehlermeldungen bleiben ebenfalls im Original.
