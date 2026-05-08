# OpenClaw auf Raspberry Pi 4 — mit Telegram & Claude Max

Dein persönlicher KI-Agent auf dem Pi, ansprechbar über Telegram, bezahlt
über deine **Claude-Max-Subscription** statt API-Tokens.

- **OpenClaw** als Agent-Framework ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw))
- **Telegram** als einziger Channel (DMs, nur du)
- **Claude Code CLI** als Auth-Brücke zu Claude Max (OAuth, kein API-Key)
- **systemd user service** mit Hardening + Auto-Restart
- Skills für Coding/DevOps, Personal Assistant und Recherche

---

## Hardware & OS

- Raspberry Pi 4 (4 GB RAM oder mehr empfohlen)
- microSD ≥ 32 GB, idealerweise A1/A2-Class
- **Raspberry Pi OS Lite (64-bit)** — 32-bit funktioniert nicht zuverlässig mit Node 24
- Ethernet oder stabiles WLAN
- Du loggst dich per SSH ein als ganz normaler User (nicht root)

---

## 1) Repo auf den Pi kopieren

Auf deinem Laptop:

```bash
scp -r openclaw-pi pi@<PI-HOST>:~/
```

Oder per `git clone` direkt auf dem Pi.

---

## 2) Bootstrap-Script ausführen

Auf dem Pi:

```bash
cd ~/openclaw-pi
bash setup.sh
```

Das Script läuft **idempotent** — du kannst es jederzeit erneut starten,
fertige Schritte werden übersprungen.

Es erledigt der Reihe nach:

1. Sanity-Check (aarch64 + Pi OS Lite)
2. apt-Update + Base-Pakete + `unattended-upgrades`
3. 2 GB Swapfile + `vm.swappiness=10`
4. Node.js 24 via NodeSource
5. npm-global-Prefix auf `~/.npm-global` setzen (kein sudo nötig)
6. **Claude Code CLI** + **OpenClaw** global installieren
7. Pause: du loggst dich mit Claude Max ein (siehe Schritt 3)
8. `~/.openclaw/openclaw.json` aus der Beispiel-Konfig anlegen
9. systemd Drop-in installieren, `loginctl enable-linger`
10. `openclaw onboard --install-daemon` starten

Am Ende bekommst du eine Anleitung für die manuellen Schritte 4–6 unten.

---

## 3) Claude Max Login (einmalig)

Wenn das Script den Browser-Login aufruft:

- `claude` startet und zeigt eine URL.
- Öffne sie auf irgendeinem Gerät und logge dich mit dem Account ein, der
  deine **Claude-Max-Subscription** hält.
- OAuth-Callback → Claude Code speichert die Credentials in `~/.claude/`.
- Im `claude`-Prompt mit `/exit` zurück zum Setup-Script.

OpenClaw greift bei jedem Inferenz-Call auf diese Credentials zurück. Der
OAuth-Token wird automatisch refreshed — kein manuelles Nachziehen nötig.

> **Wichtig:** Bei der `openclaw onboard`-Frage nach dem Provider wählst du
> **Claude CLI** (nicht "Anthropic API key"). Das ist der Pfad, der die
> Max-Subscription nutzt.

---

## 4) Telegram-Bot via BotFather

In der Telegram-App:

1. Suche `@BotFather` und starte einen Chat.
2. `/newbot` → Name eingeben, dann Username (`...bot`).
3. Du bekommst einen Token in der Form `123456789:AA...`.
4. Lass den Privacy-Mode auf Default (Enabled) — Bot sieht nur DMs und Mentions.

Token in die Datei kippen:

```bash
echo '123456789:AA...DEIN_TOKEN' > ~/.openclaw/secrets/telegram-token
chmod 600 ~/.openclaw/secrets/telegram-token
```

---

## 5) Deine numerische Telegram-User-ID herausfinden

Der sicherste Weg (kein Drittanbieter-Bot):

```bash
openclaw logs --follow
```

In Telegram dann **eine beliebige DM** an deinen frisch erstellten Bot
schicken. Die ID erscheint im Log als `"from": { "id": 123456789, ... }`.
Notiere die Zahl.

(Alternative: `curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq`.)

---

## 6) `openclaw.json` mit deiner ID füllen

```bash
nano ~/.openclaw/openclaw.json
```

Ersetze **alle drei** Vorkommen von `<DEINE_TELEGRAM_ID>` durch deine
numerische ID (ohne Anführungszeichen-Änderungen):

- `channels.telegram.allowFrom`
- `channels.telegram.execApprovals.approvers`
- `commands.ownerAllowFrom` (Format hier: `"telegram:123456789"`)

Speichern, dann:

```bash
systemctl --user restart openclaw
openclaw doctor
openclaw models list --provider anthropic
```

