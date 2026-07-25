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
# nested members are never linked flat and so are skipped by (un)install.
#
# The codex target additionally installs the full plugins, not just the
# skills. Requires python3 (skipped with a warning otherwise); --uninstall
# reverses both. --env only filters skills; the plugin extras follow
# --category:
#   - Each selected plugin's knowledge-base MCP servers
#     (plugins/<category>/.mcp.json) are registered in ~/.codex/config.toml.
#     Their `uv run --with mcp[cli]...` dependency is resolved once here into
#     a runtime venv (~/.codex/agents-mcp-runtime) and the generated config
#     points at that interpreter, so tool starts need no uv cache or PyPI
#     access — the fix for sandboxed Codex setups that deny both.
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
#     The runtime venv lives at a fixed path we own and is removed on
#     uninstall.
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
#
# $2 is the validated interpreter of the install-time runtime venv (see
# install_codex_mcp_runtime). Servers launched via `uv run ... python
# <script>` are rewritten to invoke that interpreter on <script> directly, so
# the tool start needs neither uv cache writes nor PyPI access — the dependency
# was resolved once at install time.
plugin_mcp_toml() {
  local plugin_dir="$REPO_ROOT/plugins/$1" runtime_python="${2:-}" render_python="${3:-$2}"
  "$render_python" - "$plugin_dir" "$runtime_python" <<'PY'
import json
import sys
from pathlib import Path

plugin_dir = Path(sys.argv[1])
runtime_python = sys.argv[2]
spec = json.loads((plugin_dir / ".mcp.json").read_text(encoding="utf-8"))


def toml_str(value: str) -> str:
    value = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_dir))
    return json.dumps(value)  # JSON string escaping is valid TOML


def resolve(command: str, args: list[str]) -> tuple[str, list[str]]:
    """Rewrite a `uv run ... python <script> [extra]` launch to run <script>
    with the install-time runtime interpreter, dropping the uv/dependency
    flags. Anything else is returned unchanged."""
    if command != "uv":
        return command, args
    for i, a in enumerate(args):
        if a in ("python", "python3") and i + 1 < len(args):
            return runtime_python, args[i + 1 :]
    raise ValueError("cannot resolve uv launch to a direct Python command")


lines = []
for name, server in spec.get("mcpServers", {}).items():
    command, args = resolve(server["command"], server.get("args", []))
    lines.append(f"[mcp_servers.{name}]")
    lines.append(f"command = {toml_str(command)}")
    rendered = ", ".join(toml_str(a) for a in args)
    lines.append(f"args = [{rendered}]")
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

# --- Codex MCP runtime venv -------------------------------------------------
#
# Under Claude the servers run via `uv run --with mcp[cli]>=1.2 ...`, which
# resolves the dependency on every launch — needing uv cache writes and PyPI
# access. Codex tool starts often run under a restrictive sandbox where both
# are denied, so we resolve the dependency once here, at install time, into a
# dedicated venv and point the generated config at its interpreter.

codex_mcp_runtime_dir() { printf '%s/.codex/agents-mcp-runtime' "$HOME"; }
codex_mcp_runtime_python() { printf '%s/bin/python' "$(codex_mcp_runtime_dir)"; }

