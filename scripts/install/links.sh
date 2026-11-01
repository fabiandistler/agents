# shellcheck shell=bash
# Sourced by install.sh. Dry-run aware actions, the per-clone Git hooks, and symlink primitives.

run() {
  if ((DRY_RUN)); then
    case "$1" in
      rm) printf '[dry-run] remove %s\n' "$2" ;;
      ln) printf '[dry-run] link %s\n' "$4" ;;
      mkdir) return 0 ;;
      *)
        printf 'run: unsupported dry-run operation\n' >&2
        return 2
        ;;
    esac
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

git_hooks_dir() {
  local toplevel hooks_dir
  if ! toplevel="$(git -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
    echo "--git-hook requires a Git checkout" >&2
    return 1
  fi
  # A hooksPath dir belongs to a hook manager (husky, lefthook) or is shared
  # across repositories, so this installer never writes into it.
  if [[ -n "$(git -C "$toplevel" config --get core.hooksPath || true)" ]]; then
    echo "--git-hook refuses to write while core.hooksPath is set; call ./install.sh --update from that hook manager instead" >&2
    return 1
  fi
  # --git-path resolves the common hooks dir from a linked worktree too.
  hooks_dir="$(git -C "$toplevel" rev-parse --git-path hooks)"
  [[ "$hooks_dir" == /* ]] || hooks_dir="$toplevel/$hooks_dir"
  printf '%s\n' "$hooks_dir"
}

render_git_hook() {
  local hook="$1"
  cat <<'HOOK'
#!/bin/sh
# managed-by: fabiandistler/agents install.sh
HOOK
  if [[ "$hook" == post-rewrite ]]; then
    printf '%s\n' 'cat >/dev/null'
  fi
  local install_root
  install_root="$(cd "$REPO_ROOT" && pwd -P)"
  # Git runs these hooks in every linked worktree; only the installing
  # checkout may replay, or the links would follow a worktree that gets removed.
  printf "install_root='%s'\n" "${install_root//\'/\'\\\'\'}"
  cat <<'HOOK'
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
[ "$(cd "$repo_root" && pwd -P)" = "$install_root" ] || exit 0
cd "$install_root" || exit 1
if ./install.sh --update --check; then
  exit 0
else
  check_status=$?
  [ "$check_status" -eq 3 ] || exit "$check_status"
fi
exec ./install.sh --update
HOOK
}

git_hook_is_managed() {
  [[ -f "$1" && ! -L "$1" ]] && grep -qxF "$GIT_HOOK_MARKER" "$1"
}

install_git_hooks() {
  local hooks_dir hook file content before
  hooks_dir="$(git_hooks_dir)" || return 1
  ensure_parent "$hooks_dir"
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    content="$(render_git_hook "$hook")"
    if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
      printf '  WARN      %s is not a regular hook file (skipping)\n' "$file" >&2
      continue
    fi
    if [[ -f "$file" ]]; then
      before="$(cat "$file")"
      if ! grep -qxF "$GIT_HOOK_MARKER" <<<"$before"; then
        printf '  WARN      %s is not managed by this installer (skipping)\n' "$file" >&2
        continue
      fi
      if [[ "$before" == "$content" && -x "$file" ]]; then
        printf '  ok        %s (Git hook)\n' "$file"
        continue
      fi
      if ((DRY_RUN)); then
        printf '[dry-run] update %s\n' "$file"
        continue
      fi
      write_file_atomic "$file" "$content" "$GIT_HOOK_MARKER" "" "$before" file 755
      printf '  updated   %s (Git hook)\n' "$file"
      continue
    fi
    if ((DRY_RUN)); then
      printf '[dry-run] create %s\n' "$file"
      continue
    fi
    write_file_atomic "$file" "$content" "$GIT_HOOK_MARKER" "" "" file 755
    printf '  created   %s (Git hook)\n' "$file"
  done
}

remove_git_hooks() {
  local hooks_dir hook file before
  hooks_dir="$(git_hooks_dir)" || return 1
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    [[ -e "$file" || -L "$file" ]] || continue
    if ! git_hook_is_managed "$file"; then
      printf '  WARN      %s is not a marker-owned hook (leaving it untouched)\n' "$file" >&2
      continue
    fi
    before="$(cat "$file")"
    if ((DRY_RUN)); then
      printf '[dry-run] remove %s\n' "$file"
      continue
    fi
    if ! git_hook_is_managed "$file" || [[ "$(cat "$file")" != "$before" ]]; then
      printf '  WARN      %s changed during uninstall (leaving it untouched)\n' "$file" >&2
      continue
    fi
    rm "$file"
    printf '  removed   %s (Git hook)\n' "$file"
  done
}

check_git_hooks() {
  local hooks_dir hook file expected actual state
  hooks_dir="$(git_hooks_dir)" || return 1
  for hook in post-merge post-rewrite; do
    file="$hooks_dir/$hook"
    expected="$(render_git_hook "$hook")"
    if [[ -L "$file" ]] || { [[ -e "$file" ]] && [[ ! -f "$file" ]]; }; then
      state=foreign
    elif [[ ! -f "$file" ]]; then
      state=missing
    else
      actual="$(cat "$file")"
      if ! grep -qxF "$GIT_HOOK_MARKER" <<<"$actual"; then
        state=foreign
      elif [[ "$(grep -Fxc "$GIT_HOOK_MARKER" <<<"$actual" || true)" != 1 ]]; then
        state=duplicate
      elif [[ "$actual" != "$expected" || ! -x "$file" ]]; then
        state=stale
      else
        continue
      fi
    fi
    check_record all git-hook "$file" "$state"
  done
}

link_one() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    local current
    current="$(readlink "$dest")"
    if [[ $'\n'"$PLANNED_REBASED_LINKS" == *$'\n'"$dest"$'\n'* ]]; then
      return 0
    fi
    if [[ "$current" == "$src" ]]; then
      printf '  ok        %s -> %s\n' "$dest" "$src"
      return 0
    fi
    if [[ "$current" == "$REPO_ROOT/skills/"* ]]; then
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" stale
    else
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    fi
    ((CHECK_MODE)) || printf '  WARN      %s already symlinked to %s (skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  if [[ -e "$dest" ]]; then
    check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    ((CHECK_MODE)) || printf '  WARN      %s exists and is not a symlink (skipping)\n' "$dest" >&2
    return 0
  fi
  check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" missing
  if ((DRY_RUN)); then
    printf '[dry-run] link %s\n' "$dest"
    PLANNED_LINKS+="$dest"$'\n'
    return 0
  fi
  run ln -s "$src" "$dest"
  printf '  linked    %s -> %s\n' "$dest" "$src"
}

PLANNED_REBASED_LINKS=""

rebase_repo_symlink() {
  local link="$1" current suffix new_target
  [[ -n "$OLD_REPO_ROOT" && "$OLD_REPO_ROOT" != "$REPO_ROOT" ]] || return 0
  [[ -L "$link" ]] || return 0
  current="$(readlink "$link")"
  [[ "$current" == "$OLD_REPO_ROOT/"* ]] || return 0
  suffix="${current#"$OLD_REPO_ROOT"/}"
  new_target="$REPO_ROOT/$suffix"
  [[ "$new_target" == "$REPO_ROOT/"* && (-e "$new_target" || -L "$new_target") ]] || return 0
  if ((DRY_RUN)); then
    printf '[dry-run] relink %s to current checkout\n' "$link"
    PLANNED_REBASED_LINKS+="$link"$'\n'
    return 0
  fi
  [[ -L "$link" && "$(readlink "$link")" == "$current" ]] || return 0
  rm "$link"
  [[ ! -e "$link" && ! -L "$link" ]] || {
    printf '  WARN      %s changed during --update; leaving it untouched\n' "$link" >&2
    return 0
  }
  [[ -e "$new_target" || -L "$new_target" ]] || return 0
  ln -s "$new_target" "$link"
  printf '  linked    %s -> %s (moved checkout)\n' "$link" "$new_target"
}

rebase_repo_symlink_dir() {
  local dir="$1" link
  [[ -d "$dir" ]] || return 0
  for link in "$dir"/*; do
    [[ -L "$link" ]] || continue
    rebase_repo_symlink "$link"
  done
}

# Links a dry-run planned but did not create, one per line, so a later target
# in the same dry-run sees the state the real run would leave.
PLANNED_LINKS=""

# True if dest is our link to src, or this dry-run planned it.
our_link_at() {
  local src="$1" dest="$2"
  [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]] ||
    [[ $'\n'"$PLANNED_LINKS" == *$'\n'"$dest"$'\n'* ]]
}