`openclaw doctor` prüft deine Konfig auf Lücken (Allowlist, SSRF-Schutz, ...).
`models list` muss Anthropic-Modelle zeigen — sonst ist der Claude-CLI-Login
nicht erkannt worden.

---

## 7) Erste Telegram-Nachricht

DM an deinen Bot:

```
Hallo, läuft alles?
```

Erwartung: Bot antwortet (gestreamt). Wenn nicht, siehe Troubleshooting.

Skill-Tests:

| Was tippen | Was passiert |
| --- | --- |
| `/help` | Native-Command-Menü erscheint |
| `Suche im Web nach Postgres 17 highlights` | `browser`-Skill liefert Markdown-Antwort |
| `Erinnere mich morgen 9 Uhr daran, X zu tun` | `cron`-Skill bestätigt |
| `Liste die Inhalte von /etc/hostname` | Approval-Button erscheint, du bestätigst, Bot antwortet |

---

## 8) Reboot-Test

```bash
sudo reboot
```

Nach dem Boot **ohne erneuten Login** eine DM an den Bot schicken — er muss
antworten. Wenn nicht, läuft `loginctl enable-linger` nicht (dann nochmal
`sudo loginctl enable-linger $USER`).

---

## Sicherheits-Defaults (in `openclaw.json.example` schon drin)

| Setting | Effekt |
| --- | --- |
| `dmPolicy: "allowlist"` + numerische `allowFrom` | Nur deine Telegram-ID darf den Bot DM-en. Keine Pairing-Codes für Fremde. |
| `groupPolicy: "disabled"` | Bot ignoriert jede Gruppen-Einladung. |
| `tokenFile` statt `botToken` inline | Bot-Token nicht in JSON; Datei `chmod 600`. |
| `execApprovals.enabled: true` | Jeder Shell-Befehl erfordert Inline-Button-Bestätigung in Telegram. |
| `agents.defaults.sandbox.mode: "non-main"` | Tool-Calls in isoliertem Prozess. |
| systemd `ProtectHome=read-only`, `ReadWritePaths=%h/.openclaw` | Service kann nur in OpenClaw-Daten schreiben. |
| `unattended-upgrades` | OS-Security-Patches automatisch. |

Optional zusätzlich:

- `ufw` mit Default-Deny und nur SSH offen — der Bot braucht keinen Inbound.
- SSH-Key-only (`PasswordAuthentication no` in `/etc/ssh/sshd_config`).
- `fail2ban` falls SSH offen am Internet hängt.

---

## Skills & Modelle

Siehe **[skills/coding-devops.md](skills/coding-devops.md)** für die
empfohlenen Built-ins (`browser`, `cron`, `sessions`, `canvas`, `nodes`)
und ClawHub-Add-ons (`git-tools`, `http-fetch`, `rss-reader`, ...).

Default-Modelle in der Konfig:

- **Primär:** `anthropic/claude-sonnet-4-6` — schnell, deckt 90 % der Anfragen
- **Fallback:** `anthropic/claude-opus-4-7` — bei Fehlschlag oder mit `/model opus` erzwingbar

---

## Updates

```bash
# Alles aktualisieren
sudo apt-get update && sudo apt-get full-upgrade -y
npm update -g @anthropic-ai/claude-code openclaw
systemctl --user restart openclaw
openclaw doctor
```

`unattended-upgrades` kümmert sich um OS-Security-Patches im Hintergrund.

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Bot antwortet nicht in Telegram | `systemctl --user status openclaw`, `openclaw logs --follow` |
| `models list` zeigt keine Anthropic-Modelle | `~/.claude` existiert? `claude --version`? Ggf. `claude /login` neu. |
| `openclaw doctor` warnt vor "@username" in Allowlist | Nur numerische IDs nutzen. `openclaw doctor --fix`. |
| OAuth-Token läuft ab | Sollte automatisch refreshed werden. Falls nicht: `claude /login` neu. |
| Service startet nach Reboot nicht | `loginctl enable-linger $USER` (wieder)setzen. |
| Hohe Latenz / Out-of-memory | Pi-Modell mit 4 GB RAM — Sonnet als Primär lassen, Opus nur on-demand. |
| Telegram-Privacy-Mode-Fragen | Default reicht für DM-only-Setup. Nur ändern, wenn du Gruppen aktivieren willst. |

---

## Was bewusst NICHT drin ist

- **Docker-Sandbox** — auf einem Pi 4 zu schwer; Process-Isolation reicht.
- **Webhook-Mode für Telegram** — Long-Polling spart Reverse-Proxy + TLS-Cert + offenen Port.
- **Andere Channels (Discord, Slack, ...)** — du kannst sie jederzeit in `openclaw.json` ergänzen.
- **Voice/Whisper** — kostet auf Pi 4 zu viel CPU.

Bei Fragen siehe [OpenClaw-Doku](https://docs.openclaw.ai/) und
[GitHub-Repo](https://github.com/openclaw/openclaw).
