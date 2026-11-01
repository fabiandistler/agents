# shellcheck shell=bash
# Shared by the install_*.bats suites. Expected link counts are read from the
# skills' SKILL.md frontmatter, as install.sh reads it, so the tests follow
# the catalogue instead of hard-coded numbers.

load test_helper

INSTALL="$REPO_ROOT/install.sh"
# shellcheck source=scripts/require_python.sh
. "$REPO_ROOT/scripts/require_python.sh"

install_setup() {
  common_setup
  # The TOML assertions need tomllib (3.11+).
  require_python "${BATS_TEST_FILENAME##*/}" "$PYTHON"
  # Every successful install saves its options here; keep that out of the
  # real state directory.
  XDG_STATE_HOME="$(mktemp -d)"
  export XDG_STATE_HOME
  install_claude_stub
}

# A fake claude CLI first on PATH, so the guard plugin code never reaches a
# real Claude Code install. Per HOME it keeps one list per file under
# claude_stub_dir: installed (user scope, enabled), disabled (user scope),
# project (project scope), marketplaces, and calls, its call log. A call
# matching the line in a `fail` file there exits 1; a call it does not know
# exits 64.
install_claude_stub() {
  CLAUDE_STUB_ROOT="$(mktemp -d)"
  mkdir "$CLAUDE_STUB_ROOT/bin"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'stub_root=%q\n' "$CLAUDE_STUB_ROOT"
    cat <<'STUB'
set -euo pipefail
state="$stub_root/home${HOME//\//_}"
mkdir -p "$state"
touch "$state/installed" "$state/disabled" "$state/project" "$state/marketplaces"
printf '%s\n' "$*" >>"$state/calls"
if [[ -f "$state/fail" && "$*" == "$(cat "$state/fail")" ]]; then
  echo "claude stub: failing on request: $*" >&2
  exit 1
fi
entries=""
add_plugins() {
  local id
  while IFS= read -r id; do
    entries+=",{\"id\":\"$id\",\"scope\":\"$2\",\"enabled\":$3}"
  done <"$state/$1"
}
case "$*" in
  "plugin list --json")
    add_plugins installed user true
    add_plugins disabled user false
    add_plugins project project true
    printf '[%s]\n' "${entries#,}"
    ;;
  "plugin marketplace list --json")
    while IFS= read -r name; do entries+=",{\"name\":\"$name\"}"; done <"$state/marketplaces"
    printf '[%s]\n' "${entries#,}"
    ;;
  "plugin marketplace add fabiandistler/agents")
    echo fabiandistler-agents >>"$state/marketplaces"
    ;;
  "plugin install "*@fabiandistler-agents)
    grep -Fxq fabiandistler-agents "$state/marketplaces" || {
      echo "claude stub: marketplace fabiandistler-agents not added" >&2
      exit 1
    }
    echo "$3" >>"$state/installed"
    ;;
  "plugin uninstall "*)
    grep -Fxq "$3" "$state/installed" "$state/disabled" || {
      echo "claude stub: $3 not installed" >&2
      exit 1
    }
    for list in installed disabled; do
      grep -Fxv "$3" "$state/$list" >"$state/$list.new" || true
      mv "$state/$list.new" "$state/$list"
    done
    ;;
  *)
    echo "claude stub: unexpected call: $*" >&2
    exit 64
    ;;
esac
STUB
  } >"$CLAUDE_STUB_ROOT/bin/claude"
  chmod +x "$CLAUDE_STUB_ROOT/bin/claude"
  PATH="$CLAUDE_STUB_ROOT/bin:$PATH"
}

# claude_stub_dir HOME: the stub's state directory for HOME, created on demand
# so a test can seed it before install.sh runs.
claude_stub_dir() {
  local dir="$CLAUDE_STUB_ROOT/home${1//\//_}"
  mkdir -p "$dir"
  printf '%s' "$dir"
}

# PATH without any claude command: drops the stub and replaces every other
# directory that holds a claude command with links to its other commands.
path_without_claude() {
  local dir entry shadow new_path=""
  local -a dirs
  IFS=: read -ra dirs <<<"$PATH"
  for dir in "${dirs[@]}"; do
    [[ "$dir" == "$CLAUDE_STUB_ROOT/bin" ]] && continue
    if [[ -x "$dir/claude" ]]; then
      shadow="$(mktemp -d)"
      for entry in "$dir"/*; do
        [[ "${entry##*/}" == claude ]] || ln -s "$entry" "$shadow/"
      done
      dir="$shadow"
    fi
    new_path+="${new_path:+:}$dir"
  done
  printf '%s' "$new_path"
}

# run_install HOME ARGS...: install.sh under HOME through Bats' run, so
# $status and $output hold its exit code and combined stdout and stderr.
run_install() {
  local home="$1"
  shift
  run env HOME="$home" "$INSTALL" "$@"
}

