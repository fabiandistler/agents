#!/usr/bin/env bats
# install.sh --git-hook: the per-clone post-merge and post-rewrite hooks that
# replay the saved install after a pull or rebase.

load install_helper

setup() {
  install_setup
}

# run_hook_install HOME STATE GIT_DIR ARGS...: install.sh against the Git
# directory GIT_DIR through Bats' run.
run_hook_install() {
  local home="$1" state_home="$2" git_dir="$3"
  shift 3
  run env HOME="$home" XDG_STATE_HOME="$state_home" \
    GIT_DIR="$git_dir" GIT_WORK_TREE="$REPO_ROOT" "$INSTALL" "$@"
}

# hook_run HOOK HOME STATE GIT_DIR INPUT: run a managed hook from the repo
# root as Git would, with INPUT on stdin.
hook_run() {
  local hook="$1" home="$2" state_home="$3" git_dir="$4" input="$5"
  cd "$REPO_ROOT" && printf '%s' "$input" |
    HOME="$home" XDG_STATE_HOME="$state_home" \
      GIT_DIR="$git_dir" GIT_WORK_TREE="$REPO_ROOT" "$hook"
}

# A fresh Git directory with the hooks installed for a codex install.
install_git_hook_clone() {
  hook_home="$(mktemp -d)"
  state_home="$hook_home/xdg-state"
  git_home="$(mktemp -d)"
  git -C "$git_home" init -q
  git_dir="$git_home/.git"
  hooks_dir="$git_dir/hooks"
  post_merge="$hooks_dir/post-merge"
  post_rewrite="$hooks_dir/post-rewrite"
  skill_link="$hook_home/.agents/skills/communication-analysis"
  run_hook_install "$hook_home" "$state_home" "$git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "--git-hook install failed: $output"
}

# The worktree tests exercise the hooks through real git operations in a
# throwaway copy of this checkout, so linked worktrees and core.hooksPath
# behave as they do for users.
sandbox_git() {
  HOME="$home" XDG_STATE_HOME="$state" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 \
    GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid \
    GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid git "$@"
}

run_sandbox_install() {
  local checkout="$1"
  shift
  run env HOME="$home" XDG_STATE_HOME="$state" GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_NOSYSTEM=1 "$checkout/install.sh" "$@"
}

# A committed copy of this checkout (without the Bats submodules) with a
# topic branch and a linked worktree.
fresh_sandbox() {
  sandbox="$(cd "$(mktemp -d)" && pwd -P)"
  home="$sandbox/home"
  state="$sandbox/state"
  main_clone="$sandbox/main"
  linked="$sandbox/linked"
  mkdir -p "$home" "$main_clone"
  git -C "$REPO_ROOT" ls-files -z -- ':(exclude)test/bats' |
    (cd "$REPO_ROOT" && tar --null -T - -cf -) | tar -C "$main_clone" -xf -
  sandbox_git -C "$main_clone" init -q -b main
  sandbox_git -C "$main_clone" add -A
  sandbox_git -C "$main_clone" commit -q -m sandbox
  sandbox_git -C "$main_clone" branch topic
  sandbox_git -C "$main_clone" worktree add -q "$linked" -b side
  skill_link="$home/.agents/skills/communication-analysis"
}

@test "--git-hook creates executable marker-owned hooks idempotently" {
  install_git_hook_clone
  [[ -x "$post_merge" && -x "$post_rewrite" ]] ||
    fail "--git-hook did not create executable post-merge and post-rewrite hooks"
  grep -Fqx '# managed-by: fabiandistler/agents install.sh' "$post_merge" ||
    fail "post-merge hook is missing its ownership marker"
  grep -Fqx '# managed-by: fabiandistler/agents install.sh' "$post_rewrite" ||
    fail "post-rewrite hook is missing its ownership marker"
  [[ "$(head -n 1 "$post_rewrite")" == '#!/bin/sh' &&
  "$(sed -n '3p' "$post_rewrite")" == 'cat >/dev/null' ]] ||
    fail "post-rewrite hook does not consume Git's rewrite list"
  [[ -f "$state_home/fabiandistler-agents/install.json" ]] ||
    fail "--git-hook install did not save replay state"
  before_merge="$(cat "$post_merge")"
  before_rewrite="$(cat "$post_rewrite")"
  run_hook_install "$hook_home" "$state_home" "$git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "reinstalling --git-hook failed: $output"
  [[ "$(cat "$post_merge")" == "$before_merge" &&
  "$(cat "$post_rewrite")" == "$before_rewrite" ]] ||
    fail "reinstalling --git-hook rewrote unchanged hooks"
  [[ "$output" == *"ok        $post_merge (Git hook)"* &&
    "$output" == *"ok        $post_rewrite (Git hook)"* ]] ||
    fail "reinstalling --git-hook did not report both hooks unchanged"
}

@test "post-merge checks first, then replays only when drift exists" {
  install_git_hook_clone
  rm "$skill_link"
  run hook_run "$post_merge" "$hook_home" "$state_home" "$git_dir" ""
  [[ "$status" -eq 0 && "$output" == *'--check: drift'* && -L "$skill_link" ]] ||
    fail "post-merge did not check and replay the saved install: $output"
  "$PYTHON" - "$output" "$skill_link" "$REPO_ROOT" <<'PY' || fail "post-merge ran --update before its --check"
import sys

output, skill_link, repo_root = sys.argv[1:]
check = output.index("--check: drift")
update = output.index(f"linked    {skill_link} -> {repo_root}/skills/communication-analysis")
assert check < update
PY
}

