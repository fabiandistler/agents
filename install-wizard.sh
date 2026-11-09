#!/usr/bin/env bash
# Interactive install assistant for humans. It asks for the choices that
# install.sh takes as flags, prints the equivalent non-interactive command,
# offers a dry run, and then runs install.sh with those flags. All selection
# logic stays in install.sh; this script only composes its command line.
#
# Agents never run this: it needs a terminal on stdin and exits 2 without one.
# They call ./install.sh with flags (see ./install.sh --help).
#
# Usage:
#   ./install-wizard.sh
#   ./install-wizard.sh --help
#
# INSTALL_WIZARD_ASSUME_TTY=1 skips the terminal check so the Bats suite
# (test/install_wizard.bats) can script stdin; at end of input the wizard still
# exits 2 instead of waiting.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALLER="$(dirname "$0")/install.sh"

usage() {
  cat <<'EOF'
Usage: ./install-wizard.sh [-h|--help]

Asks for target, environment, categories, instructions and guards, prints the
matching ./install.sh command, offers a dry run, then runs install.sh.
Needs a terminal on stdin. Agents and scripts call ./install.sh with flags.

Exit codes: 2 usage error (no terminal, unknown argument, input ended);
            otherwise the exit code of install.sh (0 when you decline).

Examples:
  ./install-wizard.sh
  ./install.sh --help    # the flag-driven installer this wizard runs
EOF
}

no_terminal() {
  echo "install-wizard.sh needs a terminal on stdin; use the flag-driven installer instead: ./install.sh --target=claude|codex|opencode|all|detected [options] (see ./install.sh --help)" >&2
  exit 2
}

case "${1:-}" in
  "") ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "unknown arg: $1" >&2
    usage >&2
    exit 2
    ;;
esac

if [[ ! -t 0 && "${INSTALL_WIZARD_ASSUME_TTY:-}" != 1 ]]; then
  no_terminal
fi

# detect_targets: the installer's own --target=detected logic.
# shellcheck source=scripts/install/state.sh
source "$REPO_ROOT/scripts/install/state.sh"

# Prompts go to stderr so stdout carries only the command.
ANSWER=""
ask() {
  printf '%s ' "$1" >&2
  if ! IFS= read -r ANSWER; then
    printf '\n' >&2
    no_terminal
  fi
  ANSWER="${ANSWER//[[:space:]]/}"
}

# ask_yes_no PROMPT DEFAULT(y|n): returns 0 for yes.
ask_yes_no() {
  local hint='[y/N]'
  [[ "$2" == y ]] && hint='[Y/n]'
  while true; do
    ask "$1 $hint"
    case "$ANSWER" in
      "") [[ "$2" == y ]] && return 0 || return 1 ;;
      [yY] | [yY][eE][sS]) return 0 ;;
      [nN] | [nN][oO]) return 1 ;;
      *) echo "  answer y or n" >&2 ;;
    esac
  done
}

# Prints the skills' category: values, sorted and unique.
skill_categories() {
  sed -n 's/^category:[[:space:]]*//p' "$REPO_ROOT"/skills/*/SKILL.md |
    tr -d "\"' \t\r" | grep -v '^$' | sort -u
}

choose_target() {
  local detected targets=(claude codex opencode all) i
  detected="$(detect_targets)"
  detected="${detected//$'\n'/, }"
  echo "Target agent:" >&2
  for i in "${!targets[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${targets[i]}" >&2
  done
  if [[ -n "$detected" ]]; then
    targets+=(detected)
    printf '  5) detected (found: %s)\n' "$detected" >&2
  else
    echo "  (detected is not offered: no agent command or config directory found)" >&2
  fi
  while true; do
    ask "Choose 1-${#targets[@]} or a name:"
    for i in "${!targets[@]}"; do
      if [[ "$ANSWER" == "$((i + 1))" || "$ANSWER" == "${targets[i]}" ]]; then
        TARGET="${targets[i]}"
        DETECTED="$detected"
        return 0
      fi
    done
    echo "  not a choice: ${ANSWER:-<empty>}" >&2
  done
}

choose_env() {
  local envs=(all coding chat) i
  echo "Environment (which skills to link):" >&2
  for i in "${!envs[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${envs[i]}" >&2
  done
  while true; do
    ask "Choose 1-3 or a name [all]:"
    [[ -n "$ANSWER" ]] || ANSWER=all
    for i in "${!envs[@]}"; do
      if [[ "$ANSWER" == "$((i + 1))" || "$ANSWER" == "${envs[i]}" ]]; then
        ENV="${envs[i]}"
        return 0
      fi
    done
    echo "  not a choice: $ANSWER" >&2
  done
}

choose_categories() {
  local categories=() picked=() items=() item i ok found
  while IFS= read -r item; do
    categories+=("$item")
  done < <(skill_categories)
  echo "Categories:" >&2
  for i in "${!categories[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${categories[i]}" >&2
  done
  while true; do
    ask "Comma-separated numbers or names, empty for all:"
    if [[ -z "$ANSWER" || "$ANSWER" == all ]]; then
      CATEGORY=all
      return 0
    fi
    picked=()
    ok=1
    IFS=',' read -ra items <<<"$ANSWER"
    for item in "${items[@]}"; do
      [[ -n "$item" ]] || continue
      found=""
      for i in "${!categories[@]}"; do
        if [[ "$item" == "$((i + 1))" || "$item" == "${categories[i]}" ]]; then
          found="${categories[i]}"
        fi
      done
      if [[ -z "$found" ]]; then
        echo "  not a category: $item" >&2
        ok=0
        break
      fi
      [[ " ${picked[*]-} " == *" $found "* ]] || picked+=("$found")
    done
    if ((ok)) && ((${#picked[@]})); then
      CATEGORY="$(
        IFS=,
        printf '%s' "${picked[*]}"
      )"
      return 0
    fi
  done
}

TARGET=""
DETECTED=""
ENV=all
CATEGORY=all

choose_target
# --env and --category do not apply to claude; install.sh would only warn.
if [[ "$TARGET" == claude || ("$TARGET" == detected && "$DETECTED" == claude) ]]; then
  echo "Environment and categories do not apply to claude (it installs plugins instead); skipped." >&2
else
  choose_env
  choose_categories
fi

ARGS=("--target=$TARGET")
[[ "$ENV" == all ]] || ARGS+=("--env=$ENV")
[[ "$CATEGORY" == all ]] || ARGS+=("--category=$CATEGORY")
if ask_yes_no "Install the shared instruction rules (--instructions)?" n; then
  ARGS+=(--instructions)
fi
if ask_yes_no "Install the PR merge guard (--merge-guard)?" n; then
  ARGS+=(--merge-guard)
fi
if ask_yes_no "Install the secret read guard (--secret-guard)?" n; then
  ARGS+=(--secret-guard)
fi

echo "Equivalent command (reuse it in scripts):" >&2
# Every value comes from a fixed choice list, so it needs no shell quoting.
printf '%q %s\n' "$INSTALLER" "${ARGS[*]}"

if ask_yes_no "Run a dry run first (--dry-run)?" y; then
  "$INSTALLER" "${ARGS[@]}" --dry-run
fi
if ask_yes_no "Install now?" n; then
  exec "$INSTALLER" "${ARGS[@]}"
fi
echo "Nothing installed." >&2
