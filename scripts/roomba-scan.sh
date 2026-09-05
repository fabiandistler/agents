#!/usr/bin/env bash
# roomba-scan.sh - deterministische Vorstufe fuer die Katalog-Jobs mit Werkzeugunterbau.
#
# Zweck: Rohbefunde erzeugen, damit der Agent NUR die Rest-Frage beantwortet
# (Breaking-Change-Risiko, Export wirklich tot, Nichtdeterminismus Absicht?).
#
# Nicht enthalten: Secrets, Injection, ungenutzte lokale Variablen und Imports.
# Die gehoeren ins CI-Gate (gitleaks/semgrep/bandit, ruff F401, lintr), weil sie
# abschliessend maschinell entscheidbar sind. Siehe assets/ci/.
#
# Quelle: Prompt-Idee Fabian Distler, 2026-09-01, via Skill `idee-zu-artefakt`.
# Gehoert zu: Plugin `roomba`, Skill `roomba-run`, Katalog ROOMBA.md.
#
# Aufruf:  scripts/roomba-scan.sh <deps-audit|dead-exports|test-flakiness>

set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: $0 <deps-audit|dead-exports|test-flakiness>" >&2; exit 2; }

has() { command -v "$1" >/dev/null 2>&1; }
is_r_pkg()  { [ -f DESCRIPTION ]; }
is_python() { [ -f pyproject.toml ] || [ -f requirements.txt ]; }
hdr() { printf '\n===== %s =====\n' "$1"; }
skip() { printf '[uebersprungen] %s\n' "$1"; }

case "$JOB" in

deps-audit)
  if is_r_pkg; then
    if [ -f renv.lock ] && has Rscript; then
      hdr "R: renv::vulns(lockfile = renv.lock)  [Posit PM Vulnerability API]"
      Rscript -e 'if (!requireNamespace("renv", quietly = TRUE) || !requireNamespace("curl", quietly = TRUE)) {
                    cat("renv oder curl nicht installiert\n"); quit(status = 0)
                  }
                  res <- try(renv::vulns(lockfile = "renv.lock"), silent = TRUE)
                  if (inherits(res, "try-error")) {
                    cat("renv::vulns() fehlgeschlagen:", conditionMessage(attr(res, "condition")), "\n"); quit(status = 0)
                  }
                  hit <- Filter(function(p) length(p$vulns) > 0L, res)
                  if (!length(hit)) cat("keine bekannten Vulnerabilities\n") else str(hit, max.level = 3)'
    else
      skip "renv.lock oder Rscript fehlt -> renv::vulns()"
    fi

    if has Rscript; then
      hdr "R: oysteR::audit_description()  [Sonatype OSS Index]"
      Rscript -e 'if (!requireNamespace("oysteR", quietly = TRUE)) { cat("oysteR nicht installiert\n"); quit(status = 0) }
                  res <- try(oysteR::audit_description(dir = "."), silent = TRUE)
                  if (inherits(res, "try-error")) cat("oysteR fehlgeschlagen\n") else print(res)'

      hdr "R: veraltete Pakete (old.packages)"
      Rscript -e 'op <- old.packages(); if (is.null(op)) cat("keine\n") else print(op[, c("Package","Installed","ReposVer"), drop = FALSE])'
    fi
  fi

  if is_python; then
    hdr "Python: veraltete Pakete (uv)"
    if has uv; then uv pip list --outdated 2>&1 || skip "uv pip list --outdated"; else skip "uv nicht installiert"; fi

    hdr "Python: Vulnerabilities (pip-audit)"
    if has uvx; then uvx pip-audit 2>&1 || true; else skip "uvx nicht verfuegbar -> pip-audit"; fi
  fi

  hdr "Changelog-Quellen fuer die Risikobewertung"
  echo "Pro Kandidat NEWS.md / CHANGELOG / Release Notes lesen und im Report zitieren."
  echo "Aufrufstellen im Repo finden: git grep -n <paketname>"

  hdr "Automatisierbarkeit"
  if [ -f renovate.json ] || [ -f .github/renovate.json ] || [ -f .github/dependabot.yml ]; then
    echo "Renovate/Dependabot ist konfiguriert - der Update-Teil gehoert dorthin."
  else
    echo "Weder Renovate noch Dependabot konfiguriert. Empfehlung in den Report aufnehmen:"
    echo "der reine Update-Teil gehoert dorthin, nicht in einen Agentenlauf."
  fi
  ;;

