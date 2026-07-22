#!/usr/bin/env bash
# Smoke test for install.sh. Uses an isolated $HOME under mktemp.
#
# Run: ./scripts/test_install.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"
HOST_PYTHON="$(command -v python3)"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

# Build a local mcp wheel so installer tests are hermetic.
MCP_WHEEL_DIR="$(mktemp -d)"
build_mcp_wheel() {
  local version="$1"
  "$HOST_PYTHON" - "$MCP_WHEEL_DIR" "$version" <<'PY'
import sys
import zipfile
from pathlib import Path

wheel_dir, version = Path(sys.argv[1]), sys.argv[2]
dist_info = f"mcp-{version}.dist-info"
target = wheel_dir / f"mcp-{version}-py3-none-any.whl"
files = {
    "mcp/__init__.py": "",
    "mcp/server/__init__.py": "",
    "mcp/server/fastmcp.py": "class FastMCP: pass\n",
    f"{dist_info}/METADATA": f"Metadata-Version: 2.1\nName: mcp\nVersion: {version}\nProvides-Extra: cli\n",
    f"{dist_info}/WHEEL": "Wheel-Version: 1.0\nGenerator: test_install.sh\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    f"{dist_info}/RECORD": "",
}
with zipfile.ZipFile(target, "w") as wheel:
    for name, content in files.items():
        wheel.writestr(name, content)
PY
}
build_mcp_wheel "1.2.0"
build_mcp_wheel "1.2rc1"
build_mcp_wheel "1.2.dev1"
PIP_NO_INDEX=1
PIP_FIND_LINKS="$MCP_WHEEL_DIR"
PIP_NO_CACHE_DIR=1
export PIP_NO_INDEX PIP_FIND_LINKS PIP_NO_CACHE_DIR

make_python_candidate() {
  local path="$1" version="$2" log="$3"
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf 'printf %q "${0##*/} $*" >> %q\n' '%s\n' "$log"
    printf '%s\n' 'if [[ "${1:-}" == "-c" ]]; then'
    printf '  printf %q %q\n' '%s\n' "$version"
    printf '%s\n' '  exit 0'
    printf '%s\n' 'fi'
    printf 'exec %q "$@"\n' "$HOST_PYTHON"
  } > "$path"
  chmod +x "$path"
}
make_noisy_python_candidate() {
  local path="$1" version="$2"
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf 'if [[ "${1:-}" == "-c" ]]; then printf "%%s\\n" %q; exit 0; fi\n' "$version"
    printf '%s\n' 'if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then printf "bootstrap stdout noise\n"; fi'
    printf 'exec %q "$@"\n' "$HOST_PYTHON"
  } > "$path"
  chmod +x "$path"
}
make_unavailable_candidate() {
  local path="$1"
  printf '%s\n' '#!/usr/bin/env bash' 'exit 127' > "$path"
  chmod +x "$path"
}
make_local_runtime() {
  local runtime="$1"
  "$HOST_PYTHON" -m venv "$runtime"
  "$runtime/bin/python" -m pip install --quiet --upgrade 'mcp[cli]>=1.2'
}
make_local_runtime_with_mcp_version() {
  local runtime="$1" version="$2"
  "$HOST_PYTHON" -m venv "$runtime"
  "$runtime/bin/python" -m pip install --quiet "$MCP_WHEEL_DIR/mcp-$version-py3-none-any.whl"
}

set_mcp_version() {
  local runtime="$1" wanted="$2"
  "$HOST_PYTHON" - "$runtime" "$wanted" <<'PY'
import sys
from pathlib import Path

runtime, wanted = Path(sys.argv[1]), sys.argv[2]
metadata = next(runtime.glob("lib/python*/site-packages/mcp-*.dist-info/METADATA"))
metadata.write_text(
    "\n".join(
        f"Version: {wanted}" if line.startswith("Version:") else line
        for line in metadata.read_text().splitlines()
    ) + "\n",
    encoding="utf-8",
)
PY
}

make_core_path() {
  local dir="$1" command command_path
  for command in env bash dirname grep basename awk sed mkdir ln readlink rm cat mv; do
    command_path="$(type -P "$command")"
    ln -s "$command_path" "$dir/$command"
  done
}

