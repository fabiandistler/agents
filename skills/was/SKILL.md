---
name: was
category: communication
activation: command
disable-model-invocation: true
environments: coding, chat
description: Re-pitches a short message in plain German by adding missing context before simplifying it, while keeping the repo's glossary terms verbatim.
metadata:
  version: "1.1"
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

Moment, ich komme nicht mit. Erklär deine letzte Nachricht noch einmal neu, auf Deutsch – auch wenn der Chat bisher in einer anderen Sprache lief.

- Kürz nicht. Mir fehlt Kontext, nicht Kürze.
- Gib mir zuerst kurz den Kontext: Wo stehen wir, und warum ist das wichtig?
- Schreib in Einfacher Sprache:
  - Ein Wort, eine Bedeutung. Nenn dasselbe Ding immer gleich.
  - Kurze Sätze im Aktiv. Ein Gedanke pro Satz.
  - Keine Nominalketten wie „Durchführung der Überprüfung der Konfiguration“. Schreib „prüf die Konfiguration“.
- Übernimm die Begriffe aus `GLOSSARY.md` wörtlich und übersetze sie nicht (hat das Repo mehrere, führt `GLOSSARY-MAP.md` zum richtigen). Bezeichner, Pfade und Fehlermeldungen bleiben ebenfalls im Original.

War die Nachricht dagegen lang und ich habe sie gar nicht gelesen, schlag mir stattdessen vor, den Command „tldr“ auszuführen: Die Länge entscheidet, und die sehe ich vor dem Lesen.
