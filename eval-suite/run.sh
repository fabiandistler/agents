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
#
# Mock mode (no opencode call):
#   OPENCODE_MOCK_DIR=fixtures ./run.sh
#   The runner will copy fixtures/<config>/<task>/solution.R instead of
#   shelling out to opencode. Useful for testing the harness itself.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TASK_FILTER=""
CONFIG_FILTER=""
SCORE_ONLY=""
OPENCODE_BIN="${OPENCODE_BIN:-opencode}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)        TASK_FILTER="$2"; shift 2 ;;
    --config)      CONFIG_FILTER="$2"; shift 2 ;;
    --score-only)  SCORE_ONLY="$2"; shift 2 ;;
    -h|--help)     sed -n '2,17p' "$0"; exit 0 ;;
    *)             echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$SCORE_ONLY" ]]; then
  Rscript score.R "$SCORE_ONLY"
  exit $?
fi

TS="$(date +%Y-%m-%d_%H-%M-%S)"
RUN_DIR="runs/$TS"
mkdir -p "$RUN_DIR"
echo "[run] writing to $RUN_DIR"

list_dirs() { ls -1 "$1" 2>/dev/null | sort; }

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

  cp "$ROOT/configs/$config/AGENTS.md" "$work/AGENTS.md"
  [[ -f "$task_dir/target.R" ]] && cp "$task_dir/target.R" "$work/"
  if [[ -f "$task_dir/setup.R" ]]; then
    (cd "$work" && Rscript "$task_dir/setup.R" >/dev/null 2>&1) || {
      echo "  setup.R failed" >&2
    }
  fi

  local prompt; prompt="$(cat "$task_dir/prompt.md")"
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
    (cd "$work" && "$OPENCODE_BIN" run "$prompt") \
      > "$out_dir/opencode.stdout" 2> "$out_dir/opencode.stderr" \
      || exit_code=$?
  fi
  end_ts=$(date +%s)

  if [[ -f "$work/solution.R" ]]; then
    cp "$work/solution.R" "$out_dir/solution.R"
  else
    echo "  no solution.R produced" >&2
  fi

  cat > "$out_dir/meta.json" <<JSON
{
  "config": "$config",
  "task": "$task",
  "started_at": $start_ts,
  "ended_at": $end_ts,
  "duration_s": $((end_ts - start_ts)),
  "exit_code": $exit_code,
  "mock": ${OPENCODE_MOCK_DIR:+true}${OPENCODE_MOCK_DIR:-false}
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

echo "[run] scoring..."
Rscript score.R "$RUN_DIR"
