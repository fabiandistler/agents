# shellcheck shell=bash
# Sourced by install.sh. Skill links per target, legacy cleanup, and checkout-move rebasing.

# --- Skill roots opencode shares ----------------------------------------------
#
# opencode loads skills from ~/.config/opencode/skills, ~/.claude/skills and
# ~/.agents/skills (https://opencode.ai/docs/skills), and it expects every
# name to be unique across them. So a skill whose link already sits in the
# codex skills root gets no opencode link of its own, and a duplicate we
# created earlier is removed. A skill the codex root lacks (a `targets:` field
# excluding codex, or a narrower --env or --category for codex) still gets its
# own opencode link. ~/.claude/skills is no shared root any more: Claude takes
# its skills from the plugins, and the claude migration empties that dir of our
# links (handing each one to opencode, see migrate_claude_to_plugins).

opencode_skills_dir() { target_dir_for opencode; }

# Print the codex skills root if it holds our link to src; fail otherwise.
opencode_shared_root_for() {
  local src="$1" root
  root="$(target_dir_for codex)"
  our_link_at "$src" "$root/${src##*/}" || return 1
  printf '%s' "$root"
}

# Remove our opencode link to src, if any: opencode reads src from `root`.
drop_opencode_duplicate() {
  local src="$1" root="$2" dest
  dest="$(opencode_skills_dir)/${src##*/}"
  [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]] || return 0
  check_record opencode skill-link "$dest" duplicate
  run rm "$dest"
  ((DRY_RUN)) || printf '  removed   %s (opencode reads it from %s)\n' "$dest" "$root"
}

unlink_one() {
  local src="$1" dest="$2" state="${3:-stale}"
  if [[ ! -L "$dest" ]]; then
    if [[ -e "$dest" ]]; then
      check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
      ((CHECK_MODE)) || printf '  WARN      %s exists but is not a symlink (skipping)\n' "$dest" >&2
    fi
    return 0
  fi
  local current
  current="$(readlink "$dest")"
  if [[ "$current" != "$src" ]]; then
    check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" foreign
    printf '  WARN      %s points to %s (not ours, skipping)\n' "$dest" "$current" >&2
    return 0
  fi
  check_record "$CHECK_CURRENT_TARGET" skill-link "$dest" "$state"
  if ((DRY_RUN)); then
    printf '[dry-run] remove %s\n' "$dest"
    return 0
  fi
  run rm "$dest"
  ((DRY_RUN)) && return 0
  printf '  removed   %s\n' "$dest"
}

