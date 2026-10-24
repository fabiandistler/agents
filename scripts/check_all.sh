#!/usr/bin/env bash
# The single list of this repo's CI checks. CI (.github/workflows/ci.yml) calls
# this script, and README.md / MAINTENANCE.md point here, so a new gate is
# added once, below, and nowhere else. Tool pins live in
# scripts/check_all.requirements.txt (pip) and .pre-commit-config.yaml (prek).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
# Pinned browserless Mermaid validator; mermaid is pinned next to mmdlint
# because mmdlint itself only asks for ^11.
MMDLINT="npx -y -p @sysid/mmdlint@0.1.1 -p mermaid@11.17.0 mmdlint"

# Order matters: the catalogue and plugin checks read skills.json, so the
# manifest check runs first.
CHECKS=(manifest routers descriptions docs plugins instructions python-baseline project-claude
  frontmatter evals vocab gh-graphql skill-refs reference-tocs dated-claims skill-paths secret-argv pytest prek
  compileall install-smoke mermaid)

usage() {
  cat <<'EOF'
Usage: scripts/check_all.sh [--only A,B] [--skip A,B] [--tail N] [--output FILE] [--list]
Runs every CI check from the repo root; one PASS/FAIL/MISSING line per check.
  --only A,B     run only these checks (names from --list)
  --skip A,B     run all checks except these
  --tail N       lines of a failing check's output to show (default 40, 0 = all)
  --output FILE  also write every check's full output to FILE
  --list         print the check names with the tools each needs, then exit
  -h, --help     show this help
Env: PYTHON (default python3, must be 3.11 or newer). The prek check runs ruff, ty, shellcheck, shfmt
and the secret scan at the versions pinned in .pre-commit-config.yaml; its
hooks may rewrite files (ruff --fix, shfmt, whitespace).
Exit: 0 all passed, 1 a check failed, 2 usage error,
      3 nothing failed but a check could not run (tool missing),
      4 PYTHON is missing or older than 3.11.
Examples:
  scripts/check_all.sh
  scripts/check_all.sh --only prek,pytest --tail 0
EOF
}

# Tools a check needs; "pyyaml" and "pytest" are Python modules of $PY.
needs() {
  case "$1" in
    frontmatter) echo "$PY pyyaml" ;;
    pytest) echo "$PY pytest pyyaml" ;;
    prek) echo "prek" ;;
    install-smoke) echo "bash $PY" ;;
    mermaid) echo "npx" ;;
    *) echo "$PY" ;;
  esac
}

have() {
  case "$1" in
    pyyaml) "$PY" -c 'import yaml' 2>/dev/null ;;
    pytest) "$PY" -c 'import pytest' 2>/dev/null ;;
    *) command -v "$1" >/dev/null 2>&1 ;;
  esac
}

