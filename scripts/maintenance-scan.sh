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
# Invocation, flags and exit codes: usage() below, or --help.

set -uo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/maintenance-scan.sh <deps-audit|dead-exports|test-flakiness>
Deterministic scanner for the catalog jobs that have tool support. Produces
raw findings so the agent answers only the open question (breaking-change
risk, export really dead, nondeterminism intentional?). Works in any
directory inside the target repo.
  deps-audit      vulnerable or outdated dependencies (renv::vulns, OSV CRAN, uv, pip-audit)
  dead-exports    exports with no reference outside the package (NAMESPACE, __all__)
  test-flakiness  time, randomness, network candidates in tests/ or test/
  -h, --help      this text
Examples:
  scripts/maintenance-scan.sh deps-audit
  scripts/maintenance-scan.sh test-flakiness
Exit codes:
  0  scan ran; test-flakiness without tests/ or test/ notes the skip on stderr, and
     deps-audit without DESCRIPTION, pyproject.toml or requirements.txt notes the
     skipped package audit on stdout
  2  usage error: no or unknown job
  3  environment: not a Git repo, or dead-exports without DESCRIPTION, pyproject.toml
     or requirements.txt
  6  blocked: a required tool is missing or a data source is unreachable (HTTP 403/5xx,
     DNS, proxy); the other checks ran, each blocked one is a [blocked] line on stdout,
     and stderr lists them
Plugin-wide exit code table: "## Exit codes" in plugins/repo-maintenance/README.md
(repo fabiandistler/repo-maintenance).
EOF
}

JOB="${1:-}"
case "$JOB" in
  -h | --help)
    usage
    exit 0
    ;;
  "")
    echo "No job given. Run with --help." >&2
    exit 2
    ;;
  deps-audit | dead-exports | test-flakiness)
    ;;
  *)
    echo "Unknown job: $JOB (see --help)" >&2
    echo "security-footguns and dead-code (local) run in the CI gate, not here." >&2
    exit 2
    ;;
esac

# Sibling scripts (maintenance-r-advisories.py), resolved before the cd below.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Not a Git repository." >&2
  exit 3
}
cd "$ROOT" || exit 3

has() { command -v "$1" >/dev/null 2>&1; }
is_r_pkg() { [ -f DESCRIPTION ]; }
is_python() { [ -f pyproject.toml ] || [ -f requirements.txt ]; }
hdr() { printf '\n===== %s =====\n' "$1"; }
skip() { printf '[skipped] %s\n' "$1"; }

# blocked CHECK REASON - this environment cannot run CHECK: a required tool is missing
# or a data source is unreachable (#83). The scan goes on and exits 6 at the end (#96).
BLOCKED=()
blocked() {
  printf '[blocked] %s: %s\n' "$1" "$2"
  BLOCKED+=("$1: $2")
}

