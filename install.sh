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
# The codex target additionally installs the full plugins, not just the
# skills. Requires python3 (skipped with a warning otherwise); --uninstall
# reverses both. --env only filters skills; the plugin extras follow
# --category:
#   - Each selected plugin's knowledge-base MCP servers
#     (plugins/<category>/.mcp.json) are registered in ~/.codex/config.toml.
#   - Each selected plugin's subagents (plugins/<category>/agents/*.md) are
#     converted to Codex custom agents in ~/.codex/agents/<name>.toml.
#
# Conservative behaviour:
#   - Existing correct symlink:        skip (idempotent).
#   - Symlink pointing elsewhere:      skip with a warning, never overwrite.
#   - Regular file or non-empty dir:   skip with a warning, never overwrite.
#   - Uninstall only removes a symlink whose target is a path inside this
#     repo, so foreign files at that location are never touched.
#   - MCP servers are written to ~/.codex/config.toml only between our own
#     marker comments; a foreign [mcp_servers.<name>] table with the same
#     name is never overwritten, and uninstall only removes our blocks.
#     If the marker lines have been hand-edited into an unbalanced state,
#     the whole file is left untouched rather than risk stripping too much.
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
CATEGORIES="architecture refactoring r-development ai-ml workflow communication personal"

usage() { sed -n '2,46p' "$0"; }

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

# --- Codex MCP server registration -----------------------------------------
#
# Claude installs plugins/<category>/.mcp.json natively; Codex CLI reads MCP
# servers from ~/.codex/config.toml instead. Each selected plugin's .mcp.json
# is translated into a marker-delimited TOML block so install and uninstall
# stay idempotent and never touch config we do not own.

codex_config_path() { printf '%s/.codex/config.toml' "$HOME"; }

mcp_begin_marker() {
  printf '# >>> agents:%s MCP servers (managed by install.sh, do not edit) >>>' "$1"
}

mcp_end_marker() {
  printf '# <<< agents:%s MCP servers <<<' "$1"
}

# Categories selected by --category that ship an .mcp.json.
mcp_categories() {
  local c
  if [[ "$CATEGORY" == "all" ]]; then
    for c in $CATEGORIES; do
      if [[ -f "$REPO_ROOT/plugins/$c/.mcp.json" ]]; then printf '%s\n' "$c"; fi
    done
  else
    local IFS=','
    for c in $CATEGORY; do
      c="${c//[[:space:]]/}"
      if [[ -n "$c" && -f "$REPO_ROOT/plugins/$c/.mcp.json" ]]; then
        printf '%s\n' "$c"
      fi
    done
  fi
  return 0
}