# Remove dangling symlinks a previous install left behind for skills that no
# longer exist in this repo (e.g. a skill that was renamed or deleted, or a
# router that was dismantled): --uninstall only walks the skills the repo
# currently ships, so those links would linger forever. Only broken symlinks
# whose target lies inside this repo's skills/ directory are removed; foreign
# links and anything that still resolves are left untouched.
prune_stale_skill_links() {
  local dir="$1" entry target
  [[ -d "$dir" ]] || return 0
  for entry in "$dir"/*; do
    [[ -L "$entry" ]] || continue
    [[ -e "$entry" ]] && continue
    target="$(readlink "$entry")"
    [[ "$target" == "$REPO_ROOT/skills/"* ]] || continue
    check_record "$CHECK_CURRENT_TARGET" skill-link "$entry" stale
    run rm "$entry"
    ((DRY_RUN)) || printf '  removed   %s (skill no longer in repo)\n' "$entry"
  done
}

# Earlier versions linked skills into OpenCode's agent directory
# (~/.config/opencode/agent), where the skill loader never looks. Remove any
# of our leftover symlinks from there — on install (migration) and uninstall
# alike. Symlinks not pointing into this repo are left untouched.
cleanup_opencode_legacy() {
  local skills="$1"
  local legacy_dir="$HOME/.config/opencode/agent"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    local src="$REPO_ROOT/skills/$skill"
    local dest="$legacy_dir/$skill"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$src" ]] || continue
    check_record "$CHECK_CURRENT_TARGET" legacy-skill-link "$dest" stale
    run rm "$dest"
    ((DRY_RUN)) || printf '  removed   %s (legacy opencode location)\n' "$dest"
  done <<<"$skills"
}

# Earlier releases linked command skills into OpenCode's singular command/
# directory. Their metadata now exposes the same skill as a slash command from
# skills/, so remove only those old symlinks after the new location is handled.
cleanup_opencode_legacy_commands() {
  local skills="$1" legacy_dir skill source dest
  legacy_dir="$(opencode_legacy_command_dir)"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -n "$skill" ]] || continue
    [[ "$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")" == command ]] || continue
    source="$REPO_ROOT/skills/$skill/SKILL.md"
    dest="$legacy_dir/$skill.md"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$source" ]] || continue
    check_record opencode "legacy OpenCode command skill" "$dest" stale
    if ((DRY_RUN)); then
      printf '[dry-run] remove %s\n' "$dest"
      continue
    fi
    if [[ ! -L "$dest" || "$(readlink "$dest")" != "$source" ]]; then
      printf '  WARN      %s changed during migration (leaving it untouched)\n' "$dest" >&2
      continue
    fi
    rm "$dest"
    printf '  removed   %s (legacy OpenCode command location)\n' "$dest"
  done <<<"$skills"
}

# Earlier versions linked Codex skills into ~/.codex/skills, which Codex still
# reads for backward compatibility; left there, every skill would load twice
# next to ~/.agents/skills. Remove all our links from there, whatever --env or
# --category says, on install (migration) and uninstall alike. A link counts as
# ours when its target lies inside this repo's skills/ directory, so links
# other tools put there are never touched.
cleanup_codex_skills_legacy() {
  local legacy_dir="$HOME/.codex/skills" entry
  [[ -d "$legacy_dir" ]] || return 0
  for entry in "$legacy_dir"/*; do
    [[ -L "$entry" ]] || continue
    [[ "$(readlink "$entry")" == "$REPO_ROOT/skills/"* ]] || continue
    check_record codex legacy-skill-link "$entry" stale
    run rm "$entry"
    ((DRY_RUN)) || printf '  removed   %s (deprecated codex skills dir)\n' "$entry"
  done
}

# Claude gets skills, command skills, subagents and the merge guard from the
# plugin marketplace (#567). Earlier versions linked skills into
# ~/.claude/skills, command skills into ~/.claude/commands, and wrote the merge
# guard into ~/.claude/settings.json; next to the plugins, every skill would
# load twice (/tldr and /communication:tldr). Remove what we created, on install
# and uninstall alike and regardless of --env/--category. Only symlinks into
# this repo's skills/ (dangling ones included) are touched.
# An earlier opencode install may have skipped a skill because opencode read it
# from ~/.claude/skills. When opencode is installed (its skills dir exists),
# each removed skill link is handed over: opencode gets its own link unless the
# codex root still shares it.
migrate_claude_to_plugins() {
  local dir entry src
  for dir in "$(target_dir_for claude)" "$(target_command_dir_for claude)"; do
    [[ -d "$dir" ]] || continue
    for entry in "$dir"/*; do
      [[ -L "$entry" ]] || continue
      src="$(readlink "$entry")"
      [[ "$src" == "$REPO_ROOT/skills/"* ]] || continue
      check_record claude legacy-skill-link "$entry" stale
      run rm "$entry"
      ((DRY_RUN)) || printf '  removed   %s (now in the Claude plugins)\n' "$entry"
      if [[ "$dir" == "$(target_dir_for claude)" && -f "$src/SKILL.md" ]]; then
        hand_skill_to_opencode "$src"
      fi
    done
  done
  remove_claude_settings_merge_guard
}

# Give opencode its own link to a skill it used to read from ~/.claude/skills.
hand_skill_to_opencode() {
  local src="$1" opencode_dir
  opencode_dir="$(opencode_skills_dir)"
  [[ -d "$opencode_dir" ]] || return 0
  skill_matches_target "$src/SKILL.md" opencode || return 0
  opencode_shared_root_for "$src" >/dev/null && return 0
  link_one "$src" "$opencode_dir/${src##*/}"
}

cleanup_codex_prompts_legacy() {
  local skills="$1"
  local legacy_dir="$HOME/.codex/prompts"
  [[ -d "$legacy_dir" ]] || return 0
  while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    local src="$REPO_ROOT/skills/$skill/SKILL.md"
    local dest="$legacy_dir/$skill.md"
    [[ -L "$dest" ]] || continue
    [[ "$(readlink "$dest")" == "$src" ]] || continue
    check_record codex legacy-prompt-link "$dest" stale
    run rm "$dest"
    ((DRY_RUN)) || printf '  removed   %s (deprecated codex prompt)\n' "$dest"
  done <<<"$skills"
}