@test "post-rewrite consumes rewrite input and checks before updating" {
  install_git_hook_clone
  run hook_run "$post_rewrite" "$hook_home" "$state_home" "$git_dir" "old new\n"
  [[ "$status" -eq 0 && "$output" == '--check: clean' ]] ||
    fail "clean post-rewrite did not stop after its read-only check: $output"
  rm "$skill_link"
  run hook_run "$post_rewrite" "$hook_home" "$state_home" "$git_dir" "old new\n"
  [[ "$status" -eq 0 && "$output" == *'--check: drift'* && -L "$skill_link" ]] ||
    fail "post-rewrite did not consume stdin and replay drift: $output"
}

@test "--uninstall --git-hook removes only this clone's managed hooks" {
  install_git_hook_clone
  run_hook_install "$hook_home" "$state_home" "$git_dir" --uninstall --git-hook
  [[ "$status" -eq 0 && ! -e "$post_merge" && ! -e "$post_rewrite" ]] ||
    fail "targetless --uninstall --git-hook did not remove both managed hooks: $output"
}

@test "--git-hook --dry-run creates no hooks" {
  dry_home="$(mktemp -d)"
  dry_state="$dry_home/xdg-state"
  dry_git_home="$(mktemp -d)"
  git -C "$dry_git_home" init -q
  dry_git_dir="$dry_git_home/.git"
  run_hook_install "$dry_home" "$dry_state" "$dry_git_dir" \
    --target=codex --category=communication --git-hook --dry-run
  [[ "$status" -eq 0 && ! -e "$dry_git_dir/hooks/post-merge" &&
    ! -e "$dry_git_dir/hooks/post-rewrite" ]] ||
    fail "--git-hook --dry-run wrote into the Git hooks directory"
}

@test "foreign post-merge hooks survive install and uninstall" {
  foreign_home="$(mktemp -d)"
  foreign_state="$foreign_home/xdg-state"
  foreign_git_home="$(mktemp -d)"
  git -C "$foreign_git_home" init -q
  foreign_git_dir="$foreign_git_home/.git"
  foreign_hooks="$foreign_git_dir/hooks"
  foreign_merge="$foreign_hooks/post-merge"
  foreign_rewrite="$foreign_hooks/post-rewrite"
  foreign_content=$'#!/bin/sh\n# human-owned hook\nexit 0'
  printf '%b\n' "$foreign_content" >"$foreign_merge"
  chmod +x "$foreign_merge"
  run_hook_install "$foreign_home" "$foreign_state" "$foreign_git_dir" \
    --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 && "$(cat "$foreign_merge")" == "$foreign_content" &&
  -x "$foreign_rewrite" ]] ||
    fail "--git-hook overwrote a foreign hook or failed to install the other hook: $output"
  run_hook_install "$foreign_home" "$foreign_state" "$foreign_git_dir" \
    --uninstall --git-hook
  [[ "$status" -eq 0 && "$(cat "$foreign_merge")" == "$foreign_content" &&
  ! -e "$foreign_rewrite" ]] ||
    fail "--uninstall --git-hook removed a foreign hook or kept its managed hook"
}

@test "post-merge replays only for the installing checkout, not linked worktrees" {
  fresh_sandbox
  run_sandbox_install "$main_clone" --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 ]] || fail "--git-hook install in the sandbox clone failed: $output"
  sandbox_git -C "$main_clone" switch -q topic
  echo topic >"$main_clone/topic.txt"
  sandbox_git -C "$main_clone" add topic.txt
  sandbox_git -C "$main_clone" commit -q -m topic
  sandbox_git -C "$main_clone" switch -q main
  rm "$skill_link"
  sandbox_git -C "$linked" merge -q --no-edit topic >/dev/null 2>&1
  [[ ! -e "$skill_link" && ! -L "$skill_link" ]] ||
    fail "a merge in a linked worktree replayed the install from that worktree"
  sandbox_git -C "$main_clone" merge -q --no-edit topic >/dev/null 2>&1
  [[ "$(readlink "$skill_link")" == "$main_clone/skills/communication-analysis" ]] ||
    fail "a merge in the installing clone did not replay the install into it"
}

@test "--git-hook from a linked worktree writes the hooks Git actually runs" {
  fresh_sandbox
  run_sandbox_install "$linked" --target=codex --category=communication --git-hook
  [[ "$status" -eq 0 && -x "$main_clone/.git/hooks/post-merge" &&
    -x "$main_clone/.git/hooks/post-rewrite" &&
    ! -e "$main_clone/.git/worktrees/linked/hooks/post-merge" &&
    "$output" == *"created   $main_clone/.git/hooks/post-merge (Git hook)"* ]] ||
    fail "--git-hook from a linked worktree did not write the common hooks dir: $output"
}

@test "--git-hook refuses with exit 1 when core.hooksPath is set" {
  fresh_sandbox
  sandbox_git -C "$main_clone" config core.hooksPath .husky
  run_sandbox_install "$main_clone" --target=codex --category=communication --git-hook
  [[ "$status" -eq 1 && "$output" == *'core.hooksPath is set'* &&
    ! -e "$main_clone/.husky" && ! -e "$main_clone/.git/hooks/post-merge" &&
    ! -e "$home/.agents" && ! -e "$state/fabiandistler-agents/install.json" ]] ||
    fail "--git-hook with core.hooksPath did not refuse before writing: $output"
}
