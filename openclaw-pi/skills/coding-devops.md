# Skill-Set für Coding/DevOps + Personal Assistant + Recherche

Empfohlenes Skill-Bundle für deinen Pi-Bot. Built-in-Skills sind in
`openclaw.json` über `skills.enabled` aktiviert. Community-Skills lädst du
per `openclaw skills add <name>` aus ClawHub.

## Built-in (in der Beispiel-Konfig schon aktiv)

| Skill | Wofür | Beispiel-Prompt im Telegram |
| --- | --- | --- |
| `browser` | Web-Recherche, Artikel zusammenfassen, Doku abfragen | "Fass den aktuellen Stand zu Postgres 17 partitioning zusammen." |
| `cron` | Reminder, geplante Tasks | "Erinnere mich Montag 8:30 daran, das Wochen-Standup vorzubereiten." |
| `sessions` | Konversations-Memory zwischen Telegram-Messages | (automatisch aktiv) |
| `canvas` | Markdown-Notizen / langlebige Buffer | "Pack eine Notiz an: Build-Pipeline-Ideen, Punkt 1: ..." |
| `nodes` | Multi-step Workflows | "Hol die letzten 5 Commits aus repo/foo, fass sie zusammen, schreib eine Changelog-Notiz." |

## Empfohlene ClawHub-Skills

Nicht in der Default-Konfig — manuell hinzufügen, wenn du sie brauchst.

```bash
# Git-Operationen aus Telegram (status, diff, log, blame, branch)
openclaw skills add git-tools

# HTTP-Fetch mit sauberer Markdown-Konversion fürs Reading
openclaw skills add http-fetch

# RSS-Feeds: Auto-Summary neuer Items in deinen Telegram-Chat
openclaw skills add rss-reader

# YouTube/Article-Transcript-Reader (Recherche)
openclaw skills add transcript

# Optional, falls du Pi-Sensoren/Skripte später nachrüsten willst
openclaw skills add shell-runner   # läuft IMMER über execApprovals!
```

Nach jedem `skills add` einmal:

```bash
systemctl --user restart openclaw
```

und in `openclaw.json` den Skill-Namen in `skills.enabled` ergänzen.

## Shell-Exec — bewusst nicht als eigener Skill

Shell-Befehle (`bash -lc '...'`) laufen als Agent-Default-Tool, nicht als
Skill. Mit `channels.telegram.execApprovals.enabled: true` wird **jeder**
Aufruf in Telegram bestätigt — du siehst den geplanten Befehl und drückst
einen Inline-Button, bevor er läuft. Das ist auf einem Pi 4 essentiell.

Wenn du Approvals als zu lästig empfindest und nur du Zugriff hast, kannst
du in `openclaw.json` Profile mit `autoApprove`-Patterns für read-only
Befehle anlegen (`git status`, `ls`, `cat`, ...). Vorsicht: Patterns sind
dehnbar — lieber einmal mehr klicken als einmal `rm -rf` durchwinken.

## Modell-Wahl

In der Beispielkonfig:

- **Primär:** `anthropic/claude-sonnet-4-6` — schnell, günstig im Max-Kontingent, reicht für 90 % der Telegram-Anfragen.
- **Fallback:** `anthropic/claude-opus-4-7` — wird gezogen, wenn der Primär-Call fehlschlägt oder du explizit `/model opus` im Chat schickst.

Wenn dein Pi vor allem für lange Recherche-Outputs läuft, kannst du auch
direkt Opus als Primär setzen — Latenz steigt aber spürbar.