with_fake_home() {
  local fake; fake="$(mktemp -d)"
  HOME="$fake" "$@"
  echo "$fake"
}

count_links() {
  # POSIX-portable: -L returns 0 only for symlinks.
  local dir="$1" n=0
  [[ -d "$dir" ]] || { echo 0; return; }
  for f in "$dir"/*; do
    [[ -L "$f" ]] && n=$((n + 1))
  done
  echo "$n"
}

skill_count() {
  # Count skills, optionally filtered by environment ($1 = coding|chat|all).
  local want="${1:-all}" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    if [[ "$want" != "all" ]]; then
      local envs
      envs="$(grep -m1 '^environments:' "$d/SKILL.md" 2>/dev/null | sed 's/^environments://')"
      # Absent field belongs to every environment; otherwise must list $want.
      if [[ -n "${envs//[[:space:]]/}" ]] && [[ ",${envs// /}," != *",$want,"* ]]; then
        continue
      fi
    fi
    n=$((n + 1))
  done
  echo "$n"
}

EXPECTED="$(skill_count)"
[[ "$EXPECTED" -ge 1 ]] || fail "no skills detected in repo"

# 1. dry-run for --target=all should not create anything.
HOME_DRY="$(mktemp -d)"
HOME="$HOME_DRY" "$INSTALL" --target=all --dry-run >/dev/null
[[ ! -d "$HOME_DRY/.claude" ]] || fail "dry-run created $HOME_DRY/.claude"
[[ ! -d "$HOME_DRY/.codex" ]] || fail "dry-run created $HOME_DRY/.codex"
[[ ! -d "$HOME_DRY/.config/opencode" ]] || fail "dry-run created $HOME_DRY/.config/opencode"
pass "dry-run creates no files"

# 2. install --target=claude links every skill exactly once.
HOME_C="$(mktemp -d)"
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
got="$(count_links "$HOME_C/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "claude install: expected $EXPECTED links, got $got"
pass "claude install creates $EXPECTED symlinks"

# 3. Re-running is idempotent (still exactly $EXPECTED links).
HOME="$HOME_C" "$INSTALL" --target=claude >/dev/null
got="$(count_links "$HOME_C/.claude/skills")"
[[ "$got" -eq "$EXPECTED" ]] || fail "idempotent run: link count drifted to $got"
pass "claude install is idempotent"

# 4. Foreign symlink is preserved.
mkdir -p "$HOME_C/.claude/skills"
foreign_src="$(mktemp -d)/foreign"
mkdir "$foreign_src"
ln -sfn "$foreign_src" "$HOME_C/.claude/skills/foreign-skill"
HOME="$HOME_C" "$INSTALL" --target=claude --uninstall >/dev/null
[[ -L "$HOME_C/.claude/skills/foreign-skill" ]] || fail "uninstall removed a foreign symlink"
pass "uninstall preserves foreign symlinks"

# 5. Uninstall removes our symlinks; foreign stays.
ours_remaining=0
for f in "$HOME_C/.claude/skills"/*; do
  [[ -L "$f" ]] || continue
  target="$(readlink "$f")"
  [[ "$target" == "$REPO_ROOT/"* ]] && ours_remaining=$((ours_remaining + 1))
done
[[ "$ours_remaining" -eq 0 ]] || fail "uninstall left $ours_remaining of our symlinks"
pass "uninstall removes our symlinks only"

# 6. install --target=all populates all three roots.
HOME_A="$(mktemp -d)"
HOME="$HOME_A" "$INSTALL" --target=all >/dev/null
for sub in ".claude/skills" ".codex/skills" ".config/opencode/agent"; do
  got="$(count_links "$HOME_A/$sub")"
  [[ "$got" -eq "$EXPECTED" ]] || fail "all install: $sub has $got links, expected $EXPECTED"
done
pass "all install populates claude, codex, opencode"

# 7. --env=chat links only the chat subset (non-empty, strictly fewer than all).
CHAT_EXPECTED="$(skill_count chat)"
CODING_EXPECTED="$(skill_count coding)"
[[ "$CHAT_EXPECTED" -ge 1 ]] || fail "no chat skills detected"
[[ "$CHAT_EXPECTED" -lt "$EXPECTED" ]] || fail "chat subset is not smaller than all"
HOME_CHAT="$(mktemp -d)"
HOME="$HOME_CHAT" "$INSTALL" --target=claude --env=chat >/dev/null
got="$(count_links "$HOME_CHAT/.claude/skills")"
[[ "$got" -eq "$CHAT_EXPECTED" ]] || fail "env=chat: expected $CHAT_EXPECTED links, got $got"
pass "env=chat links only the $CHAT_EXPECTED chat skills"

# 8. --env=coding links only the coding subset.
HOME_CODE="$(mktemp -d)"
HOME="$HOME_CODE" "$INSTALL" --target=claude --env=coding >/dev/null
got="$(count_links "$HOME_CODE/.claude/skills")"
[[ "$got" -eq "$CODING_EXPECTED" ]] || fail "env=coding: expected $CODING_EXPECTED links, got $got"
pass "env=coding links only the $CODING_EXPECTED coding skills"

# 9. coding + chat cover at least every skill (skills in both are counted twice).
[[ $((CODING_EXPECTED + CHAT_EXPECTED)) -ge "$EXPECTED" ]] \
  || fail "coding ($CODING_EXPECTED) + chat ($CHAT_EXPECTED) < all ($EXPECTED)"
pass "coding + chat subsets cover all skills"

# 10. dry-run with a filter creates nothing.
HOME_DF="$(mktemp -d)"
HOME="$HOME_DF" "$INSTALL" --target=claude --env=chat --dry-run >/dev/null
[[ ! -d "$HOME_DF/.claude" ]] || fail "dry-run --env=chat created $HOME_DF/.claude"
pass "dry-run --env=chat creates no files"

# 11. an invalid --env value is rejected.
if HOME="$(mktemp -d)" "$INSTALL" --target=claude --env=bogus >/dev/null 2>&1; then
  fail "invalid --env=bogus was accepted"
fi
pass "invalid --env is rejected"

# 12. --category links only the matching subset (non-empty, fewer than all).
category_count() {
  # Count skills whose category: frontmatter is in the comma-separated list $1.
  local want="$1" n=0
  for d in "$REPO_ROOT"/skills/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    local cat
    cat="$(grep -m1 '^category:' "$d/SKILL.md" 2>/dev/null | sed 's/^category://')"
    cat="${cat//[[:space:]]/}"
    [[ -n "$cat" ]] && [[ ",$want," == *",$cat,"* ]] && n=$((n + 1))
  done
  echo "$n"
}
ARCH_EXPECTED="$(category_count architecture)"
[[ "$ARCH_EXPECTED" -ge 1 ]] || fail "no architecture skills detected"
[[ "$ARCH_EXPECTED" -lt "$EXPECTED" ]] || fail "architecture subset is not smaller than all"
HOME_CAT="$(mktemp -d)"
HOME="$HOME_CAT" "$INSTALL" --target=claude --category=architecture >/dev/null
got="$(count_links "$HOME_CAT/.claude/skills")"
[[ "$got" -eq "$ARCH_EXPECTED" ]] || fail "category=architecture: expected $ARCH_EXPECTED links, got $got"
pass "category=architecture links only the $ARCH_EXPECTED architecture skills"

# 13. a comma-separated --category list links the union of both subsets.
MULTI_EXPECTED="$(category_count architecture,refactoring)"
HOME_MULTI="$(mktemp -d)"
HOME="$HOME_MULTI" "$INSTALL" --target=claude --category=architecture,refactoring >/dev/null
got="$(count_links "$HOME_MULTI/.claude/skills")"
[[ "$got" -eq "$MULTI_EXPECTED" ]] || fail "category list: expected $MULTI_EXPECTED links, got $got"
pass "category=architecture,refactoring links $MULTI_EXPECTED skills"

# 14. an invalid --category value is rejected.
if HOME="$(mktemp -d)" "$INSTALL" --target=claude --category=bogus >/dev/null 2>&1; then
  fail "invalid --category=bogus was accepted"
fi
pass "invalid --category is rejected"

# 15. codex install registers the plugin MCP servers in config.toml.
HOME_MCP="$(mktemp -d)"
HOME="$HOME_MCP" "$INSTALL" --target=codex >/dev/null
CONFIG="$HOME_MCP/.codex/config.toml"
[[ -f "$CONFIG" ]] || fail "codex install did not create config.toml"
grep -Fxq '[mcp_servers.architecture-kb]' "$CONFIG" \
  || fail "architecture-kb missing from config.toml"
grep -Fxq '[mcp_servers.refactoring-kb]' "$CONFIG" \
  || fail "refactoring-kb missing from config.toml"
python3 - "$CONFIG" <<'PY' || fail "config.toml is not valid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    cfg = tomllib.load(f)
servers = cfg["mcp_servers"]
for name in ("architecture-kb", "refactoring-kb"):
    assert servers[name]["command"], name
    assert "${CLAUDE_PLUGIN_ROOT}" not in " ".join(servers[name]["args"]), name
PY
pass "codex install registers MCP servers as valid TOML"

# 15b. Managed MCP commands never retain a uv fallback.
RUNTIME_PY="$HOME_MCP/.codex/agents-mcp-runtime/bin/python"
python3 - "$CONFIG" "$RUNTIME_PY" <<'PY' || fail "MCP runtime rewrite is inconsistent"
import sys, tomllib
config, runtime_py = sys.argv[1], sys.argv[2]
with open(config, "rb") as f:
    servers = tomllib.load(f)["mcp_servers"]
for name in ("architecture-kb", "refactoring-kb"):
    cmd, args = servers[name]["command"], servers[name]["args"]
    assert cmd == runtime_py, (name, cmd)
    assert args and args[0].endswith("server.py"), (name, args)
    assert cmd != "uv" and not any("--with" in a for a in args), (name, args)
PY
pass "runtime venv rewrites MCP blocks to its interpreter"

# 16. re-running leaves config.toml byte-identical.
before="$(cat "$CONFIG")"
HOME="$HOME_MCP" "$INSTALL" --target=codex >/dev/null
[[ "$(cat "$CONFIG")" == "$before" ]] || fail "MCP registration is not idempotent"
pass "MCP registration is idempotent"

# 17. codex uninstall removes our blocks but keeps foreign config.
printf '\n[mcp_servers.foreign]\ncommand = "keep-me"\n' >> "$CONFIG"
HOME="$HOME_MCP" "$INSTALL" --target=codex --uninstall >/dev/null
grep -Fxq '[mcp_servers.foreign]' "$CONFIG" \
  || fail "uninstall dropped a foreign MCP server"
if grep -q 'mcp_servers\.\(architecture\|refactoring\)-kb' "$CONFIG"; then
  fail "uninstall left our MCP servers in config.toml"
fi
[[ -d "$HOME_MCP/.codex/agents-mcp-runtime" ]] \
  && fail "uninstall left the MCP runtime venv behind"
pass "codex uninstall removes only our MCP servers"

# 18. a category without an .mcp.json registers no MCP servers.
HOME_NOMCP="$(mktemp -d)"
HOME="$HOME_NOMCP" "$INSTALL" --target=codex --category=workflow >/dev/null
[[ ! -f "$HOME_NOMCP/.codex/config.toml" ]] \
  || fail "category=workflow created config.toml"
pass "category without MCP servers leaves config.toml alone"

# 19. a foreign server table with our name is never overwritten.
HOME_FOREIGN="$(mktemp -d)"
mkdir -p "$HOME_FOREIGN/.codex"
printf '[mcp_servers.architecture-kb]\ncommand = "mine"\n' \
  > "$HOME_FOREIGN/.codex/config.toml"
HOME="$HOME_FOREIGN" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq 'command = "mine"' "$HOME_FOREIGN/.codex/config.toml" \
  || fail "foreign architecture-kb table was overwritten"
pass "foreign MCP server table is preserved"

# 20. a foreign table using a quoted key is also detected and preserved.
HOME_QUOTED="$(mktemp -d)"
mkdir -p "$HOME_QUOTED/.codex"
printf '[mcp_servers."architecture-kb"]\ncommand = "mine"\n' \
  > "$HOME_QUOTED/.codex/config.toml"
HOME="$HOME_QUOTED" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq 'command = "mine"' "$HOME_QUOTED/.codex/config.toml" \
  || fail "quoted-key foreign table was overwritten"
python3 - "$HOME_QUOTED/.codex/config.toml" <<'PY' || fail "quoted-key case left invalid TOML"
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    tomllib.load(f)
PY
pass "quoted-key foreign table is preserved and config stays valid TOML"

# 21. unbalanced markers (hand-deleted end marker) leave the file untouched.
HOME_UNBAL="$(mktemp -d)"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null
CONFIG_UNBAL="$HOME_UNBAL/.codex/config.toml"
grep -v '^# <<< agents:architecture' "$CONFIG_UNBAL" > "$CONFIG_UNBAL.tmp"
printf '\n[mcp_servers.precious]\ncommand = "keep-me"\n' >> "$CONFIG_UNBAL.tmp"
mv "$CONFIG_UNBAL.tmp" "$CONFIG_UNBAL"
before="$(cat "$CONFIG_UNBAL")"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
[[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] \
  || fail "install modified a config with unbalanced markers"
HOME="$HOME_UNBAL" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ "$(cat "$CONFIG_UNBAL")" == "$before" ]] \
  || fail "uninstall modified a config with unbalanced markers"
pass "unbalanced markers leave config.toml untouched"

# 22. codex install converts plugin subagents to valid custom-agent TOML.
HOME_AG="$(mktemp -d)"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
AGENTS_DIR="$HOME_AG/.codex/agents"
for agent in coupling-analyst cohesion-analyst; do
  [[ -f "$AGENTS_DIR/$agent.toml" ]] || fail "missing $agent.toml"
done
python3 - "$AGENTS_DIR" <<'PY' || fail "agent TOML is invalid or incomplete"
import sys, tomllib
from pathlib import Path
for name in ("coupling-analyst", "cohesion-analyst"):
    with open(Path(sys.argv[1]) / f"{name}.toml", "rb") as f:
        agent = tomllib.load(f)
    assert agent["name"] == name
    assert agent["description"]
    assert agent["developer_instructions"].strip()
    assert "${CLAUDE_PLUGIN_ROOT}" not in agent["developer_instructions"]
PY
pass "codex install converts subagents to valid agent TOML"

# 23. re-running leaves the agent files identical; foreign files survive.
before="$(cat "$AGENTS_DIR/coupling-analyst.toml")"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null
[[ "$(cat "$AGENTS_DIR/coupling-analyst.toml")" == "$before" ]] \
  || fail "agent conversion is not idempotent"
printf 'name = "mine"\n' > "$AGENTS_DIR/cohesion-analyst.toml"
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq 'name = "mine"' "$AGENTS_DIR/cohesion-analyst.toml" \
  || fail "foreign agent file was overwritten"
pass "agent conversion is idempotent and preserves foreign files"

# 24. uninstall removes generated agents only; foreign files stay.
HOME="$HOME_AG" "$INSTALL" --target=codex --category=architecture --uninstall >/dev/null 2>&1
[[ ! -f "$AGENTS_DIR/coupling-analyst.toml" ]] \
  || fail "uninstall left a generated agent file"
[[ -f "$AGENTS_DIR/cohesion-analyst.toml" ]] \
  || fail "uninstall removed a foreign agent file"
pass "uninstall removes only generated agent files"

# 25. a category without agents creates no agents directory.
HOME_NOAG="$(mktemp -d)"
HOME="$HOME_NOAG" "$INSTALL" --target=codex --category=workflow >/dev/null
[[ ! -d "$HOME_NOAG/.codex/agents" ]] \
  || fail "category=workflow created an agents directory"
pass "category without subagents leaves agents directory alone"

# 26. Runtime provisioning ignores a Python 3.9 candidate, selects 3.12,
# and generates only direct interpreter commands for managed MCP servers.
HOME_RUNTIME="$(mktemp -d)"
RUNTIME_BIN="$(mktemp -d)"
RUNTIME_LOG="$(mktemp)"
make_python_candidate "$RUNTIME_BIN/python3" "3.9" "$RUNTIME_LOG"
make_python_candidate "$RUNTIME_BIN/python3.12" "3.12" "$RUNTIME_LOG"
for candidate in python3.13 python3.11 python3.10; do
  make_unavailable_candidate "$RUNTIME_BIN/$candidate"
done
mkdir -p "$HOME_RUNTIME/.codex/agents-mcp-runtime/bin"
{
  printf '%s\n' '#!/usr/bin/env bash'
  printf '%s\n' 'if [[ "${1:-}" == "-c" ]]; then printf "%s\\n" "3.9"; exit 0; fi'
  printf '%s\n' 'exit 70'
} > "$HOME_RUNTIME/.codex/agents-mcp-runtime/bin/python"
chmod +x "$HOME_RUNTIME/.codex/agents-mcp-runtime/bin/python"
PATH="$RUNTIME_BIN:$PATH" HOME="$HOME_RUNTIME" "$INSTALL" --target=codex >/dev/null
RUNTIME_PY="$HOME_RUNTIME/.codex/agents-mcp-runtime/bin/python"
[[ -x "$RUNTIME_PY" ]] || fail "compatible runtime venv was not created"
grep -Fq 'python3.12 -m venv' "$RUNTIME_LOG" \
  || fail "installer did not select the Python 3.12 candidate"
if grep -Eq '^(command = "uv"|.*uv run)' "$HOME_RUNTIME/.codex/config.toml"; then
  fail "managed MCP command still falls back to uv"
fi
pass "runtime rejects Python 3.9 and writes direct MCP commands"

# 27. A venv that advertises mcp 1.2 but cannot import fastmcp is replaced.
HOME_INCOMPLETE="$(mktemp -d)"
INCOMPLETE_RUNTIME="$HOME_INCOMPLETE/.codex/agents-mcp-runtime"
mkdir -p "$HOME_INCOMPLETE/.codex"
make_local_runtime "$INCOMPLETE_RUNTIME"
rm -rf "$INCOMPLETE_RUNTIME/lib"/python*/site-packages/mcp
HOME="$HOME_INCOMPLETE" "$INSTALL" --target=codex --category=architecture >/dev/null
"$INCOMPLETE_RUNTIME/bin/python" -c 'import mcp.server.fastmcp' \
  || fail "incomplete runtime was reused instead of replaced"
pass "incomplete MCP runtime is replaced"

# 28. A validated runtime is reused without invoking pip, so it also works
# when a later run is offline.
HOME_HEALTHY="$(mktemp -d)"
HEALTHY_RUNTIME="$HOME_HEALTHY/.codex/agents-mcp-runtime"
mkdir -p "$HOME_HEALTHY/.codex"
make_local_runtime "$HEALTHY_RUNTIME"
touch "$HEALTHY_RUNTIME/reuse-sentinel"
mv "$HEALTHY_RUNTIME/bin/python" "$HEALTHY_RUNTIME/bin/python.real"
{
  printf '%s\n' '#!/usr/bin/env bash'
  printf '%s\n' 'if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then exit 71; fi'
  printf 'exec %q "$@"\n' "$HEALTHY_RUNTIME/bin/python.real"
} > "$HEALTHY_RUNTIME/bin/python"
chmod +x "$HEALTHY_RUNTIME/bin/python"
HOME="$HOME_HEALTHY" "$INSTALL" --target=codex --category=architecture >/dev/null
grep -Fxq "command = \"$HEALTHY_RUNTIME/bin/python\"" "$HOME_HEALTHY/.codex/config.toml" \
  || fail "healthy runtime was not reused offline"
[[ -f "$HEALTHY_RUNTIME/reuse-sentinel" ]] \
  || fail "healthy runtime was rebuilt instead of reused"
pass "healthy MCP runtime is reused offline"

# 29. Provisioning failure removes only our selected marker blocks and never
# leaves a managed uv command behind; foreign config remains untouched.
HOME_FAILURE="$(mktemp -d)"
FAILURE_BIN="$(mktemp -d)"
FAILURE_LOG="$(mktemp)"
mkdir -p "$HOME_FAILURE/.codex"
printf '%s\n' \
  '[mcp_servers.foreign]' \
  'command = "keep-me"' \
  '' \
  '# >>> agents:architecture MCP servers (managed by install.sh, do not edit) >>>' \
  '[mcp_servers.architecture-kb]' \
  'command = "uv"' \
  '# <<< agents:architecture MCP servers <<<' \
  > "$HOME_FAILURE/.codex/config.toml"
make_python_candidate "$FAILURE_BIN/python3" "3.9" "$FAILURE_LOG"
for candidate in python3.13 python3.12 python3.11 python3.10; do
  make_unavailable_candidate "$FAILURE_BIN/$candidate"
done
PATH="$FAILURE_BIN:$PATH" HOME="$HOME_FAILURE" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq '[mcp_servers.foreign]' "$HOME_FAILURE/.codex/config.toml" \
  || fail "provisioning failure removed foreign MCP config"
if grep -q 'agents:architecture MCP servers\|mcp_servers.architecture-kb\|command = "uv"' "$HOME_FAILURE/.codex/config.toml"; then
  fail "provisioning failure left a broken managed MCP block"
fi
pass "provisioning failure fails closed and preserves foreign config"

# 30. A compatible python3.12 is sufficient when python3 is absent from PATH.
HOME_PY312="$(mktemp -d)"
PY312_BIN="$(mktemp -d)"
PY312_CORE="$(mktemp -d)"
PY312_LOG="$(mktemp)"
make_python_candidate "$PY312_BIN/python3.12" "3.12" "$PY312_LOG"
make_core_path "$PY312_CORE"
PATH="$PY312_BIN:$PY312_CORE" HOME="$HOME_PY312" bash "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
PY312_CONFIG="$HOME_PY312/.codex/config.toml"
[[ -f "$PY312_CONFIG" ]] || fail "python3.12-only install did not register MCP config"
grep -Fxq "command = \"$HOME_PY312/.codex/agents-mcp-runtime/bin/python\"" "$PY312_CONFIG" \
  || fail "python3.12-only install did not use the runtime interpreter"
pass "python3.12-only install registers direct MCP commands"

# 31. PEP 440 prereleases below 1.2 are not reused as healthy runtimes.
for prerelease in 1.2rc1 1.2.dev1; do
  HOME_PRERELEASE="$(mktemp -d)"
  PRERELEASE_RUNTIME="$HOME_PRERELEASE/.codex/agents-mcp-runtime"
  mkdir -p "$HOME_PRERELEASE/.codex"
  make_local_runtime_with_mcp_version "$PRERELEASE_RUNTIME" "$prerelease"
  HOME="$HOME_PRERELEASE" "$INSTALL" --target=codex --category=architecture >/dev/null
  "$PRERELEASE_RUNTIME/bin/python" - "$prerelease" <<'PY' || fail "pre-release MCP runtime was reused: $prerelease"
import sys
from importlib.metadata import version

assert version("mcp") == "1.2.0", version("mcp")
PY
done
pass "pre-release MCP runtimes below 1.2 are replaced"
# 32. A failed noisy provisioner cannot leave a managed block behind.
HOME_NOISY="$(mktemp -d)"
NOISY_BIN="$(mktemp -d)"
NOISY_LINKS="$(mktemp -d)"
mkdir -p "$HOME_NOISY/.codex"
printf '%s\n' \
  '[mcp_servers.foreign]' \
  'command = "keep-me"' \
  '' \
  '# >>> agents:architecture MCP servers (managed by install.sh, do not edit) >>>' \
  '[mcp_servers.architecture-kb]' \
  'command = "uv"' \
  '# <<< agents:architecture MCP servers <<<' \
  > "$HOME_NOISY/.codex/config.toml"
make_noisy_python_candidate "$NOISY_BIN/python3" "3.12"
for candidate in python3.13 python3.12 python3.11 python3.10; do
  make_unavailable_candidate "$NOISY_BIN/$candidate"
done
PIP_FIND_LINKS="$NOISY_LINKS" PATH="$NOISY_BIN:$PATH" HOME="$HOME_NOISY" "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq '[mcp_servers.foreign]' "$HOME_NOISY/.codex/config.toml" \
  || fail "noisy provisioning failure removed foreign config"
if grep -q 'agents:architecture MCP servers\|mcp_servers.architecture-kb' "$HOME_NOISY/.codex/config.toml"; then
  fail "noisy provisioning failure left a managed MCP block"
fi
pass "provisioning stdout cannot become a managed runtime command"

# 33. An unresolved uv command removes only its managed block.
HOME_BAD_UV="$(mktemp -d)"
REPO_BAD_UV="$(mktemp -d)/agents-copy"
cp -a "$REPO_ROOT" "$REPO_BAD_UV"
printf '%s\n' \
  '{"mcpServers":{"architecture-kb":{"command":"uv","args":["run","--with","mcp[cli]>=1.2","not-python"]}}}' \
  > "$REPO_BAD_UV/plugins/architecture/.mcp.json"
mkdir -p "$HOME_BAD_UV/.codex"
printf '%s\n' \
  '[mcp_servers.foreign]' \
  'command = "keep-me"' \
  '' \
  '# >>> agents:architecture MCP servers (managed by install.sh, do not edit) >>>' \
  '[mcp_servers.architecture-kb]' \
  'command = "uv"' \
  '# <<< agents:architecture MCP servers <<<' \
  > "$HOME_BAD_UV/.codex/config.toml"
HOME="$HOME_BAD_UV" "$REPO_BAD_UV/install.sh" --target=codex --category=architecture >/dev/null 2>&1
grep -Fxq '[mcp_servers.foreign]' "$HOME_BAD_UV/.codex/config.toml" \
  || fail "unresolved uv removed foreign config"
if grep -q 'agents:architecture MCP servers\|mcp_servers.architecture-kb' "$HOME_BAD_UV/.codex/config.toml"; then
  fail "unresolved uv left a managed MCP block"
fi
pass "unresolved uv command fails closed"

# 34. PEP 440 post releases reuse; invalid suffixes fail closed.
PEP_CORE="$(mktemp -d)"
PEP_BIN="$(mktemp -d)"
make_core_path "$PEP_CORE"
for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
  make_unavailable_candidate "$PEP_BIN/$candidate"
done
for accepted in 1.2-1 1.2rev1 1.2r1 1.2.post1.dev1 1.3alpha1; do
  HOME_PEP="$(mktemp -d)"
  PEP_RUNTIME="$HOME_PEP/.codex/agents-mcp-runtime"
  mkdir -p "$HOME_PEP/.codex"
  make_local_runtime "$PEP_RUNTIME"
  set_mcp_version "$PEP_RUNTIME" "$accepted"
  touch "$PEP_RUNTIME/accepted-sentinel"
  PATH="$PEP_BIN:$PEP_CORE" HOME="$HOME_PEP" bash "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
  [[ -f "$PEP_RUNTIME/accepted-sentinel" ]] \
    || fail "valid PEP 440 version was not reused: $accepted"
done
HOME_BAD_VERSION="$(mktemp -d)"
BAD_VERSION_RUNTIME="$HOME_BAD_VERSION/.codex/agents-mcp-runtime"
mkdir -p "$HOME_BAD_VERSION/.codex"
make_local_runtime "$BAD_VERSION_RUNTIME"
set_mcp_version "$BAD_VERSION_RUNTIME" "1.2nonsense"
PATH="$PEP_BIN:$PEP_CORE" HOME="$HOME_BAD_VERSION" bash "$INSTALL" --target=codex --category=architecture >/dev/null 2>&1
[[ ! -d "$BAD_VERSION_RUNTIME" ]] \
  || fail "invalid PEP 440 suffix was accepted"
pass "PEP 440 threshold accepts post releases and rejects invalid suffixes"

# 35. Dry-run plans replacement without changing managed TOML.
HOME_DRY_MCP="$(mktemp -d)"
mkdir -p "$HOME_DRY_MCP/.codex"
printf '%s\n' \
  '[mcp_servers.foreign]' \
  'command = "keep-me"' \
  '' \
  '# >>> agents:architecture MCP servers (managed by install.sh, do not edit) >>>' \
  '[mcp_servers.architecture-kb]' \
  'command = "uv"' \
  '# <<< agents:architecture MCP servers <<<' \
  > "$HOME_DRY_MCP/.codex/config.toml"
DRY_CONFIG="$HOME_DRY_MCP/.codex/config.toml"
before="$(cat "$DRY_CONFIG")"
dry_output="$(HOME="$HOME_DRY_MCP" "$INSTALL" --target=codex --category=architecture --dry-run 2>&1)"
[[ "$(cat "$DRY_CONFIG")" == "$before" ]] || fail "dry-run modified managed MCP config"
[[ "$dry_output" == *"create MCP runtime venv"* ]] \
  || fail "dry-run did not plan runtime creation"
[[ "$dry_output" == *"remove architecture MCP servers"* ]] \
  || fail "dry-run did not plan managed-block replacement"
[[ "$dry_output" == *"register architecture MCP servers"* ]] \
  || fail "dry-run did not plan MCP registration"
pass "dry-run plans runtime replacement without changing config"

echo "all install.sh tests passed"
