#!/usr/bin/env bash
# Eval runner: invokes opencode for each (config, task) pair and saves the
# generated solution.R into runs/<ts>/<config>/<task>/.
#
# Usage:
#   ./run.sh                                  # all tasks, all configs
#   ./run.sh --task 03-pkg-state-env          # one task, all configs
#   ./run.sh --config with-skill              # all tasks, one config
#   ./run.sh --task 01-dt-aggregate --config baseline
#   ./run.sh --score-only runs/<ts>           # just re-score an existing run
#   ./run.sh --no-judge                       # skip the LLM judge step
#
# Configuration via env:
#   OPENCODE_BIN     CLI under test (default: opencode). The eval suite is
#                    designed around opencode's `run --pure` flag, so other
#                    coder CLIs are not drop-in replacements here.
#   JUDGE_CLI        CLI used by judge.R for LLM-as-judge scoring
#                    (default: claude). Independent of OPENCODE_BIN — you
#                    can evaluate any CLI under test with any judge.
#
# Mock mode (no opencode call):
#   OPENCODE_MOCK_DIR=fixtures ./run.sh
#   The runner will copy fixtures/<config>/<task>/solution.R instead of
#   shelling out to opencode. Useful for testing the harness itself.
#   The judge is also skipped in mock mode.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TASK_FILTER=""
CONFIG_FILTER=""
SCORE_ONLY=""
NO_JUDGE="${NO_JUDGE:-}"
OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
JUDGE_CLI="${JUDGE_CLI:-claude}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)        TASK_FILTER="$2"; shift 2 ;;
    --config)      CONFIG_FILTER="$2"; shift 2 ;;
    --score-only)  SCORE_ONLY="$2"; shift 2 ;;
    --no-judge)    NO_JUDGE=1; shift ;;
    -h|--help)     sed -n '2,18p' "$0"; exit 0 ;;
    *)             echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Run scoring + judge + aggregation + viewer over an existing run dir.
finalize() {
  local run_dir="$1"
  echo "[run] scoring..."
  Rscript score.R "$run_dir"

  if [[ -z "$NO_JUDGE" && -z "${OPENCODE_MOCK_DIR:-}" ]] && command -v "$JUDGE_CLI" &>/dev/null; then
    echo "[run] judging with $JUDGE_CLI..."
    JUDGE_CLI="$JUDGE_CLI" Rscript judge.R "$run_dir"
  else
    echo "[run] skipping judge (NO_JUDGE, mock mode, or $JUDGE_CLI not on PATH)"
    Rscript judge.R "$run_dir" --skip
  fi

  echo "[run] aggregating..."
  Rscript aggregate.R "$run_dir"

  echo "[run] viewer..."
  Rscript generate_viewer.R "$run_dir"
}

if [[ -n "$SCORE_ONLY" ]]; then
  finalize "$SCORE_ONLY"
  exit $?
fi

TS="$(date +%Y-%m-%d_%H-%M-%S)"
RUN_DIR="runs/$TS"
mkdir -p "$RUN_DIR"
echo "[run] writing to $RUN_DIR"

list_dirs() { find "$1" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort; }

CONFIGS=$(list_dirs configs)
TASKS=$(list_dirs tasks)

[[ -n "$CONFIG_FILTER" ]] && CONFIGS="$CONFIG_FILTER"
[[ -n "$TASK_FILTER"   ]] && TASKS="$TASK_FILTER"