file_inode() {
  "$PYTHON" -c 'import os, sys; print(os.stat(sys.argv[1]).st_ino)' "$1"
}

count_links() {
  # POSIX-portable: -L returns 0 only for symlinks.
  local dir="$1" n=0 f
  [[ -d "$dir" ]] || {
    echo 0
    return
  }
  for f in "$dir"/*; do
    [[ -L "$f" ]] && n=$((n + 1))
  done
  echo "$n"
}

# True if a skill's frontmatter marks it `activation: command`.
skill_is_command() {
  grep -Eq '^activation:[[:space:]]*command[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
}

# True if a skill is a per-category router (activation: router).
skill_is_router() {
  grep -Eq '^activation:[[:space:]]*router[[:space:]]*$' "$1/SKILL.md" 2>/dev/null
}

skill_dir_category() {
  grep -m1 '^category:' "$1/SKILL.md" 2>/dev/null | sed 's/^category://;s/[[:space:]]//g'
}

# Space-padded list of categories that ship a router skill, computed on first
# use: most tests never need it.
ROUTED_CATEGORIES=""
routed_categories() {
  local d
  if [[ -z "$ROUTED_CATEGORIES" ]]; then
    ROUTED_CATEGORIES=" "
    for d in "$REPO_ROOT"/skills/*/; do
      [[ -f "$d/SKILL.md" ]] || continue
      skill_is_router "$d" && ROUTED_CATEGORIES+="$(skill_dir_category "$d") "
    done
  fi
}

# True if a skill is an auto member nested under a router (not linked at top
# level): a non-router, non-command skill whose category is routed.
skill_is_nested_member() {
  routed_categories
  skill_is_router "$1" && return 1
  skill_is_command "$1" && return 1
  [[ "$ROUTED_CATEGORIES" == *" $(skill_dir_category "$1") "* ]]
}

# True if a skill is installed for the given target ($2). A skill without a
# `targets:` field belongs to every target.
skill_matches_target() {
  local targets
  targets="$(grep -m1 '^targets:' "$1/SKILL.md" 2>/dev/null | sed 's/^targets://')"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  [[ ",${targets// /}," == *",$2,"* ]]
}

# True if a skill belongs to environment $2 (coding|chat|all). A skill without
# an `environments:` field belongs to every environment.
skill_matches_env() {
  local envs
  [[ "$2" == all ]] && return 0
  envs="$(grep -m1 '^environments:' "$1/SKILL.md" 2>/dev/null | sed 's/^environments://')"
  [[ -z "${envs//[[:space:]]/}" ]] || [[ ",${envs// /}," == *",$2,"* ]]
}

skill_count() {
  # Count auto-triggered skills (those linked into the skills dir), optionally
  # filtered by environment ($1 = coding|chat|all) and target ($2, default
  # claude — skills may opt out of a target via `targets:`).
  local want="${1:-all}" target="${2:-claude}" n=0 d
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" && continue
    # Nested members ride under their router, so they are not linked flat.
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" "$target" || continue
    skill_matches_env "$d" "$want" || continue
    n=$((n + 1))
  done
  echo "$n"
}

command_count() {
  # Count `activation: command` skills (linked as ordinary skills), optionally
  # filtered by environment ($1 = coding|chat|all) and target ($2, default
  # claude).
  local want="${1:-all}" target="${2:-claude}" n=0 d
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" || continue
    skill_matches_target "$d" "$target" || continue
    skill_matches_env "$d" "$want" || continue
    n=$((n + 1))
  done
  echo "$n"
}

category_count() {
  # Count skills whose category: frontmatter is in the comma-separated list $1,
  # as installed for target $2 (default claude).
  local want="$1" target="${2:-claude}" n=0 d cat
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" "$target" || continue
    cat="$(grep -m1 '^category:' "$d/SKILL.md" 2>/dev/null | sed 's/^category://')"
    cat="${cat//[[:space:]]/}"
    [[ -n "$cat" ]] && [[ ",$want," == *",$cat,"* ]] && n=$((n + 1))
  done
  echo "$n"
}

# Every link opencode creates on its own: auto and command skills.
opencode_expected() {
  echo $(($(skill_count all opencode) + $(command_count all opencode)))
}

# Skills opencode links itself under --target=all: those that skip codex, so
# ~/.agents/skills (the root opencode shares) does not hold them. With `auto`,
# only the auto skills among them.
opencode_only_expected() {
  local only_auto="${1:-}" n=0 d
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_nested_member "$d" && continue
    skill_matches_target "$d" opencode || continue
    skill_matches_target "$d" codex && continue
    [[ -n "$only_auto" ]] && skill_is_command "$d" && continue
    n=$((n + 1))
  done
  echo "$n"
}
