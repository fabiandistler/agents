#!/usr/bin/env bats
# install.sh: linking skills per target, migrations from older layouts,
# router members, and pruning links to dropped skills.

load install_helper

setup() {
  install_setup
}

@test "the catalogue has auto and command skills to count" {
  [[ "$(skill_count)" -ge 1 ]] || fail "no skills detected in repo"
  [[ "$(command_count all)" -ge 1 ]] || fail "no command skills detected in repo"
}

@test "dry-run creates no files" {
  # dry-run for --target=all should not create anything.
  HOME_DRY="$(mktemp -d)"
  dry_output="$(HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run 2>&1)"
  [[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
  [[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
  [[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
  [[ "$(grep -c '^\[dry-run\] write .*/\.codex/agents/.*\.toml$' <<<"$dry_output")" -eq 2 ]] ||
    fail "dry-run agent writes were not one target-only line each"
}

@test "all install populates codex and opencode; unchanged links retain their inode" {
  # install --target=all populates codex and opencode only. Both runtimes
  # install command skills in their normal skills roots.
  CODEX_SKILLS_EXPECTED=$(($(skill_count all codex) + $(command_count all codex)))
  OPENCODE_ONLY_EXPECTED="$(opencode_only_expected)"
  HOME_A="$(mktemp -d)"
  HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
  [[ ! -e "$HOME_A/.claude" ]] || fail "all install created ~/.claude"
  got="$(count_links "$HOME_A/.config/opencode/skills")"
  [[ "$got" -eq "$OPENCODE_ONLY_EXPECTED" ]] ||
    fail "all install: opencode skills has $got links, expected $OPENCODE_ONLY_EXPECTED"
  got="$(count_links "$HOME_A/.agents/skills")"
  [[ "$got" -eq "$CODEX_SKILLS_EXPECTED" ]] ||
    fail "all install: .agents/skills has $got links, expected $CODEX_SKILLS_EXPECTED"
  [[ ! -e "$HOME_A/.config/opencode/command" ]] ||
    fail "all install created the legacy OpenCode command directory"
  [[ -L "$HOME_A/.agents/skills/repo-status" ]] || fail "codex: command skill repo-status not linked into skills/"
  [[ -f "$HOME_A/.agents/skills/repo-status/agents/openai.yaml" ]] ||
    fail "codex: command skill repo-status missing its openai.yaml sidecar"
  [[ ! -e "$HOME_A/.codex/prompts/repo-status.md" ]] || fail "codex: command skill repo-status leaked into deprecated prompts/"
  documentation_link="$HOME_A/.agents/skills/documentation"
  link_inode_before="$(stat -c %i "$documentation_link")"
  reinstall_output="$(HOME="$HOME_A" "$INSTALL" --target=all 2>&1)"
  [[ "$(stat -c %i "$documentation_link")" == "$link_inode_before" ]] ||
    fail "reinstall replaced an unchanged skill link"
  grep -q '^  ok .*\.agents/skills/documentation' <<<"$reinstall_output" ||
    fail "reinstall did not report the unchanged skill link as ok"
}

@test "all uninstall removes command skills from the normal skill roots" {
  # --uninstall removes command-skill links from the normal skill roots.
  HOME_A="$(mktemp -d)"
  HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
  HOME="$HOME_A" "$INSTALL" --target=all --uninstall >/dev/null
  [[ ! -e "$HOME_A/.agents/skills/repo-status" ]] || fail "codex uninstall left command skill repo-status behind"
  [[ ! -e "$HOME_A/.config/opencode/skills/repo-status" ]] ||
    fail "OpenCode uninstall left command skill repo-status in skills/"
}

@test "unchanged skill links keep their inode" {
  # re-running an install keeps the existing skill symlink inode.
  HOME_LINK_IDEM="$(mktemp -d)"
  HOME="$HOME_LINK_IDEM" "$INSTALL" --target=opencode --category=workflow >/dev/null
  IDEM_LINK="$HOME_LINK_IDEM/.config/opencode/skills/natural-planning"
  link_inode_before="$(file_inode "$IDEM_LINK")"
  link_output="$(HOME="$HOME_LINK_IDEM" "$INSTALL" --target=opencode --category=workflow 2>&1)"
  [[ "$(file_inode "$IDEM_LINK")" == "$link_inode_before" ]] ||
    fail "reinstall rewrote an unchanged skill link"
  grep -q '  ok .*natural-planning' <<<"$link_output" ||
    fail "reinstall did not report the unchanged skill link as ok"
}

@test "dry-run plans each write as one normalized line" {
  # each planned write uses one normalized dry-run line.
  oc_dry="$(HOME="$(mktemp -d)" "$INSTALL" --target=all --dry-run 2>&1)"
  dry_action_lines="$(grep '^\[dry-run\]' <<<"$oc_dry")"
  if grep -Ev '^\[dry-run\] (link|write|remove) .+$' <<<"$dry_action_lines" >/dev/null; then
    fail "dry-run emitted a non-normalized action line"
  fi
  if grep -Eq '^  (linked|removed|updated|agent) ' <<<"$oc_dry"; then
    fail "dry-run emitted a second write status line"
  fi
  [[ "$(grep -c '^\[dry-run\] write .*/\.codex/agents/.*\.toml$' <<<"$oc_dry")" -eq 2 ]] ||
    fail "dry-run did not report each agent TOML write once"
}

@test "codex install cleans the deprecated prompts dir" {
  # codex install migrates our symlinks out of the deprecated prompts dir
  # (~/.codex/prompts) while preserving foreign entries there.
  HOME_CX="$(mktemp -d)"
  legacy_prompts="$HOME_CX/.codex/prompts"
  mkdir -p "$legacy_prompts"
  first_command=""
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    skill_is_command "$d" || continue
    first_command="$(basename "$d")"
    break
  done
  [[ -n "$first_command" ]] || fail "no command skill found for codex prompts migration test"
  ln -s "$REPO_ROOT/skills/$first_command/SKILL.md" "$legacy_prompts/$first_command.md"
  foreign_prompt_src="$(mktemp -d)/foreign-prompt.md"
  : >"$foreign_prompt_src"
  ln -s "$foreign_prompt_src" "$legacy_prompts/foreign-prompt.md"
  HOME="$HOME_CX" "$INSTALL" --target=codex >/dev/null
  [[ ! -L "$legacy_prompts/$first_command.md" ]] || fail "deprecated codex prompt for $first_command not migrated"
  [[ -L "$legacy_prompts/foreign-prompt.md" ]] || fail "codex prompt cleanup removed a foreign symlink"
}

@test "codex links into ~/.agents/skills and migrates out of ~/.codex/skills" {
  # codex links into ~/.agents/skills (#565) and migrates our links out of the
  # deprecated ~/.codex/skills, still-valid and dangling ones alike, whatever
  # --category says; foreign entries there survive, and a dry-run keeps all.
  HOME_CXS="$(mktemp -d)"
  legacy_skills="$HOME_CXS/.codex/skills"
  mkdir -p "$legacy_skills/hand-made"
  ln -s "$REPO_ROOT/skills/documentation" "$legacy_skills/documentation"
  ln -s "$REPO_ROOT/skills/architecture" "$legacy_skills/architecture"
  ln -s "$REPO_ROOT/skills/removed-skill" "$legacy_skills/removed-skill"
  foreign_codex_skill="$(mktemp -d)/foreign-skill"
  mkdir "$foreign_codex_skill"
  ln -s "$foreign_codex_skill" "$legacy_skills/foreign-skill"
  HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication --dry-run >/dev/null
  [[ -L "$legacy_skills/documentation" ]] || fail "dry-run migrated a ~/.codex/skills link"
  HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication >/dev/null
  for name in documentation architecture removed-skill; do
    [[ ! -L "$legacy_skills/$name" ]] || fail "our ~/.codex/skills/$name link was not migrated"
  done
  [[ -L "$legacy_skills/foreign-skill" ]] || fail "codex migration removed a foreign symlink"
  [[ -d "$legacy_skills/hand-made" ]] || fail "codex migration removed a foreign directory"
  [[ -L "$HOME_CXS/.agents/skills/documentation" ]] || fail "codex did not link into ~/.agents/skills"
  ln -s "$REPO_ROOT/skills/documentation" "$legacy_skills/documentation"
  HOME="$HOME_CXS" "$INSTALL" --target=codex --category=communication --uninstall >/dev/null
  [[ ! -L "$legacy_skills/documentation" ]] || fail "codex uninstall left our ~/.codex/skills link"
  [[ ! -e "$HOME_CXS/.agents/skills/documentation" ]] || fail "codex uninstall left ~/.agents/skills link"
}

@test "name collisions in ~/.agents/skills warn and keep the foreign entry" {
  # other tools write to ~/.agents/skills too: a name already taken there is
  # warned about and left alone, never overwritten (#565).
  HOME_COL="$(mktemp -d)"
  mkdir -p "$HOME_COL/.agents/skills/documentation"
  printf 'theirs\n' >"$HOME_COL/.agents/skills/documentation/SKILL.md"
  foreign_tldr="$(mktemp -d)/tldr"
  mkdir "$foreign_tldr"
  ln -s "$foreign_tldr" "$HOME_COL/.agents/skills/tldr"
  col_err="$(HOME="$HOME_COL" "$INSTALL" --target=codex --category=communication 2>&1 >/dev/null)"
  grep -Fxq 'theirs' "$HOME_COL/.agents/skills/documentation/SKILL.md" ||
    fail "codex install overwrote a foreign skill in ~/.agents/skills"
  [[ "$(readlink "$HOME_COL/.agents/skills/tldr")" == "$foreign_tldr" ]] ||
    fail "codex install replaced a foreign symlink in ~/.agents/skills"
  grep -q 'WARN.*agents/skills/documentation' <<<"$col_err" ||
    fail "no warning for the name collision on documentation"
  grep -q 'WARN.*agents/skills/tldr' <<<"$col_err" ||
    fail "no warning for the name collision on tldr"
  [[ -L "$HOME_COL/.agents/skills/communication-analysis" ]] ||
    fail "a collision stopped the remaining codex links"
}

@test "routed category registers only its router; members ride nested" {
  # A routed category links only its router at top level; the auto members
  # ride nested under the router's members/ dir (readable, not registered),
  # and none of them leak into the skills directory.
  HOME_ROUTED="$(mktemp -d)"
  HOME="$HOME_ROUTED" "$INSTALL" --target=opencode --category=architecture >/dev/null
  ROUTED_SKILLS="$HOME_ROUTED/.config/opencode/skills"
  [[ -L "$ROUTED_SKILLS/architecture" ]] || fail "router 'architecture' not linked"
  [[ -f "$ROUTED_SKILLS/architecture/SKILL.md" ]] || fail "router SKILL.md not readable"
  [[ "$(count_links "$ROUTED_SKILLS")" -eq 1 ]] ||
    fail "routed category linked more than the router at top level"
  # A representative member resolves through the router's members/ dir ...
  [[ -f "$ROUTED_SKILLS/architecture/members/coupling-cohesion/SKILL.md" ]] ||
    fail "nested member coupling-cohesion not readable via the router"
  # ... but is never registered as its own top-level skill.
  for member in c4-modeling coupling-cohesion ddd; do
    [[ ! -e "$ROUTED_SKILLS/$member" ]] ||
      fail "routed member $member leaked into the skills directory"
  done
  HOME="$HOME_ROUTED" "$INSTALL" --target=opencode --category=architecture --uninstall >/dev/null
  [[ ! -e "$ROUTED_SKILLS/architecture" ]] || fail "uninstall left the router behind"
}

@test "pre-router flat member links are cleaned up on install and uninstall" {
  # Migration from a pre-router install: members used to be linked flat at
  # top level. Those links still resolve, so the dangling-link prune cannot
  # catch them — install must unlink them explicitly, or the members keep
  # registering alongside the router. Foreign entries must survive.
  HOME_MIG="$(mktemp -d)"
  MIG_SKILLS="$HOME_MIG/.config/opencode/skills"
  mkdir -p "$MIG_SKILLS"
  mig_members=""
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    [[ "$(skill_dir_category "$d")" == "architecture" ]] || continue
    skill_is_nested_member "$d" || continue
    name="$(basename "$d")"
    ln -s "$REPO_ROOT/skills/$name" "$MIG_SKILLS/$name"
    mig_members+="$name"$'\n'
  done
  [[ -n "$mig_members" ]] || fail "no nested architecture members found for the migration test"
  mig_foreign="$(mktemp -d)/foreign"
  mkdir "$mig_foreign"
  ln -s "$mig_foreign" "$MIG_SKILLS/foreign-skill"
  HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture >/dev/null
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    [[ ! -e "$MIG_SKILLS/$name" ]] ||
      fail "pre-router flat link for $name survived the upgrade"
  done <<<"$mig_members"
  [[ -L "$MIG_SKILLS/architecture" ]] || fail "migration did not link the router"
  [[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "migration removed a foreign symlink"
  # ... and --uninstall clears the flat links too, not just the router.
  HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture >/dev/null
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    ln -s "$REPO_ROOT/skills/$name" "$MIG_SKILLS/$name"
  done <<<"$mig_members"
  HOME="$HOME_MIG" "$INSTALL" --target=opencode --category=architecture --uninstall >/dev/null
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    [[ ! -e "$MIG_SKILLS/$name" ]] || fail "uninstall left the pre-router flat link for $name"
  done <<<"$mig_members"
  [[ -L "$MIG_SKILLS/foreign-skill" ]] || fail "uninstall removed a foreign symlink"
}

@test "install prunes dangling links to skills the repo dropped" {
  # A dangling symlink left by a skill the repo no longer ships is pruned;
  # foreign and still-valid links are left alone.
  HOME_STALE="$(mktemp -d)"
  HOME="$HOME_STALE" "$INSTALL" --target=opencode --category=communication >/dev/null
  STALE_SKILLS="$HOME_STALE/.config/opencode/skills"
  ln -s "$REPO_ROOT/skills/removed-skill" "$STALE_SKILLS/removed-skill"
  foreign_dangling="$(mktemp -d)/gone"
  ln -s "$foreign_dangling" "$STALE_SKILLS/foreign-dangling"
  HOME="$HOME_STALE" "$INSTALL" --target=opencode --category=communication >/dev/null
  [[ ! -L "$STALE_SKILLS/removed-skill" ]] || fail "stale link for a removed skill survived"
  [[ -L "$STALE_SKILLS/foreign-dangling" ]] || fail "prune removed a foreign dangling symlink"
  [[ -L "$STALE_SKILLS/documentation" ]] || fail "prune removed a valid skill link"
}
