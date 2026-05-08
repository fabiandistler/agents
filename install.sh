#!/usr/bin/env bash
# Symlink the skills in this repo into the conventional install paths
# for popular coding agents. Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude              # ~/.claude/skills/<skill>
#   ./install.sh --target=codex               # ~/.codex/skills/<skill>
#   ./install.sh --target=opencode            # ~/.config/opencode/agent/<skill>
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # remove symlinks owned by us
#
# Conservative behaviour:
#   - Existing correct symlink:        skip (idempotent).
#   - Symlink pointing elsewhere:      skip with a warning, never overwrite.
#   - Regular file or non-empty dir:   skip with a warning, never overwrite.
#   - Uninstall only removes a symlink whose target is a path inside this
#     repo, so foreign files at that location are never touched.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

DRY_RUN=0
UNINSTALL=0
TARGET=""

usage() { sed -n '2,18p' "$0"; }

for arg in "$@"; do
  case "$arg" in
    --target=*)   TARGET="${arg#--target=}" ;;
    --dry-run)    DRY_RUN=1 ;;
    --uninstall)  UNINSTALL=1 ;;
    -h|--help)    usage; exit 0 ;;
    *)            echo "unknown arg: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "missing --target=claude|codex|opencode|all" >&2
  usage >&2
  exit 2
fi

target_dir_for() {
  case "$1" in
    claude)   printf '%s/.claude/skills\n'        "$HOME" ;;
    codex)    printf '%s/.codex/skills\n'         "$HOME" ;;
    opencode) printf '%s/.config/opencode/agent\n' "$HOME" ;;
    *) echo "unknown target: $1" >&2; return 1 ;;
  esac
}

resolve_targets() {
  if [[ "$TARGET" == "all" ]]; then
    printf 'claude\ncodex\nopencode\n'
  else
    printf '%s\n' "$TARGET"
  fi
}

list_skills() {
  # A directory is a skill iff it contains SKILL.md.
  # Skip hidden dirs and non-skill subprojects.
  local skip='^(scripts|eval-suite|mcp-wiki-server)$'
  for d in "$REPO_ROOT"/*/; do
    local name; name="$(basename "$d")"
    [[ "$name" =~ $skip ]] && continue
    [[ -f "$d/SKILL.md" ]] || continue
    printf '%s\n' "$name"
  done
}

run() {
  if (( DRY_RUN )); then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

ensure_parent() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    run mkdir -p "$dir"
  fi
}

link_one() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    local current; current="$(readlink "$dest")"
    if [[ "$current" == "$src" ]]; then
      printf '  ok        %s -> %s\n' "$dest" "$src"
      return 0
    fi
    printf '  WARN      %s already symlinked to %s (skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  if [[ -e "$dest" ]]; then
    printf '  WARN      %s exists and is not a symlink (skipping)\n' "$dest" >&2
    return 0
  fi
  run ln -s "$src" "$dest"
  printf '  linked    %s -> %s\n' "$dest" "$src"
}

unlink_one() {
  local src="$1" dest="$2"
  if [[ ! -L "$dest" ]]; then
    if [[ -e "$dest" ]]; then
      printf '  WARN      %s exists but is not a symlink (skipping)\n' "$dest" >&2
    fi
    return 0
  fi
  local current; current="$(readlink "$dest")"
  if [[ "$current" != "$src" ]]; then
    printf '  WARN      %s points to %s (not ours, skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  run rm "$dest"
  printf '  removed   %s\n' "$dest"
}

main() {
  local skills; skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT" >&2
    exit 1
  fi

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    local dest_dir; dest_dir="$(target_dir_for "$target")"
    printf '%s: %s\n' "$target" "$dest_dir"
    if (( UNINSTALL == 0 )); then
      ensure_parent "$dest_dir"
    fi
    while IFS= read -r skill; do
      local src="$REPO_ROOT/$skill"
      local dest="$dest_dir/$skill"
      if (( UNINSTALL )); then
        unlink_one "$src" "$dest"
      else
        link_one "$src" "$dest"
      fi
    done <<< "$skills"
  done < <(resolve_targets)
}

main
