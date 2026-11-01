# shellcheck shell=bash
# Sourced by install.sh. main() applies the selection to each target; check_main() reports drift.

main() {
  local skills
  [[ -n "$RESOLVED_TARGETS" ]] || RESOLVED_TARGETS="$(resolve_targets)"
  skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT (env=$ENV, category=$CATEGORY)" >&2
    exit 1
  fi
  rebase_managed_repo_paths
  local routed
  routed="$(routed_categories)"
  [[ "$ENV" != "all" ]] && printf 'env filter: %s\n' "$ENV"
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"
  if [[ -n "$FILTER_FLAGS" ]] && target_is_selected claude; then
    printf '  WARN      %s: no effect for claude (its skills come from the plugin marketplace)\n' \
      "${FILTER_FLAGS# }" >&2
  fi

  if ((INSTRUCTIONS && UNINSTALL == 0)); then
    CHECK_CURRENT_TARGET=all
    install_instruction_payloads
  fi

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    # shellcheck disable=SC2034  # check_record (selection.sh) reads it
    CHECK_CURRENT_TARGET="$target"
    if [[ "$target" == "claude" ]]; then
      printf 'claude: skills, commands and subagents come from the plugin marketplace\n'
      migrate_claude_to_plugins
      ((UNINSTALL)) || printf '  note      claude: claude plugin marketplace add %s\n' "$MARKETPLACE"
    else
      printf '%s: %s\n' "$target" "$(target_dir_for "$target")"
      sync_skill_links "$target" "$skills" "$routed"
    fi
    if [[ "$target" == "codex" ]]; then
      cleanup_codex_skills_legacy
      cleanup_codex_prompts_legacy "$skills"
      # Runs on both paths: an upgrade must drop a managed block left by a
      # version that still registered the knowledge-base MCP servers.
      remove_legacy_codex_mcp
      prune_stale_codex_agents
      if ((UNINSTALL)); then
        uninstall_codex_agents
        remove_codex_member_overrides
      else
        install_codex_agents
        install_codex_member_overrides < <(codex_routed_members "$(target_dir_for codex)" "$skills")
      fi
      ((CHECK_MODE)) && check_codex_guard_hooks
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
      cleanup_opencode_legacy_commands "$skills"
      prune_stale_opencode_agents
      if ((UNINSTALL)); then
        uninstall_opencode_agents
      else
        install_opencode_agents
      fi
    fi
    if ((INSTRUCTIONS)); then
      if ((UNINSTALL)); then
        remove_instructions "$target"
        if [[ "$target" == "claude" ]]; then
          remove_claude_rules
          remove_claude_python_hook
        fi
      else
        install_instructions "$target"
        if [[ "$target" == "claude" ]]; then
          install_claude_rules
          install_claude_python_hook
        fi
      fi
    fi
    for guard in $GUARDS; do
      if ((UNINSTALL)); then
        uninstall_guard "$guard" "$target"
      else
        install_guard "$guard" "$target"
      fi
    done
  done < <(resolve_targets)

  if ((INSTRUCTIONS && UNINSTALL)); then
    prune_instruction_payloads
  fi
}

check_result() {
  local missing=0 stale=0 foreign=0 duplicate=0 untrusted=0
  local target kind path state output_dir tsv
  # shellcheck disable=SC2034  # kind and path only skip their fields
  while IFS=$'\t' read -r target kind path state; do
    case "$state" in
      missing) missing=$((missing + 1)) ;;
      stale) stale=$((stale + 1)) ;;
      foreign) foreign=$((foreign + 1)) ;;
      duplicate) duplicate=$((duplicate + 1)) ;;
      untrusted-hook) untrusted=$((untrusted + 1)) ;;
    esac
  done <<<"$CHECK_ROWS"

  if ((CHECK_OUTPUT_SET)); then
    [[ ! -L "$CHECK_OUTPUT" ]] || {
      echo "--output must not be a symlink: $CHECK_OUTPUT" >&2
      return 1
    }
    [[ ! -d "$CHECK_OUTPUT" ]] || {
      echo "--output must be a file: $CHECK_OUTPUT" >&2
      return 1
    }
    output_dir="${CHECK_OUTPUT%/*}"
    [[ "$output_dir" != "$CHECK_OUTPUT" ]] || output_dir=.
    [[ -d "$output_dir" ]] || {
      echo "--output directory does not exist: $output_dir" >&2
      return 1
    }
    tsv=$'target\tkind\tpath\tstate\n'
    tsv+="$CHECK_ROWS"
    write_file_atomic "$CHECK_OUTPUT" "${tsv%$'\n'}"
  fi

  if [[ -z "$CHECK_ROWS" ]]; then
    printf '%s\n' '--check: clean'
    return 0
  fi
  printf -- '--check: drift (missing=%d stale=%d foreign=%d duplicate=%d untrusted-hook=%d)\n' \
    "$missing" "$stale" "$foreign" "$duplicate" "$untrusted"
  return 3
}

check_main() {
  main >/dev/null
  ((GIT_HOOK)) && check_git_hooks
  check_result
}
