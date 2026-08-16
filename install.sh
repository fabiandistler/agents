#!/usr/bin/env bash
# Symlink the skills in this repo into the conventional install paths
# for popular coding agents. Idempotent; reversible via --uninstall.
#
# Usage:
#   ./install.sh --target=claude              # ~/.claude/skills/<skill>
#   ./install.sh --target=codex               # ~/.codex/skills/<skill>
#   ./install.sh --target=opencode            # ~/.config/opencode/skills/<skill>
#   ./install.sh --target=all                 # all of the above
#   ./install.sh --target=all --dry-run       # show what would happen
#   ./install.sh --target=all --uninstall     # remove symlinks owned by us
#   ./install.sh --target=claude --env=chat   # only chat skills
#   ./install.sh --target=codex  --env=coding # only coding skills
#   ./install.sh --target=claude --category=architecture,refactoring
#
# --env=coding|chat|all (default all) selects which skills to (un)install,
# based on each skill's `environments:` frontmatter field. A skill with no
# such field belongs to every environment.
#
# --category=<name>[,<name>...] (default all) further narrows the selection
# to skills whose `category:` frontmatter field matches one of the given
# categories. Combinable with --env.
#
# A skill may also restrict itself to some agents with a `targets:` frontmatter
# field (comma-separated subset of claude, codex, opencode; absent means all).
# A skill that excludes a target is never linked there, and an existing link we
# own is removed on the next install — `skill-creator` uses this to stay out of
# Claude, which ships its own.
#
# Skills with `activation: command` in their frontmatter are user-invoked,
# not model-triggered. For claude and opencode they are linked into the
# target's command directory (~/.claude/commands, ~/.config/opencode/command)
# as <name>.md instead of the skills directory, keeping them out of the
# auto-trigger metadata. Codex custom prompts (~/.codex/prompts) are
# deprecated, so under codex these skills install into the skills directory
# like any other; their agents/openai.yaml sidecar
# (policy.allow_implicit_invocation: false) keeps Codex from auto-triggering
# them, so they stay explicit-only. --uninstall reverses this, and codex
# installs also remove any leftover ~/.codex/prompts symlinks we created.
#
# A category may ship a router skill (`activation: router`, named after the
# category). Its auto skills are nested under the router's members/ dir, so
# only the router is linked at top level; the members load lazily when the
# router routes to them, keeping the category to a single trigger entry. The
# nested members are never linked flat; a flat link left by a pre-router
# install is removed, on both the install and the uninstall path.
# Claude registers only top-level skills, so the members stay hidden there.
# Codex, however, discovers skills recursively and follows symlinks
# (openai/codex#22275), so it would register each nested members/<name>/SKILL.md
# as its own skill. To preserve the router's progressive disclosure under codex,
# install additionally disables every nested member by name in
# ~/.codex/config.toml via a managed [[skills.config]] block (enabled = false),
# which drops them from the model's skill list; --uninstall removes the block.
#
# The codex target additionally installs the full plugins, not just the
# skills. Requires python3 (skipped with a warning otherwise); --uninstall
# reverses both. --env only filters skills; the plugin extras follow
# --category:
#   - Each selected plugin's subagents (plugins/<category>/agents/*.md) are
#     converted to Codex custom agents in ~/.codex/agents/<name>.toml.
#
# Conservative behaviour:
#   - Existing correct symlink:        skip (idempotent).
#   - Symlink pointing elsewhere:      skip with a warning, never overwrite.
#   - Regular file or non-empty dir:   skip with a warning, never overwrite.
#   - Uninstall only removes a symlink whose target is a path inside this
#     repo, so foreign files at that location are never touched.
#   - Both install and uninstall prune dangling symlinks left over from
#     skills this repo no longer ships, again only when the (now missing)
#     target was inside this repo.
#   - Earlier versions registered knowledge-base MCP servers in
#     ~/.codex/config.toml. They are gone; install and uninstall both strip
#     any leftover managed block and its runtime venv. Only our own marker
#     block is touched — a foreign [mcp_servers.<name>] table survives, and
#     hand-edited unbalanced markers leave the whole file alone.
#   - Generated agent files carry a marker comment; a file at the same path
#     without the marker is never overwritten, and uninstall only removes
#     marker-carrying files.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

DRY_RUN=0
UNINSTALL=0
TARGET=""
ENV="all"
CATEGORY="all"

# Must match the category list in scripts/build_manifest.py.
CATEGORIES="architecture refactoring ai-ml workflow communication personal"