dead-exports)
  echo "Hinweis: lokale ungenutzte Variablen und Imports sind Sache des CI-Gates."
  echo "Dieser Job behandelt nur Exporte ueber die Paketgrenze."

  if is_r_pkg && has Rscript; then
    hdr "R: exportierte Objekte ohne Referenz ausserhalb von R/ (KANDIDATEN, kein Beweis)"
    Rscript -e 'if (!file.exists("NAMESPACE")) { cat("kein NAMESPACE\n"); quit(status = 0) }
                ns <- readLines("NAMESPACE", warn = FALSE)
                ex <- sub("^export\\((.*)\\)$", "\\1", grep("^export\\(", ns, value = TRUE))
                ex <- gsub("[\"`]", "", ex)
                dirs <- c("tests", "vignettes", "inst", "man", "demo")
                dirs <- dirs[dir.exists(dirs)]
                paths <- if (length(dirs)) list.files(dirs, recursive = TRUE, full.names = TRUE) else character()
                txt <- if (length(paths)) unlist(lapply(paths, readLines, warn = FALSE)) else character()
                cand <- ex[!vapply(ex, function(f) any(grepl(f, txt, fixed = TRUE)), logical(1))]
                if (!length(cand)) cat("keine\n") else cat(paste0("- ", cand, collapse = "\n"), "\n")'
  fi

  if is_python; then
    hdr "Python: vulture (min-confidence 80, KANDIDATEN)"
    if has uvx; then uvx vulture . --min-confidence 80 2>&1 || true; else skip "uvx -> vulture"; fi

    hdr "Python: __all__-Eintraege ohne Referenz ausserhalb des Moduls"
    if has uvx; then uvx ruff check --select F822 . 2>&1 || true; else skip "uvx -> ruff F822"; fi
  fi

  hdr "Pflichtbelege je Streichung"
  cat <<'NOTE'
- git grep -n <name>                 (ganzes Repo)
- NAMESPACE / __all__ / re-exports
- Vignetten, Tests, inst/, Beispiele
- Reverse-Dependencies bzw. Konsumenten-Repos
- git log -S<name>                   (kuerzlich hinzugefuegt = vermutlich Absicht)
- dynamische Aufrufe: do.call, getExportedValue, match.fun, getattr, Registry-Muster
NOTE
  ;;

test-flakiness)
  TDIRS=""
  for d in tests test; do [ -d "$d" ] && TDIRS="$TDIRS $d"; done
  if [ -z "$TDIRS" ]; then echo "kein tests/ oder test/ Verzeichnis gefunden"; exit 0; fi

  hdr "Kandidaten: Zeitabhaengigkeit"
  grep -rnE 'Sys\.time|Sys\.Date|datetime\.now|time\.time|date\.today' $TDIRS 2>/dev/null || echo "keine"

  hdr "Kandidaten: Zufall"
  grep -rnE '\b(sample|runif|rnorm|rbinom|random\.|np\.random|uuid4)\b' $TDIRS 2>/dev/null || echo "keine"
  echo "--- Gegenprobe: gesetzte Seeds ---"
  grep -rnE 'set\.seed|local_seed|random\.seed|seed *=' $TDIRS 2>/dev/null || echo "keine"

  hdr "Kandidaten: Netzabhaengigkeit"
  grep -rnE 'https?://|httr|curl|requests\.|urllib|httpx' $TDIRS 2>/dev/null || echo "keine"
  echo "--- Gegenprobe: Mocking/Fixtures ---"
  grep -rnE 'httptest|vcr|webmock|responses|respx|mock' $TDIRS 2>/dev/null || echo "keine"

  hdr "Kandidaten: Sleep / Timing"
  grep -rnE 'Sys\.sleep|time\.sleep' $TDIRS 2>/dev/null || echo "keine"

  hdr "Regel fuer den Fix"
  echo "Nur die Quelle des Nichtdeterminismus ersetzen (withr::local_seed, Fixtures, Mocks)."
  echo "Assertions bleiben unveraendert. Ein Test, der danach anders prueft, ist kein Fix."
  ;;

*)
  echo "Unbekannter Job: $JOB" >&2
  echo "security-footguns und dead-code(lokal) laufen im CI-Gate, nicht hier." >&2
  exit 2
  ;;
esac