# Render plugins/<category>/.mcp.json as Codex config.toml tables, with
# ${CLAUDE_PLUGIN_ROOT} resolved to the plugin directory in this repo.
plugin_mcp_toml() {
  local plugin_dir="$REPO_ROOT/plugins/$1"
  python3 - "$plugin_dir" <<'PY'
import json
import sys
from pathlib import Path

plugin_dir = Path(sys.argv[1])
spec = json.loads((plugin_dir / ".mcp.json").read_text(encoding="utf-8"))


def toml_str(value: str) -> str:
    value = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
    return json.dumps(value)  # JSON string escaping is valid TOML


lines = []
for name, server in spec.get("mcpServers", {}).items():
    lines.append(f"[mcp_servers.{name}]")
    lines.append(f"command = {toml_str(server['command'])}")
    args = ", ".join(toml_str(a) for a in server.get("args", []))
    lines.append(f"args = [{args}]")
    env = server.get("env", {})
    if env:
        pairs = ", ".join(f"{k} = {toml_str(v)}" for k, v in env.items())
        lines.append(f"env = {{ {pairs} }}")
    lines.append("")
print("\n".join(lines).rstrip())
PY
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

install_codex_mcp() {
  local config; config="$(codex_config_path)"
  local cats; cats="$(mcp_categories)"
  [[ -n "$cats" ]] || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    printf '  WARN      python3 not found; cannot register MCP servers in %s\n' \
      "$config" >&2
    return 0
  fi
  local cat toml rest name skip
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    if ! toml="$(plugin_mcp_toml "$cat")"; then
      printf '  WARN      failed to parse plugins/%s/.mcp.json (skipping)\n' "$cat" >&2
      continue
    fi
    if (( DRY_RUN )); then
      printf '[dry-run] register %s MCP servers in %s\n' "$cat" "$config"
      continue
    fi
    mkdir -p "$(dirname "$config")"
    [[ -f "$config" ]] || : > "$config"
    if ! mcp_markers_balanced "$cat" < "$config"; then
      printf '  WARN      unbalanced %s marker lines in %s (leaving it untouched)\n' \
        "$cat" "$config" >&2
      continue
    fi
    rest="$(strip_mcp_block "$cat" < "$config")"
    skip=0
    while IFS= read -r name; do
      if [[ ! "$name" =~ ^[A-Za-z0-9_-]+$ ]]; then
        printf '  WARN      MCP server name %q is not a bare TOML key (skipping %s)\n' \
          "$name" "$cat" >&2
        skip=1
        continue
      fi
      # Match bare and quoted forms of the table header, with optional
      # trailing whitespace or comment: [mcp_servers."<name>"] # note
      if printf '%s\n' "$rest" \
        | grep -Eq "^\[mcp_servers\.\"?$name\"?\][[:space:]]*(#.*)?$"; then
        printf '  WARN      [mcp_servers.%s] already in %s (not ours, skipping %s)\n' \
          "$name" "$config" "$cat" >&2
        skip=1
      fi
    done < <(printf '%s\n' "$toml" | sed -n 's/^\[mcp_servers\.\([^]]*\)\]$/\1/p')
    if (( skip )); then continue; fi
    {
      if [[ -n "$rest" ]]; then printf '%s\n\n' "$rest"; fi
      mcp_begin_marker "$cat"; printf '\n'
      printf '%s\n' "$toml"
      mcp_end_marker "$cat"; printf '\n'
    } > "$config.tmp.$$"
    mv "$config.tmp.$$" "$config"
    printf '  mcp       %s servers registered in %s\n' "$cat" "$config"
  done <<< "$cats"
}

uninstall_codex_mcp() {
  local config; config="$(codex_config_path)"
  [[ -f "$config" ]] || return 0
  local cat before after
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    before="$(cat "$config")"
    if ! mcp_markers_balanced "$cat" <<< "$before"; then
      printf '  WARN      unbalanced %s marker lines in %s (leaving it untouched)\n' \
        "$cat" "$config" >&2
      continue
    fi
    after="$(strip_mcp_block "$cat" <<< "$before")"
    [[ "$after" != "$before" ]] || continue
    if (( DRY_RUN )); then
      printf '[dry-run] remove %s MCP servers from %s\n' "$cat" "$config"
      continue
    fi
    if [[ -n "$after" ]]; then
      printf '%s\n' "$after" > "$config"
    else
      : > "$config"
    fi
    printf '  removed   %s MCP servers from %s\n' "$cat" "$config"
  done < <(mcp_categories)
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

main() {
  local skills; skills="$(list_skills)"
  if [[ -z "$skills" ]]; then
    echo "no skills found under $REPO_ROOT (env=$ENV, category=$CATEGORY)" >&2
    exit 1
  fi
  [[ "$ENV" != "all" ]] && printf 'env filter: %s\n' "$ENV"
  [[ "$CATEGORY" != "all" ]] && printf 'category filter: %s\n' "$CATEGORY"

  while IFS= read -r target; do
    [[ -z "$target" ]] && continue
    local dest_dir; dest_dir="$(target_dir_for "$target")"
    printf '%s: %s\n' "$target" "$dest_dir"
    if (( UNINSTALL == 0 )); then
      ensure_parent "$dest_dir"
    fi
    while IFS= read -r skill; do
      local src="$REPO_ROOT/skills/$skill"
      local dest="$dest_dir/$skill"
      if (( UNINSTALL )); then
        unlink_one "$src" "$dest"
      else
        link_one "$src" "$dest"
      fi
    done <<< "$skills"
    if [[ "$target" == "codex" ]]; then
      if (( UNINSTALL )); then
        uninstall_codex_mcp
        uninstall_codex_agents
      else
        install_codex_mcp
        install_codex_agents
      fi
    fi
  done < <(resolve_targets)
}

main
