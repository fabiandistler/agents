#!/usr/bin/env bash
# maintenance-scan.sh - deterministic scanner for the catalog jobs that have tool support.
#
# Purpose: produce raw findings so the agent answers ONLY the open question
# (breaking-change risk, export really dead, nondeterminism intentional?).
#
# Not included: secrets, injection, unused local variables and imports.
# Those belong in the CI gate (gitleaks, ruff, bandit, lintr) because a machine
# can decide them conclusively. See assets/ci/.
#
# Source: prompt idea by Fabian Distler, 2026-09-01, via skill `idee-zu-artefakt`.
# Part of: plugin `repo-maintenance`, skill `maintenance-run`, catalog MAINTENANCE.md.
#
# Usage:   scripts/maintenance-scan.sh <deps-audit|dead-exports|test-flakiness>

set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: $0 <deps-audit|dead-exports|test-flakiness>" >&2; exit 2; }

has() { command -v "$1" >/dev/null 2>&1; }
is_r_pkg()  { [ -f DESCRIPTION ]; }
is_python() { [ -f pyproject.toml ] || [ -f requirements.txt ]; }
hdr() { printf '\n===== %s =====\n' "$1"; }
skip() { printf '[skipped] %s\n' "$1"; }

case "$JOB" in

deps-audit)
  if is_r_pkg; then
    if [ -f renv.lock ] && has Rscript; then
      hdr "R: renv::vulns(lockfile = renv.lock)  [Posit PM Vulnerability API]"
      Rscript -e 'if (!requireNamespace("renv", quietly = TRUE) || !requireNamespace("curl", quietly = TRUE)) {
                    cat("renv or curl not installed\n"); quit(status = 0)
                  }
                  res <- try(renv::vulns(lockfile = "renv.lock"), silent = TRUE)
                  if (inherits(res, "try-error")) {
                    cat("renv::vulns() failed:", conditionMessage(attr(res, "condition")), "\n"); quit(status = 0)
                  }
                  hit <- Filter(function(p) length(p$vulns) > 0L, res)
                  if (!length(hit)) cat("no known vulnerabilities\n") else str(hit, max.level = 3)'
    else
      skip "renv.lock or Rscript missing -> renv::vulns()"
    fi

    if has Rscript; then
      hdr "R: oysteR::audit_description()  [Sonatype OSS Index]"
      Rscript -e 'if (!requireNamespace("oysteR", quietly = TRUE)) { cat("oysteR not installed\n"); quit(status = 0) }
                  res <- try(oysteR::audit_description(dir = "."), silent = TRUE)
                  if (inherits(res, "try-error")) cat("oysteR failed\n") else print(res)'

      hdr "R: outdated packages (old.packages)"
      Rscript -e 'op <- old.packages(); if (is.null(op)) cat("none\n") else print(op[, c("Package","Installed","ReposVer"), drop = FALSE])'
    fi
  fi

  if is_python; then
    hdr "Python: outdated packages (uv)"
    if has uv; then uv pip list --outdated 2>&1 || skip "uv pip list --outdated"; else skip "uv not installed"; fi

    hdr "Python: Vulnerabilities (pip-audit)"
    if has uvx; then uvx pip-audit 2>&1 || true; else skip "uvx not available -> pip-audit"; fi
  fi

  hdr "Changelog sources for the risk assessment"
  echo "For each candidate, read NEWS.md / CHANGELOG / release notes and cite them in the report."
  echo "Find call sites in the repo: git grep -n <package-name>"

  hdr "Automation"
  if [ -f renovate.json ] || [ -f .github/renovate.json ] || [ -f .github/dependabot.yml ]; then
    echo "Renovate/Dependabot is configured - the update work belongs there."
  else
    echo "Neither Renovate nor Dependabot is configured. Add a recommendation to the report:"
    echo "the plain update work belongs there, not in an agent run."
  fi
  ;;

dead-exports)
  echo "Note: unused local variables and imports are the CI gate's job."
  echo "This job handles only exports across the package boundary."

  if is_r_pkg && has Rscript; then
    hdr "R: exported objects with no reference outside R/ (CANDIDATES, not proof)"
    Rscript -e 'if (!file.exists("NAMESPACE")) { cat("no NAMESPACE\n"); quit(status = 0) }
                ns <- readLines("NAMESPACE", warn = FALSE)
                ex <- sub("^export\\((.*)\\)$", "\\1", grep("^export\\(", ns, value = TRUE))
                ex <- gsub("[\"`]", "", ex)
                dirs <- c("tests", "vignettes", "inst", "demo")
                dirs <- dirs[dir.exists(dirs)]
                paths <- if (length(dirs)) list.files(dirs, recursive = TRUE, full.names = TRUE) else character()
                txt <- if (length(paths)) unlist(lapply(paths, readLines, warn = FALSE)) else character()
                cand <- ex[!vapply(ex, function(f) any(grepl(f, txt, fixed = TRUE)), logical(1))]
                if (!length(cand)) cat("none\n") else cat(paste0("- ", cand, collapse = "\n"), "\n")'
  fi

  if is_python; then
    hdr "Python: vulture (min-confidence 80, CANDIDATES)"
    if has uvx; then uvx vulture . --min-confidence 80 2>&1 || true; else skip "uvx -> vulture"; fi

    hdr "Python: __all__ entries with no reference outside the module"
    if has uvx; then uvx ruff check --select F822 . 2>&1 || true; else skip "uvx -> ruff F822"; fi
  fi

  hdr "Required evidence per removal"
  cat <<'NOTE'
- git grep -n <name>                 (whole repo)
- NAMESPACE / __all__ / re-exports
- vignettes, tests, inst/, examples
- reverse dependencies or consumer repos
- git log -S<name>                   (recently added = probably intentional)
- dynamic calls: do.call, getExportedValue, match.fun, getattr, registry patterns
NOTE
  ;;

test-flakiness)
  TDIRS=""
  for d in tests test; do [ -d "$d" ] && TDIRS="$TDIRS $d"; done
  if [ -z "$TDIRS" ]; then echo "no tests/ or test/ directory found"; exit 0; fi

  hdr "Candidates: time dependency"
  grep -rnE 'Sys\.time|Sys\.Date|datetime\.now|time\.time|date\.today' $TDIRS 2>/dev/null || echo "none"

  hdr "Candidates: randomness"
  grep -rnE '\b(sample|runif|rnorm|rbinom|random\.|np\.random|uuid4)\b' $TDIRS 2>/dev/null || echo "none"
  echo "--- Cross-check: seeds that are set ---"
  grep -rnE 'set\.seed|local_seed|random\.seed|seed *=' $TDIRS 2>/dev/null || echo "none"

  hdr "Candidates: network dependency"
  grep -rnE 'https?://|httr|curl|requests\.|urllib|httpx' $TDIRS 2>/dev/null || echo "none"
  echo "--- Cross-check: mocking/fixtures ---"
  grep -rnE 'httptest|vcr|webmock|responses|respx|mock' $TDIRS 2>/dev/null || echo "none"

  hdr "Candidates: sleep / timing"
  grep -rnE 'Sys\.sleep|time\.sleep' $TDIRS 2>/dev/null || echo "none"

  hdr "Rule for the fix"
  echo "Replace only the source of nondeterminism (withr::local_seed, fixtures, mocks)."
  echo "Assertions stay unchanged. A test that checks something different afterwards is not a fix."
  ;;

*)
  echo "Unknown job: $JOB" >&2
  echo "security-footguns and dead-code (local) run in the CI gate, not here." >&2
  exit 2
  ;;
esac
