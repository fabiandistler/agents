#!/usr/bin/env bash
# setup-hooks.sh — richtet prek-Hooks in einem Repo ein (Python und/oder R).
#
# Aufruf aus einem beliebigen Verzeichnis des Ziel-Repos:
#   /pfad/zu/setup-hooks.sh [--builtin] [--force]
#
#   --builtin  generische Hooks als prek-builtins statt ueber pre-commit-hooks.
#              Schneller und ohne Python-Env, aber die Config ist dann
#              nicht mehr mit dem originalen pre-commit lauffaehig.
#   --force    vorhandene .pre-commit-config.yaml ueberschreiben.
#
# Herkunft: Forge-Durchgang 09.09.2026, Rohmaterial https://prek.j178.dev/
# Entscheidungen: air statt styler (Formatierung ohne R-Runtime), lintr
# zusaetzlich (braucht System-R), ruff + ty auf der Python-Seite.
#
# Closed loop:
#   Messung:   Existiert .git/hooks/pre-commit in den Repos, und meldet prek
#              beim Commit reale Funde ("files were modified by this hook")?
#   Latenz:    sofort, bei jedem Commit.
#   Kriterium: nach 4 Wochen in >=2 Repos aktiv, mindestens 1 realer Fund.
#   Anpassung: kein Fund -> Hookset kuerzen. Skript nie ein zweites Mal
#              benutzt -> auf reine Templates zurueckstufen. lintr zu langsam
#              -> stages: [pre-push].
#   Review:    07.10.2026

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAGMENTS="${SCRIPT_DIR}/fragments"
BASE="base-compat.yaml"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --builtin) BASE="base-builtin.yaml"; shift ;;
    --force)   FORCE=1; shift ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unbekanntes Argument: $1" >&2; exit 2 ;;
  esac
done

[[ -d "$FRAGMENTS" ]] || { echo "Fragmente nicht gefunden: $FRAGMENTS" >&2; exit 1; }

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Kein Git-Repository. Abbruch." >&2; exit 1; }
cd "$ROOT"

command -v prek >/dev/null 2>&1 || {
  echo "prek nicht im PATH. Installation z.B.: uv tool install prek" >&2; exit 1; }

CONFIG=".pre-commit-config.yaml"
if [[ -e "$CONFIG" && $FORCE -eq 0 ]]; then
  echo "$CONFIG existiert bereits. Mit --force ueberschreiben." >&2; exit 1
fi
if [[ -e "prek.toml" && $FORCE -eq 0 ]]; then
  echo "prek.toml existiert bereits — prek wuerde die YAML ignorieren." >&2; exit 1
fi

has_python=0
has_r=0
[[ -f pyproject.toml || -f setup.py ]] && has_python=1
[[ -n "$(git ls-files -- '*.py' | head -n1)" ]] && has_python=1
[[ -f DESCRIPTION ]] && has_r=1
[[ -n "$(git ls-files -- '*.R' '*.r' | head -n1)" ]] && has_r=1

if [[ $has_python -eq 0 && $has_r -eq 0 ]]; then
  echo "Weder Python- noch R-Dateien gefunden. Nichts einzurichten." >&2; exit 1
fi

if [[ $has_r -eq 1 ]] && ! command -v Rscript >/dev/null 2>&1; then
  echo "WARNUNG: Rscript fehlt — der lintr-Hook wird beim Lauf scheitern." >&2
fi

{
  echo "# Erzeugt von setup-hooks.sh am $(date +%F). Runner: prek."
  echo "# Revs anschliessend mit 'prek update --cooldown-days 7' aktualisieren."
  cat "${FRAGMENTS}/${BASE}"
  [[ $has_python -eq 1 ]] && cat "${FRAGMENTS}/python.yaml"
  [[ $has_r -eq 1 ]] && cat "${FRAGMENTS}/r.yaml"
} > "$CONFIG"

echo "Geschrieben: ${ROOT}/${CONFIG} (python=${has_python}, r=${has_r}, base=${BASE})"

if ! prek update --cooldown-days 7; then
  echo "WARNUNG: 'prek update' fehlgeschlagen — Revs bleiben auf den" >&2
  echo "         Werten aus den Fragmenten und sind moeglicherweise alt." >&2
fi

prek install

cat <<'EOF'

Naechster Schritt, bewusst nicht automatisch ausgefuehrt:

  prek run --all-files

Der erste Lauf formatiert das gesamte Repo und erzeugt einen grossen Diff.
Das gehoert in einen eigenen Commit, nicht in den naechsten fachlichen.
EOF