case "$JOB" in

  deps-audit)
    # The changelog note and the Renovate/Dependabot check below need no package.
    if ! is_r_pkg && ! is_python; then
      skip "no DESCRIPTION, pyproject.toml or requirements.txt -> R and Python package audit"
    fi

    if is_r_pkg; then
      if [ -f renv.lock ] && has Rscript; then
        hdr "R: renv::vulns(lockfile = renv.lock)  [Posit PM Vulnerability API]"
        Rscript -e 'if (!requireNamespace("renv", quietly = TRUE) || !requireNamespace("curl", quietly = TRUE)) {
                    cat("renv or curl not installed\n"); quit(status = 3)
                  }
                  res <- try(renv::vulns(lockfile = "renv.lock"), silent = TRUE)
                  if (inherits(res, "try-error")) {
                    cat("renv::vulns() failed:", conditionMessage(attr(res, "condition")), "\n"); quit(status = 6)
                  }
                  hit <- Filter(function(p) length(p$vulns) > 0L, res)
                  if (!length(hit)) cat("no known vulnerabilities\n") else str(hit, max.level = 3)'
        case $? in
          3) blocked "renv::vulns()" "tool missing - R package renv or curl" ;;
          6) blocked "renv::vulns()" "unreachable - Posit PM Vulnerability API (renv::vulns() error above)" ;;
        esac
      elif [ -f renv.lock ]; then
        blocked "renv::vulns()" "tool missing - Rscript"
      else
        skip "no renv.lock -> renv::vulns()"
      fi

      # Needs neither R nor renv.lock: DESCRIPTION constraints against the OSV dump.
      hdr "R: DESCRIPTION constraints vs. OSV CRAN advisories  [R Consortium advisory database]"
      if has python3 && [ -f "$SCRIPT_DIR/maintenance-r-advisories.py" ] && [ -f "$SCRIPT_DIR/maintenance-new-deps.py" ]; then
        python3 "$SCRIPT_DIR/maintenance-r-advisories.py" 2>&1
        # Exit 3 (dump unreadable) is printed above as "not checked", not blocked.
        case $? in
          6) blocked "OSV CRAN advisories" "unreachable - OSV CRAN dump (error above)" ;;
        esac
      elif has python3; then
        blocked "OSV CRAN advisories" "tool missing - maintenance-r-advisories.py or maintenance-new-deps.py next to the scanner"
      else
        blocked "OSV CRAN advisories" "tool missing - python3"
      fi

      if has Rscript; then
        hdr "R: outdated packages (old.packages)"
        # No package index from any repository would read as "none" outdated.
        Rscript -e 'ap <- available.packages()
                  if (!nrow(ap)) { cat("no package index from any repository in getOption(\"repos\")\n"); quit(status = 6) }
                  op <- old.packages(available = ap); if (is.null(op)) cat("none\n") else print(op[, c("Package","Installed","ReposVer"), drop = FALSE])' ||
          blocked "old.packages()" "unreachable - CRAN mirror, or none set in the repos option (R message above)"
      else
        blocked "old.packages()" "tool missing - Rscript"
      fi
    fi

    if is_python; then
      hdr "Python: outdated packages (uv)"
      if has uv; then uv pip list --outdated 2>&1 || skip "uv pip list --outdated"; else blocked "uv pip list --outdated" "tool missing - uv"; fi

      hdr "Python: Vulnerabilities"
      if [ -f uv.lock ] && [ -f .github/workflows/maintenance-deps-audit.yml ]; then
        echo "Scanned in CI (uv audit, workflow maintenance-deps-audit). Triage its latest"
        echo "weekly report: artifact 'uv-audit' of the last scheduled run."
        if has gh; then
          gh run list --workflow maintenance-deps-audit.yml --event schedule --limit 1 2>&1 || true
        fi
      elif [ -f uv.lock ] && has uv; then
        uv audit --locked --preview-features audit-command 2>&1
        # Exit 1 means findings, printed above. uv exits 2 on any error: an OSV or index
        # failure, but also a stale uv.lock under --locked - the error above names which.
        case $? in
          2) blocked "uv audit" "unreachable - OSV or package index (uv exit 2, error above; a stale uv.lock exits 2 too)" ;;
        esac
      elif [ -f requirements.txt ] && has uvx; then
        uvx pip-audit -r requirements.txt 2>&1 || true
      elif [ -f uv.lock ]; then
        blocked "uv audit" "tool missing - uv"
      elif [ -f requirements.txt ]; then
        blocked "pip-audit" "tool missing - uvx"
      else
        skip "no uv.lock or requirements.txt -> vulnerability scan"
      fi
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
    # Exports are NAMESPACE or __all__ entries: without an R or Python package there are none.
    if ! is_r_pkg && ! is_python; then
      echo "No DESCRIPTION, pyproject.toml or requirements.txt found. Nothing to scan." >&2
      exit 3
    fi

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
    if is_r_pkg && ! has Rscript; then blocked "R exports" "tool missing - Rscript"; fi

    if is_python; then
      hdr "Python: vulture (min-confidence 80, CANDIDATES)"
      if has uvx; then uvx vulture . --min-confidence 80 2>&1 || true; else blocked "vulture" "tool missing - uvx"; fi

      hdr "Python: __all__ entries with no reference outside the module"
      if has uvx; then uvx ruff check --select F822 . 2>&1 || true; else blocked "ruff F822" "tool missing - uvx"; fi
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
    tdirs=()
    for d in tests test; do [ -d "$d" ] && tdirs+=("$d"); done
    if [ "${#tdirs[@]}" -eq 0 ]; then
      skip "no tests/ or test/ directory -> flakiness scan" >&2
      exit 0
    fi

    # Vendored Bats libraries (submodules under test/bats/ from the prek-hooks
    # Bats fragment, or test/test_helper/) are not the repo's tests (#73).
    vendored_excludes=(--exclude-dir=bats-core --exclude-dir=bats-assert --exclude-dir=bats-support)

    hdr "Candidates: time dependency"
    grep -rnE "${vendored_excludes[@]}" 'Sys\.time|Sys\.Date|datetime\.now|time\.time|date\.today' "${tdirs[@]}" 2>/dev/null || echo "none"

    hdr "Candidates: randomness"
    grep -rnE "${vendored_excludes[@]}" '\b(sample|runif|rnorm|rbinom|random\.|np\.random|uuid4|import[[:space:]]+random)\b' "${tdirs[@]}" 2>/dev/null || echo "none"
    echo "--- Cross-check: seeds that are set ---"
    grep -rnE "${vendored_excludes[@]}" 'set\.seed|local_seed|random\.seed|seed *=' "${tdirs[@]}" 2>/dev/null || echo "none"

    hdr "Candidates: network dependency"
    grep -rnE "${vendored_excludes[@]}" 'https?://|httr|curl|requests\.|urllib|httpx' "${tdirs[@]}" 2>/dev/null || echo "none"
    echo "--- Cross-check: mocking/fixtures ---"
    grep -rnE "${vendored_excludes[@]}" 'httptest|vcr|webmock|responses|respx|mock' "${tdirs[@]}" 2>/dev/null || echo "none"

    hdr "Candidates: sleep / timing"
    grep -rnE "${vendored_excludes[@]}" 'Sys\.sleep|time\.sleep' "${tdirs[@]}" 2>/dev/null || echo "none"

    hdr "Rule for the fix"
    echo "Replace only the source of nondeterminism (withr::local_seed, fixtures, mocks)."
    echo "Assertions stay unchanged. A test that checks something different afterwards is not a fix."
    ;;
esac

if [ "${#BLOCKED[@]}" -gt 0 ]; then
  echo "Blocked: ${#BLOCKED[@]} check(s) could not run in this environment (exit 6):" >&2
  printf '  %s\n' "${BLOCKED[@]}" >&2
  exit 6
fi