usage() { sed -n '2,53p' "$0"; }

for arg in "$@"; do
  case "$arg" in
    --target=*)   TARGET="${arg#--target=}" ;;
    --env=*)      ENV="${arg#--env=}" ;;
    --category=*) CATEGORY="${arg#--category=}" ;;
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

case "$ENV" in
  all|coding|chat) ;;
  *) echo "invalid --env=$ENV (expected coding|chat|all)" >&2; usage >&2; exit 2 ;;
esac

if [[ "$CATEGORY" != "all" ]]; then
  IFS=',' read -ra _cats <<< "$CATEGORY"
  for c in "${_cats[@]}"; do
    c="${c//[[:space:]]/}"
    [[ -n "$c" ]] || continue
    if [[ " $CATEGORIES " != *" $c "* ]]; then
      echo "invalid --category=$c (expected one of: ${CATEGORIES// /|}|all)" >&2
      usage >&2
      exit 2
    fi
  done
fi

target_dir_for() {
  case "$1" in
    claude)   printf '%s/.claude/skills\n'        "$HOME" ;;
    codex)    printf '%s/.codex/skills\n'         "$HOME" ;;
    opencode) printf '%s/.config/opencode/skills\n' "$HOME" ;;
    *) echo "unknown target: $1" >&2; return 1 ;;
  esac
}

# Where each target discovers user-invoked commands. `activation: command`
# skills go here (as <name>.md) instead of the skills directory.
target_command_dir_for() {
  case "$1" in
    claude)   printf '%s/.claude/commands\n'         "$HOME" ;;
    opencode) printf '%s/.config/opencode/command\n' "$HOME" ;;
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

# Read the comma-separated `environments:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_environments() {
  local skill_md="$1" line
  line="$(grep -m1 '^environments:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#environments:}"
}

# True if a skill belongs to the requested environment. A skill with no
# `environments:` field belongs to every environment.
skill_matches_env() {
  local skill_md="$1" want="$2" envs
  [[ "$want" == "all" ]] && return 0
  envs="$(skill_environments "$skill_md")"
  [[ -z "${envs//[[:space:]]/}" ]] && return 0
  local IFS=','
  for e in $envs; do
    e="${e//[[:space:]]/}"
    [[ "$e" == "$want" ]] && return 0
  done
  return 1
}

# Read the comma-separated `targets:` frontmatter value of a SKILL.md.
# Prints the raw value (may be empty if the field is absent).
skill_targets() {
  local skill_md="$1" line
  line="$(grep -m1 '^targets:' "$skill_md" 2>/dev/null || true)"
  printf '%s' "${line#targets:}"
}

# True if a skill should be installed for the given target. A skill with no
# `targets:` field belongs to every target.
skill_matches_target() {
  local skill_md="$1" want="$2" targets
  targets="$(skill_targets "$skill_md")"
  [[ -z "${targets//[[:space:]]/}" ]] && return 0
  local IFS=','
  for t in $targets; do
    t="${t//[[:space:]]/}"
    [[ "$t" == "$want" ]] && return 0
  done
  return 1
}

# Read the `activation:` frontmatter value of a SKILL.md. Prints `command`
# for user-invoked skills, `router` for a per-category router skill, `auto`
# otherwise (the default when absent).
skill_activation() {
  local skill_md="$1" line act
  line="$(grep -m1 '^activation:' "$skill_md" 2>/dev/null || true)"
  act="${line#activation:}"
  act="${act//[[:space:]]/}"
  case "$act" in
    command) printf 'command' ;;
    router)  printf 'router' ;;
    *)       printf 'auto' ;;
  esac
}

# Print the `category:` frontmatter value of a SKILL.md (empty if absent).
skill_category() {
  local skill_md="$1" line cat
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  printf '%s' "${cat//[[:space:]]/}"
}

# Space-padded list of categories that ship a router skill (activation:
# router). A routed category's auto skills are nested under the router's
# members/ dir, so install.sh links only the router and skips the members.
routed_categories() {
  local out=" "
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    if [[ "$(skill_activation "$d/SKILL.md")" == "router" ]]; then
      out+="$(skill_category "$d/SKILL.md") "
    fi
  done
  printf '%s' "$out"
}