run_check() {
  case "$1" in
    manifest) "$PY" scripts/build_manifest.py --check ;;
    routers) "$PY" scripts/build_routers.py --check ;;
    descriptions) "$PY" scripts/check_descriptions.py ;;
    docs) "$PY" scripts/check_docs.py ;;
    plugins) "$PY" scripts/check_plugins.py ;;
    instructions) "$PY" scripts/check_instructions.py ;;
    python-baseline) "$PY" scripts/check_python_baseline.py ;;
    project-claude) "$PY" scripts/build_project_claude.py --check ;;
    frontmatter)
      # Running the validator, not just compiling it, proves its allowlist
      # still matches the frontmatter this repo ships.
      local d fail=0
      for d in skills/*/; do
        [ -f "${d}SKILL.md" ] || continue
        "$PY" scripts/quick_validate.py "$d" >/dev/null 2>&1 || {
          echo "${d}SKILL.md: $("$PY" scripts/quick_validate.py "$d" 2>&1)"
          fail=1
        }
      done
      return $fail
      ;;
    evals) "$PY" scripts/check_evals.py --strict ;;
    vocab) "$PY" scripts/check_skill_vocab.py ;;
    gh-graphql) "$PY" scripts/check_gh_graphql.py ;;
    skill-refs) "$PY" scripts/check_skill_refs.py ;;
    reference-tocs) "$PY" scripts/check_reference_tocs.py ;;
    dated-claims) "$PY" scripts/check_dated_claims.py ;;
    skill-paths) "$PY" scripts/check_skill_paths.py ;;
    secret-argv) "$PY" scripts/check_secret_argv.py ;;
    # Every test_*.py under scripts/ and skills/; naming one file left the
    # other skills' tests unrun.
    pytest) "$PY" -m pytest -q scripts skills ;;
    prek) prek run --all-files --show-diff-on-failure ;;
    compileall) "$PY" -m compileall -q scripts skills ;;
    install-smoke) bash scripts/test_install.sh ;;
    mermaid)
      # Prove the guard can go red first; a validator that parses nothing
      # would otherwise pass forever.
      $MMDLINT scripts/fixtures/mermaid/valid.md || return 1
      if $MMDLINT scripts/fixtures/mermaid/broken.md; then
        echo "mmdlint accepted scripts/fixtures/mermaid/broken.md"
        return 1
      fi
      git ls-files -z '*.md' '*.markdown' ':!:scripts/fixtures/' | xargs -0 -r $MMDLINT
      ;;
  esac
}

only="" skip="" tail_n=40 output=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only)
      only="${2:-}"
      shift 2 || {
        usage >&2
        exit 2
      }
      ;;
    --skip)
      skip="${2:-}"
      shift 2 || {
        usage >&2
        exit 2
      }
      ;;
    --tail)
      tail_n="${2:-}"
      shift 2 || {
        usage >&2
        exit 2
      }
      ;;
    --output)
      output="${2:-}"
      shift 2 || {
        usage >&2
        exit 2
      }
      ;;
    --list)
      for c in "${CHECKS[@]}"; do printf '%s\t%s\n' "$c" "$(needs "$c")"; done
      exit 0
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$tail_n" in '' | *[!0-9]*)
  echo "--tail needs a number, got: $tail_n" >&2
  exit 2
  ;;
esac
for name in ${only//,/ } ${skip//,/ }; do
  case " ${CHECKS[*]} " in *" $name "*) ;; *)
    echo "unknown check: $name (allowed: ${CHECKS[*]})" >&2
    exit 2
    ;;
  esac
done

selected() {
  if [ -n "$only" ]; then case ",$only," in *",$1,"*) ;; *) return 1 ;; esac fi
  case ",$skip," in *",$1,"*) return 1 ;; esac
}

cd "$REPO_ROOT" || exit 2

# Stop before the first check on an old interpreter; a pre-push run with the
# system python3 would otherwise end in MISSING lines or tomllib tracebacks.
# shellcheck source=scripts/require_python.sh
. scripts/require_python.sh
for name in "${CHECKS[@]}"; do
  selected "$name" || continue
  case " $(needs "$name") " in *" $PY "*)
    require_python check_all.sh "$PY" || exit 4
    break
    ;;
  esac
done

if [ -n "$output" ]; then : >"$output" || exit 2; fi
log="$(mktemp)"
trap 'rm -f "$log"' EXIT

failed=() missing=()
for name in "${CHECKS[@]}"; do
  selected "$name" || continue

  absent=""
  for tool in $(needs "$name"); do have "$tool" || absent="$absent $tool"; done
  if [ -n "$absent" ]; then
    case "$absent" in
      *npx*) fix="install Node.js (provides npx)" ;;
      *) fix="pip install -r scripts/check_all.requirements.txt" ;;
    esac
    echo "MISSING $name: not installed:$absent ($fix)"
    missing+=("$name")
    continue
  fi

  start=$SECONDS
  run_check "$name" >"$log" 2>&1
  status=$?
  if [ -n "$output" ]; then
    {
      echo "===== $name (exit $status)"
      cat "$log"
    } >>"$output"
  fi
  if [ $status -eq 0 ]; then
    echo "PASS $name ($((SECONDS - start))s)"
  else
    echo "FAIL $name (exit $status)"
    if [ "$tail_n" -eq 0 ]; then sed 's/^/  | /' "$log"; else tail -n "$tail_n" "$log" | sed 's/^/  | /'; fi
    failed+=("$name")
  fi
done

echo "summary: ${#failed[@]} failed${failed[*]:+ (${failed[*]})}, ${#missing[@]} missing${missing[*]:+ (${missing[*]})}"
[ ${#failed[@]} -gt 0 ] && exit 1
[ ${#missing[@]} -gt 0 ] && exit 3
exit 0