# Link (or, with --uninstall, unlink) the selected skills for one target, then
# prune links to skills the repo no longer ships.
sync_skill_links() {
  local target="$1" skills="$2" routed="$3"
  local dest_dir shared_root
  dest_dir="$(target_dir_for "$target")"
  if ((UNINSTALL == 0)); then
    ensure_parent "$dest_dir"
  fi
  while IFS= read -r skill; do
    local src dest activation category
    activation="$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")"
    category="$(skill_category "$REPO_ROOT/skills/$skill/SKILL.md")"
    if [[ "$activation" == "auto" && "$routed" == *" $category "* ]]; then
      # Auto member of a routed category: it is nested under the router's
      # members/ dir and loads lazily when routed to, so it is never linked
      # at top level. Command skills are ordinary skill links for Codex and
      # OpenCode, and their runtime metadata keeps them explicitly invoked.
      # Codex discovers the nested member recursively anyway; it is disabled
      # by path in ~/.codex/config.toml further down.
      # Migration: before this category was routed, the member was linked
      # flat here. That link still resolves, so prune_stale_skill_links (which
      # only removes broken ones) leaves it, and the member keeps registering
      # at top level — exactly what routing exists to prevent. Remove it on
      # both paths. unlink_one only touches a symlink pointing at our own
      # path, so foreign entries and real directories are left alone.
      unlink_one "$REPO_ROOT/skills/$skill" "$dest_dir/$skill"
      continue
    else
      # A normal auto or command skill, or the router itself (linked as a
      # whole dir so its nested members/ come along).
      src="$REPO_ROOT/skills/$skill"
      dest="$dest_dir/$skill"
    fi
    # A skill whose `targets:` field excludes this agent is never linked
    # here; unlinking instead keeps the tree self-healing when the field is
    # added to a skill that was already installed.
    if ((UNINSTALL)) || ! skill_matches_target "$REPO_ROOT/skills/$skill/SKILL.md" "$target"; then
      unlink_one "$src" "$dest"
    elif [[ "$target" == "opencode" && "$dest" == "$dest_dir/"* ]] &&
      shared_root="$(opencode_shared_root_for "$src")"; then
      drop_opencode_duplicate "$src" "$shared_root"
      if ((DRY_RUN)) && [[ "$(readlink "$dest" 2>/dev/null)" == "$src" ]]; then
        continue
      fi
      printf '  shared    %s (opencode reads it from %s)\n' "$dest" "$shared_root"
    else
      link_one "$src" "$dest"
      # Run in either order, claude/codex and opencode end up with one link.
      if [[ "$target" != "opencode" && "$dest" == "$dest_dir/"* ]] &&
        our_link_at "$src" "$dest"; then
        drop_opencode_duplicate "$src" "$dest_dir"
      fi
    fi
  done <<<"$skills"
  # opencode loses the skills it read from this root; tell the user how to
  # give it links of its own. --target=all removes opencode's links anyway.
  if ((UNINSTALL)) && [[ "$TARGET" != "all" && "$target" != "opencode" ]] &&
    [[ -d "$(opencode_skills_dir)" ]]; then
    printf '  note      opencode read skills from %s; re-run --target=opencode to link them for it\n' \
      "$dest_dir" >&2
  fi
  prune_stale_skill_links "$dest_dir"
  if [[ "$target" == "opencode" ]]; then
    prune_stale_skill_links "$(opencode_legacy_command_dir)"
  fi
  return 0
}

rebase_managed_repo_paths() {
  local target config guard file agents_dir agent name payloads_dir
  [[ "$CHECK_MODE" == 0 && -n "$OLD_REPO_ROOT" && "$OLD_REPO_ROOT" != "$REPO_ROOT" ]] ||
    return 0
  while IFS= read -r target; do
    [[ -n "$target" ]] || continue
    rebase_managed_block_path "$(instruction_file_for "$target")" \
      "$(instructions_begin_marker)" "$(instructions_end_marker)"
    case "$target" in
      claude)
        rebase_repo_symlink_dir "$HOME/.claude/skills"
        rebase_repo_symlink_dir "$HOME/.claude/commands"
        while IFS= read -r file; do
          [[ -n "$file" ]] && rebase_owned_file_path "$file" "$(claude_rule_marker)"
        done < <(list_managed_claude_rules)
        ;;
      codex)
        rebase_repo_symlink_dir "$HOME/.agents/skills"
        rebase_repo_symlink_dir "$HOME/.codex/skills"
        rebase_repo_symlink_dir "$HOME/.codex/prompts"
        config="$(codex_config_path)"
        rebase_managed_block_path "$config" "$(skill_override_begin_marker)" \
          "$(skill_override_end_marker)"
        for guard in merge secret; do
          rebase_managed_block_path "$config" "$(guard_begin_marker "$guard")" \
            "$(guard_end_marker "$guard")"
        done
        agents_dir="$(codex_agents_dir)"
        for agent in "$agents_dir"/*.toml; do
          [[ -f "$agent" ]] || continue
          rebase_owned_file_path "$agent" "$AGENT_MARKER"
        done
        ;;
      opencode)
        rebase_repo_symlink_dir "$HOME/.config/opencode/skills"
        rebase_repo_symlink_dir "$(opencode_legacy_command_dir)"
        rebase_repo_symlink_dir "$HOME/.config/opencode/plugins"
        rebase_repo_symlink_dir "$HOME/.config/opencode/agent"
        agents_dir="$(opencode_agents_dir)"
        for agent in "$agents_dir"/*.md; do
          [[ -f "$agent" && ! -L "$agent" ]] || continue
          rebase_owned_file_path "$agent" "$AGENT_MARKER"
        done
        ;;
    esac
  done < <(resolve_targets)

  payloads_dir="$(instruction_payloads_dir)"
  for name in \
    30-python.md \
    70-code-review-conventions.md \
    80-agent-pipelines.md \
    85-agent-scripts.md; do
    rebase_owned_file_path "$payloads_dir/$name" "$(instruction_payload_marker)"
  done
  rebase_owned_file_path "$payloads_dir/python_init_context.py" \
    '# managed-by: fabiandistler/agents install.sh'
}