run_one() {
  local config="$1" task="$2"
  local task_dir="$ROOT/tasks/$task"
  local out_dir="$ROOT/$RUN_DIR/$config/$task"
  local work; work="$(mktemp -d)"
  mkdir -p "$out_dir"

  echo "[run] $config / $task   (workdir: $work)"

  local flags_file="$ROOT/configs/$config/flags"
  local opencode_flags=""
  local flags_json="[]"
  if [[ -f "$flags_file" ]]; then
    opencode_flags="$(cat "$flags_file")"
    flags_json="[$(echo "$opencode_flags" | tr ' \n' '\0' | xargs -0 printf '"%s",' | sed 's/,$//')]"
  fi

  local oc_config="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/opencode.json"
  local model_json='"unknown"'
  local plugins_json="[]"
  local mcp_json="[]"
  if [[ -f "$oc_config" ]] && command -v jq &>/dev/null; then
    local raw_model
    raw_model=$(jq -r '.model // .small_model // empty' "$oc_config")
    [[ -n "$raw_model" ]] && model_json="\"$raw_model\""
    plugins_json=$(jq -c '[.plugin // [] | .[]]' "$oc_config")
    mcp_json=$(jq -c '[.mcp // {} | keys[]]' "$oc_config")
  fi

  local extra_flags=""
  local config_model_file="$ROOT/configs/$config/model"
  if [[ -f "$config_model_file" ]]; then
    local config_model
    config_model=$(tr -d '[:space:]' < "$config_model_file")
    model_json="\"$config_model\""
    extra_flags="-m $config_model"
  fi

  local pure_mode=false
  if echo " $opencode_flags " | grep -qw -- '--pure'; then
    pure_mode=true
    plugins_json="[]"
    mcp_json="[]"
  fi

  local skills_enabled=false
  local context_files_json="[]"
  if [[ -f "$ROOT/configs/$config/AGENTS.md" ]]; then
    skills_enabled=true
    context_files_json='["AGENTS.md"]'
  fi

  local oc_version="unknown"
  oc_version=$("$OPENCODE_BIN" --version 2>/dev/null | head -1 | tr -d '[:space:]') || true

  [[ -f "$ROOT/configs/$config/AGENTS.md" ]] && cp "$ROOT/configs/$config/AGENTS.md" "$work/AGENTS.md"
  [[ -f "$task_dir/target.R" ]] && cp "$task_dir/target.R" "$work/"
  if [[ -f "$task_dir/setup.R" ]]; then
    (cd "$work" && Rscript "$task_dir/setup.R" >/dev/null 2>&1) || {
      echo "  setup.R failed" >&2
    }
  fi

  local prompt
  prompt="$(Rscript -e 'suppressWarnings(Sys.setlocale("LC_ALL","C.UTF-8")); cat(yaml::yaml.load(paste(readLines(commandArgs(TRUE)[1], encoding="UTF-8", warn=FALSE), collapse="\n"))$prompt)' "$task_dir/task.yaml")"
  local start_ts end_ts exit_code=0

  start_ts=$(date +%s)
  if [[ -n "${OPENCODE_MOCK_DIR:-}" ]]; then
    local fixture="$ROOT/$OPENCODE_MOCK_DIR/$config/$task/solution.R"
    if [[ -f "$fixture" ]]; then
      cp "$fixture" "$work/solution.R"
    else
      echo "  [mock] no fixture at $fixture — skipping write" >&2
      exit_code=127
    fi
  else
    (cd "$work" && "$OPENCODE_BIN" run $opencode_flags $extra_flags "$prompt") \
      > "$out_dir/opencode.stdout" 2> "$out_dir/opencode.stderr" \
      || exit_code=$?
  fi
  end_ts=$(date +%s)
  local mock_val
  mock_val=$([ -n "${OPENCODE_MOCK_DIR:-}" ] && echo true || echo false)

  if [[ -f "$work/solution.R" ]]; then
    cp "$work/solution.R" "$out_dir/solution.R"
  else
    echo "  no solution.R produced" >&2
  fi

  cat > "$out_dir/meta.json" <<JSON
{
  "config": "$config",
  "task": "$task",
  "opencode_flags": $flags_json,
  "model": $model_json,
  "opencode_version": "$oc_version",
  "pure_mode": $pure_mode,
  "plugins": $plugins_json,
  "mcp_servers": $mcp_json,
  "skills_enabled": $skills_enabled,
  "context_files": $context_files_json,
  "started_at": $start_ts,
  "ended_at": $end_ts,
  "duration_s": $((end_ts - start_ts)),
  "exit_code": $exit_code,
  "mock": $mock_val
}
JSON

  rm -rf "$work"
}

for config in $CONFIGS; do
  [[ -d "configs/$config" ]] || { echo "no such config: $config" >&2; exit 2; }
  for task in $TASKS; do
    [[ -d "tasks/$task" ]] || { echo "no such task: $task" >&2; exit 2; }
    run_one "$config" "$task"
  done
done

finalize "$RUN_DIR"