# Print the first usable Python interpreter in the documented preference
# order. A name alone is not enough: installations often retain a python3
# symlink to an unsupported interpreter after an OS upgrade.
codex_mcp_python() {
  local candidate version major minor
  for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version="$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null)" \
      || continue
    if [[ "$version" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
      major="${BASH_REMATCH[1]}"
      minor="${BASH_REMATCH[2]}"
      if (( major > 3 || (major == 3 && minor >= 10) )); then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

# A runtime is usable only when both the Python and mcp contracts hold. The
# import check catches interrupted installs that still leave mcp dist-info
# metadata behind.
codex_mcp_runtime_valid() {
  local py="$1" version major minor
  [[ -x "$py" ]] || return 1
  version="$("$py" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null)" \
    || return 1
  [[ "$version" =~ ^([0-9]+)\.([0-9]+)$ ]] || return 1
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  (( major > 3 || (major == 3 && minor >= 10) )) || return 1
  "$py" -c '
from importlib.metadata import PackageNotFoundError, version
import re

try:
    raw = version("mcp").strip().lower()
except PackageNotFoundError:
    raise SystemExit(1)

# PEP 440 public-version parser used only for the >=1.2 threshold. It keeps
# the runtime-valid contract independent of pip vendored modules.
match = re.fullmatch(r"""
    v?(?:(?P<epoch>\d+)!)?
    (?P<release>\d+(?:\.\d+)*)
    (?:(?P<pre_sep>[-_.]?)(?P<pre>alpha|beta|preview|pre|rc|c|a|b)[-_.]?(?P<pre_n>\d*))?
    (?P<post>(?:[-_.]?(?:post|rev|r)[-_.]?\d*)|(?:-\d+))?
    (?:(?P<dev_sep>[-_.]?)dev[-_.]?(?P<dev_n>\d*))?
    (?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?
""", raw, re.VERBOSE)
if not match:
    raise SystemExit(1)
epoch = int(match.group("epoch") or 0)
release = [int(part) for part in match.group("release").split(".")]
while len(release) > 1 and release[-1] == 0:
    release.pop()
base = [1, 2]
if epoch == 0 and release < base:
    raise SystemExit(1)
if epoch == 0 and release == base:
    # A pre/dev release of the base version is older than 1.2. A post release
    # remains newer even when it carries a following development segment.
    if match.group("pre") or (match.group("dev_n") is not None and not match.group("post")):
        raise SystemExit(1)
import mcp.server.fastmcp
' >/dev/null 2>&1
}

# Collect the unique `--with <spec>` dependency specs across the selected
# plugins' uv-launched MCP servers, one per line.
codex_mcp_requirements() {
  local render_python="$1"
  local cats; cats="$(mcp_categories)"
  [[ -n "$cats" ]] || return 0
  "$render_python" - "$REPO_ROOT" $cats <<'PY'
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
seen: list[str] = []
for cat in sys.argv[2:]:
    spec = json.loads((repo_root / "plugins" / cat / ".mcp.json").read_text("utf-8"))
    for server in spec.get("mcpServers", {}).values():
        if server.get("command") != "uv":
            continue
        args = server.get("args", [])
        for i, a in enumerate(args):
            if a == "--with" and i + 1 < len(args) and args[i + 1] not in seen:
                seen.append(args[i + 1])
print("\n".join(seen))
PY
}

# Provision the runtime venv and install the collected requirements into it.
# Prints the interpreter path only after validation. On failure it prints a
# concrete warning and returns no interpreter, so callers can fail closed
# rather than write a broken uv fallback into Codex's config.
install_codex_mcp_runtime() {
  local cats; cats="$(mcp_categories)"
  [[ -n "$cats" ]] || return 0

  local venv; venv="$(codex_mcp_runtime_dir)"
  local py; py="$(codex_mcp_runtime_python)"
  local bootstrap_python reqs

  if (( DRY_RUN )); then
    if bootstrap_python="$(codex_mcp_python)"; then
      reqs="$(codex_mcp_requirements "$bootstrap_python")"
      printf '[dry-run] create MCP runtime venv %s with %s and install: %s\n' \
        "$venv" "$bootstrap_python" "$(printf '%s ' $reqs)" >&2
      printf '%s\n' "$py"
    else
      printf '  WARN      no Python >=3.10 found; MCP servers will not be registered\n' >&2
    fi
    return 0
  fi

  if codex_mcp_runtime_valid "$py"; then
    printf '  runtime   reusing validated MCP runtime %s\n' "$venv" >&2
    printf '%s\n' "$py"
    return 0
  fi

  if [[ -e "$venv" ]]; then
    rm -rf "$venv"
  fi
  if ! bootstrap_python="$(codex_mcp_python)"; then
    printf '  WARN      no compatible Python >=3.10 found; MCP servers were not registered\n' >&2
    return 0
  fi
  reqs="$(codex_mcp_requirements "$bootstrap_python")"
  [[ -n "${reqs//[[:space:]]/}" ]] || return 0  # no uv server; nothing to do
  if ! "$bootstrap_python" -m venv "$venv" 1>&2; then
    printf '  WARN      could not create MCP runtime venv %s with %s; MCP servers were not registered\n' \
      "$venv" "$bootstrap_python" >&2
    return 0
  fi
  # shellcheck disable=SC2086
  if ! "$py" -m pip install --quiet --upgrade $reqs 1>&2; then
    printf '  WARN      could not install MCP dependencies into %s; MCP servers were not registered\n' \
      "$venv" >&2
    return 0
  fi
  if ! codex_mcp_runtime_valid "$py"; then
    printf '  WARN      MCP runtime %s failed validation; MCP servers were not registered\n' \
      "$venv" >&2
    return 0
  fi
  printf '  runtime   MCP dependencies installed in %s\n' "$venv" >&2
  printf '%s\n' "$py"
}

remove_codex_mcp_blocks() {
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
  done < <(
    if (( $# )); then
      printf '%s\n' "$@"
    else
      mcp_categories
    fi
  )
}

install_codex_mcp() {
  local config; config="$(codex_config_path)"
  local cats; cats="$(mcp_categories)"
  [[ -n "$cats" ]] || return 0
  local runtime_python; runtime_python="$(install_codex_mcp_runtime)"
  if [[ -z "$runtime_python" ]]; then
    remove_codex_mcp_blocks
    return 0
  fi
  if (( DRY_RUN )); then
    remove_codex_mcp_blocks
    while IFS= read -r cat; do
      [[ -n "$cat" ]] || continue
      printf '[dry-run] register %s MCP servers in %s\n' "$cat" "$config"
    done <<< "$cats"
    return 0
  fi
  local cat toml rest name skip
  while IFS= read -r cat; do
    [[ -n "$cat" ]] || continue
    if ! toml="$(plugin_mcp_toml "$cat" "$runtime_python" "$runtime_python")"; then
      printf '  WARN      failed to render plugins/%s/.mcp.json; removing managed block\n' "$cat" >&2
      remove_codex_mcp_blocks "$cat"
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
  remove_codex_mcp_blocks

  # Remove the install-time runtime venv we provisioned for these servers.
  local venv; venv="$(codex_mcp_runtime_dir)"
  if [[ -d "$venv" ]]; then
    if (( DRY_RUN )); then
      printf '[dry-run] remove MCP runtime venv %s\n' "$venv"
    else
      rm -rf "$venv"
      printf '  removed   MCP runtime venv %s\n' "$venv"
    fi
  fi
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
    local dest_dir cmd_dir="" cmd_dir_ready=0
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
        # (or unlinked) at top level. Command skills bypass routing (handled
        # above for non-codex; linked as skills for codex), so they are not
        # skipped here.
        continue
      else
        # A normal auto skill, or the router itself (linked as a whole dir so
        # its nested members/ come along).
        src="$REPO_ROOT/skills/$skill"
        dest="$dest_dir/$skill"
      fi
      if (( UNINSTALL )); then
        unlink_one "$src" "$dest"
      else
        link_one "$src" "$dest"
      fi
    done <<< "$skills"
    if [[ "$target" == "codex" ]]; then
      cleanup_codex_prompts_legacy "$skills"
      if (( UNINSTALL )); then
        uninstall_codex_mcp
        uninstall_codex_agents
      else
        install_codex_mcp
        install_codex_agents
      fi
    fi
    if [[ "$target" == "opencode" ]]; then
      cleanup_opencode_legacy "$skills"
    fi
  done < <(resolve_targets)
}

main