# True if a skill's `category:` frontmatter matches the requested filter.
# `all` matches everything; a skill without the field only matches `all`.
skill_matches_category() {
  local skill_md="$1" want="$2" line cat
  [[ "$want" == "all" ]] && return 0
  line="$(grep -m1 '^category:' "$skill_md" 2>/dev/null || true)"
  cat="${line#category:}"
  cat="${cat//[[:space:]]/}"
  [[ -n "$cat" ]] || return 1
  [[ ",${want// /}," == *",$cat,"* ]]
}

list_skills() {
  # A directory under skills/ is a skill iff it contains SKILL.md.
  for d in "$REPO_ROOT"/skills/*/; do
    local name; name="$(basename "$d")"
    [[ -f "$d/SKILL.md" ]] || continue
    skill_matches_env "$d/SKILL.md" "$ENV" || continue
    skill_matches_category "$d/SKILL.md" "$CATEGORY" || continue
    printf '%s\n' "$name"
  done
}

# --- Legacy Codex MCP cleanup ----------------------------------------------
#
# Earlier versions registered each plugin's knowledge-base MCP server in
# ~/.codex/config.toml between marker comments, backed by a runtime venv at a
# fixed path. Those servers are gone — the skills' references/ pages are read
# directly now — so both install and uninstall strip whatever a previous
# version left behind. Install has to do it too: an upgrade would otherwise
# keep Codex pointing at a server script this repo no longer ships.

codex_config_path() { printf '%s/.codex/config.toml' "$HOME"; }

# Categories that ever shipped an .mcp.json. Hardcoded, because the files this
# list was once derived from no longer exist.
LEGACY_MCP_CATEGORIES="architecture refactoring"

codex_mcp_runtime_dir() { printf '%s/.codex/agents-mcp-runtime' "$HOME"; }

mcp_begin_marker() {
  printf '# >>> agents:%s MCP servers (managed by install.sh, do not edit) >>>' "$1"
}

mcp_end_marker() {
  printf '# <<< agents:%s MCP servers <<<' "$1"
}

# True if stdin's marker lines for a category are absent or form properly
# nested begin/end pairs. A hand-edited config with a dangling begin or end
# marker must not be stripped: strip_mcp_block would silently drop
# everything from the begin marker to end of file.
mcp_markers_balanced() {
  awk -v b="$(mcp_begin_marker "$1")" -v e="$(mcp_end_marker "$1")" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the marker block (inclusive) for a category, plus
# the separator blank line before it and any blank lines left at the start
# of the file (so reinstalls do not accumulate or shuffle blank lines).
# Blank lines are held back one step and only flushed once the next line
# turns out not to be our begin marker.
strip_mcp_block() {
  awk -v b="$(mcp_begin_marker "$1")" -v e="$(mcp_end_marker "$1")" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Drop every managed MCP block a previous version wrote, plus the runtime venv
# it provisioned. Foreign [mcp_servers.*] tables live outside our markers and
# are never touched; a hand-edited unbalanced marker pair leaves the file alone.
remove_legacy_codex_mcp() {
  local config; config="$(codex_config_path)"
  local cat before after
  if [[ -f "$config" ]]; then
    for cat in $LEGACY_MCP_CATEGORIES; do
      before="$(cat "$config")"
      if ! mcp_markers_balanced "$cat" <<< "$before"; then
        printf '  WARN      unbalanced %s marker lines in %s (leaving it untouched)\n' \
          "$cat" "$config" >&2
        continue
      fi
      after="$(strip_mcp_block "$cat" <<< "$before")"
      [[ "$after" != "$before" ]] || continue
      if (( DRY_RUN )); then
        printf '[dry-run] remove legacy %s MCP servers from %s\n' "$cat" "$config"
        continue
      fi
      if [[ -n "$after" ]]; then
        printf '%s\n' "$after" > "$config"
      else
        : > "$config"
      fi
      printf '  removed   legacy %s MCP servers from %s\n' "$cat" "$config"
    done
  fi

  local venv; venv="$(codex_mcp_runtime_dir)"
  if [[ -d "$venv" ]]; then
    if (( DRY_RUN )); then
      printf '[dry-run] remove legacy MCP runtime venv %s\n' "$venv"
    else
      rm -rf "$venv"
      printf '  removed   legacy MCP runtime venv %s\n' "$venv"
    fi
  fi
}

# --- Codex routed-member skill overrides -----------------------------------
#
# Codex discovers skills by scanning its skill roots recursively and following
# symlinks (openai/codex#22275), so the sub-skills nested under a router's
# members/ dir get registered as independent skills — defeating the router's
# progressive disclosure. (Claude registers only top-level skills, so it is
# unaffected.) To keep the members hidden under codex, disable each nested
# member by name in ~/.codex/config.toml via a [[skills.config]] entry
# (enabled = false), which drops it from the model's skill list. The block is
# marker-delimited so install and uninstall stay idempotent and never touch
# config we do not own.

skill_override_begin_marker() {
  printf '# >>> agents routed-member skill overrides (managed by install.sh, do not edit) >>>'
}

skill_override_end_marker() {
  printf '# <<< agents routed-member skill overrides <<<'
}

# True if stdin's override marker lines are absent or form a properly nested
# begin/end pair (see mcp_markers_balanced for the rationale).
skill_override_markers_balanced() {
  awk -v b="$(skill_override_begin_marker)" -v e="$(skill_override_end_marker)" '
    $0 == b { if (open) bad = 1; open = 1; next }
    $0 == e { if (!open) bad = 1; open = 0; next }
    END { exit (bad || open) ? 1 : 0 }
  '
}

# Filter stdin, dropping the override marker block (inclusive) and normalising
# surrounding blank lines (see strip_mcp_block).
strip_skill_override_block() {
  awk -v b="$(skill_override_begin_marker)" -v e="$(skill_override_end_marker)" '
    $0 == b { skip = 1; pending = 0; next }
    $0 == e { skip = 0; next }
    skip { next }
    $0 == "" { if (pending && printed) print ""; pending = 1; next }
    { if (pending && printed) print ""; pending = 0; print; printed = 1 }
  '
}

# Render one [[skills.config]] disable table per member name read on stdin.
render_skill_override_toml() {
  local name first=1
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if [[ ! "$name" =~ ^[A-Za-z0-9_-]+$ ]]; then
      printf '  WARN      skill name %q is not a bare identifier (skipping override)\n' \
        "$name" >&2
      continue
    fi
    (( first )) || printf '\n'
    first=0
    printf '[[skills.config]]\nname = "%s"\nenabled = false\n' "$name"
  done
}

# Strip our override block from ~/.codex/config.toml (leaving foreign config).
remove_codex_member_overrides() {
  local config; config="$(codex_config_path)"
  [[ -f "$config" ]] || return 0
  local before after
  before="$(cat "$config")"
  if ! skill_override_markers_balanced <<< "$before"; then
    printf '  WARN      unbalanced skill-override marker lines in %s (leaving it untouched)\n' \
      "$config" >&2
    return 0
  fi
  after="$(strip_skill_override_block <<< "$before")"
  [[ "$after" != "$before" ]] || return 0
  if (( DRY_RUN )); then
    printf '[dry-run] remove routed-member skill overrides from %s\n' "$config"
    return 0
  fi
  if [[ -n "$after" ]]; then
    printf '%s\n' "$after" > "$config"
  else
    : > "$config"
  fi
  printf '  removed   routed-member skill overrides from %s\n' "$config"
}

# Write the managed override block that disables the nested router members
# named on stdin (one per line). With no names, any stale block is removed.
# Uses only shell built-ins and the same core tools as the rest of install.sh
# (no sort/wc/tr) so it works under the minimal sandboxed PATH.
install_codex_member_overrides() {
  local config; config="$(codex_config_path)"
  local members="" count=0 name
  while IFS= read -r name; do
    [[ -n "${name//[[:space:]]/}" ]] || continue
    members+="$name"$'\n'
    count=$((count + 1))
  done
  if [[ -z "$members" ]]; then
    remove_codex_member_overrides
    return 0
  fi
  if (( DRY_RUN )); then
    remove_codex_member_overrides
    printf '[dry-run] disable %s routed member skills in %s\n' "$count" "$config"
    return 0
  fi
  mkdir -p "$(dirname "$config")"
  [[ -f "$config" ]] || : > "$config"
  if ! skill_override_markers_balanced < "$config"; then
    printf '  WARN      unbalanced skill-override marker lines in %s (leaving it untouched)\n' \
      "$config" >&2
    return 0
  fi
  local rest toml
  rest="$(strip_skill_override_block < "$config")"
  toml="$(printf '%s' "$members" | render_skill_override_toml)"
  {
    if [[ -n "$rest" ]]; then printf '%s\n\n' "$rest"; fi
    skill_override_begin_marker; printf '\n'
    printf '%s\n' "$toml"
    skill_override_end_marker; printf '\n'
  } > "$config.tmp.$$"
  mv "$config.tmp.$$" "$config"
  printf '  skills    %s routed members disabled in %s\n' "$count" "$config"
}

# --- Codex custom agent registration ----------------------------------------
#
# Claude loads plugins/<category>/agents/*.md natively; Codex CLI discovers
# custom agents as TOML files under ~/.codex/agents/ instead. Each agent's
# frontmatter name/description and Markdown body (its system prompt) are
# converted to a generated <name>.toml carrying a marker comment, so install
# and uninstall never touch files we did not generate. The `tools:` and
# `model:` frontmatter fields have no Codex equivalent and are dropped
# (model and sandbox are inherited from the parent session).

codex_agents_dir() { printf '%s/.codex/agents' "$HOME"; }

AGENT_MARKER='# generated by fabiandistler/agents install.sh; do not edit'

# Categories selected by --category that ship subagents.
agent_categories() {
  local c
  if [[ "$CATEGORY" == "all" ]]; then
    for c in $CATEGORIES; do
      if compgen -G "$REPO_ROOT/plugins/$c/agents/*.md" >/dev/null; then
        printf '%s\n' "$c"
      fi
    done
  else
    local IFS=','
    for c in $CATEGORY; do
      c="${c//[[:space:]]/}"
      if [[ -n "$c" ]] && compgen -G "$REPO_ROOT/plugins/$c/agents/*.md" >/dev/null; then
        printf '%s\n' "$c"
      fi
    done
  fi
  return 0
}

# Render one agents/<name>.md as a Codex custom-agent TOML file, with
# ${CLAUDE_PLUGIN_ROOT} resolved to the plugin directory in this repo.
plugin_agent_toml() {
  local md="$1" plugin_dir="$2" marker="$3"
  python3 - "$md" "$plugin_dir" "$marker" <<'PY'
import json
import sys
from pathlib import Path

try:
    md_path, plugin_dir, marker = sys.argv[1], sys.argv[2], sys.argv[3]
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    if lines[0].strip() != "---":
        raise ValueError("missing frontmatter")
    close = lines[1:].index("---") + 1
    body = "\n".join(lines[close + 1 :]).strip()
    if not body:
        raise ValueError("empty agent body")

    # Minimal YAML subset: `key: value` plus `key: >-` folded blocks whose
    # continuation lines are indented; folded newlines become spaces.
    fm: dict[str, str] = {}
    key = None
    parts: list[str] = []

    def flush():
        if key is not None:
            fm[key] = " ".join(p.strip() for p in parts if p.strip())

    for line in lines[1:close]:
        if line[:1] in (" ", "\t") and key is not None:
            parts.append(line)
            continue
        flush()
        k, _, v = line.partition(":")
        key, parts = k.strip(), [v.replace(">-", "", 1) if v.strip() == ">-" else v]
    flush()

    name, desc = fm["name"], fm["description"]
    body = body.replace("${CLAUDE_PLUGIN_ROOT}", plugin_dir) + "\n"
    body = body.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')

    print(marker)
    print(f"name = {json.dumps(name)}")
    print(f"description = {json.dumps(desc)}")
    print()
    print(f'developer_instructions = """\n{body}"""')
except Exception:
    sys.exit(1)
PY
}

install_codex_agents() {
  local agents_dir; agents_dir="$(codex_agents_dir)"
  local cats; cats="$(agent_categories)"
  [[ -n "$cats" ]] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot install agents in %s\n' \
      "$agents_dir" >&2
    return 0
  fi
  local cat md name dest toml
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.toml"
      if ! toml="$(plugin_agent_toml "$md" "$REPO_ROOT/plugins/$cat" "$AGENT_MARKER")"; then
        printf '  WARN      failed to convert %s (skipping)\n' "$md" >&2
        continue
      fi
      if (( DRY_RUN )); then
        printf '[dry-run] write agent %s\n' "$dest"
        continue
      fi
      if [[ -e "$dest" ]] && ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s exists and was not generated by us (skipping)\n' \
          "$dest" >&2
        continue
      fi
      mkdir -p "$agents_dir"
      printf '%s\n' "$toml" > "$dest.tmp.$$"
      mv "$dest.tmp.$$" "$dest"
      printf '  agent     %s -> %s\n' "$name" "$dest"
    done
  done <<< "$cats"
}

uninstall_codex_agents() {
  local agents_dir; agents_dir="$(codex_agents_dir)"
  local cat md name dest
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    for md in "$REPO_ROOT/plugins/$cat/agents/"*.md; do
      name="$(basename "$md" .md)"
      dest="$agents_dir/$name.toml"
      [[ -f "$dest" ]] || continue
      if ! grep -qF "$AGENT_MARKER" "$dest"; then
        printf '  WARN      %s was not generated by us (skipping)\n' "$dest" >&2
        continue
      fi
      if (( DRY_RUN )); then
        printf '[dry-run] remove agent %s\n' "$dest"
        continue
      fi
      rm "$dest"
      printf '  removed   %s\n' "$dest"
    done
  done < <(agent_categories)
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
    run rm "$entry"
    printf '  removed   %s (skill no longer in repo)\n' "$entry"
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
    run rm "$dest"
    printf '  removed   %s (legacy opencode location)\n' "$dest"
  done <<< "$skills"
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
    run rm "$dest"
    printf '  removed   %s (deprecated codex prompt)\n' "$dest"
  done <<< "$skills"
}

main() {
  local skills; skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT (env=$ENV, category=$CATEGORY)" >&2
    exit 1
  fi
  local routed; routed="$(routed_categories)"
  [[ "$ENV" != "all" ]] && printf 'env filter: %s\n' "$ENV"
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    local dest_dir cmd_dir="" cmd_dir_ready=0 codex_disabled_members=""
    dest_dir="$(target_dir_for "$target")"
    [[ "$target" != "codex" ]] && cmd_dir="$(target_command_dir_for "$target")"
    printf '%s: %s\n' "$target" "$dest_dir"
    if (( UNINSTALL == 0 )); then
      ensure_parent "$dest_dir"
    fi
    while IFS= read -r skill; do
      local src dest activation category
      activation="$(skill_activation "$REPO_ROOT/skills/$skill/SKILL.md")"
      category="$(skill_category "$REPO_ROOT/skills/$skill/SKILL.md")"
      if [[ "$activation" == "command" && "$target" != "codex" ]]; then
        # User-invoked: link the single SKILL.md into the command directory.
        src="$REPO_ROOT/skills/$skill/SKILL.md"
        dest="$cmd_dir/$skill.md"
        if (( UNINSTALL == 0 )) && (( cmd_dir_ready == 0 )); then
          ensure_parent "$cmd_dir"
          cmd_dir_ready=1
        fi
      elif [[ "$activation" == "auto" && "$routed" == *" $category "* ]]; then
        # Auto member of a routed category: it is nested under the router's
        # members/ dir and loads lazily when routed to, so it is never linked
        # at top level. Command skills bypass routing (handled above for
        # non-codex; linked as skills for codex), so they are not skipped here.
        # Codex discovers the nested member recursively anyway, so record it to
        # disable by name in ~/.codex/config.toml further down.
        [[ "$target" == "codex" ]] && codex_disabled_members+="$skill"$'\n'
        # Migration: before this category was routed, the member was linked
        # flat here. That link still resolves, so prune_stale_skill_links (which
        # only removes broken ones) leaves it, and the member keeps registering
        # at top level — exactly what routing exists to prevent. Remove it on
        # both paths. unlink_one only touches a symlink pointing at our own
        # path, so foreign entries and real directories are left alone.
        unlink_one "$REPO_ROOT/skills/$skill" "$dest_dir/$skill"
        continue
      else
        # A normal auto skill, or the router itself (linked as a whole dir so
        # its nested members/ come along).
        src="$REPO_ROOT/skills/$skill"
        dest="$dest_dir/$skill"
      fi
      # A skill whose `targets:` field excludes this agent is never linked
      # here; unlinking instead keeps the tree self-healing when the field is
      # added to a skill that was already installed.
      if (( UNINSTALL )) || ! skill_matches_target "$REPO_ROOT/skills/$skill/SKILL.md" "$target"; then
        unlink_one "$src" "$dest"
      else
        link_one "$src" "$dest"
      fi
    done <<< "$skills"
    prune_stale_skill_links "$dest_dir"
    [[ -n "$cmd_dir" ]] && prune_stale_skill_links "$cmd_dir"
    if [[ "$target" == "codex" ]]; then
      cleanup_codex_prompts_legacy "$skills"
      # Runs on both paths: an upgrade must drop a managed block left by a
      # version that still registered the knowledge-base MCP servers.
      remove_legacy_codex_mcp
      if (( UNINSTALL )); then
        uninstall_codex_agents
        remove_codex_member_overrides
      else
        install_codex_agents
        printf '%s' "$codex_disabled_members" | install_codex_member_overrides
      fi
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
    fi
  done < <(resolve_targets)
}

main
