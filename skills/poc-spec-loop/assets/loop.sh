#!/usr/bin/env bash
# poc-spec-loop / Phase 2 driver — SKELETON, not yet run against a real PoC.
#
# Owns everything the per-task prompt must not carry: branch, item selection,
# fresh-context invocation, check execution, attempts/BLOCKED bookkeeping,
# checkpoints, stop conditions, PR.
#
# Preconditions (checked below): git, jq, gh, claude on PATH; clean tree;
# plans/prd.json with approved:true.
#
# VERIFY BEFORE FIRST RUN: the exact non-interactive flags of `claude -p`
# (allowed tools / permission mode) for the installed Claude Code version —
# `claude --help`. Without them the loop hangs on the first permission prompt.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRD=plans/prd.json
SPEC=plans/SPEC.md
BLOCKED=plans/BLOCKED.md
CHECKPOINT_EVERY=5
MAX_ATTEMPTS=3
MAX_CONSECUTIVE_BLOCKED=3
MAX_ITEMS=40   # hard cap from assets/prd.schema.json
if [[ -n ${CLAUDE_FLAGS:-} ]]; then read -ra CLAUDE_FLAGS <<<"$CLAUDE_FLAGS"   # override via env, space-separated
else CLAUDE_FLAGS=(--allowedTools "Bash,Read,Edit,Write,Glob,Grep"); fi       # VERIFY

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  cat <<'EOF'
Usage: loop.sh [-h|--help]
Env: CLAUDE_FLAGS="..." overrides default claude flags (space-separated).
Examples:
  skills/poc-spec-loop/assets/loop.sh
  CLAUDE_FLAGS="--allowedTools Bash,Read" skills/poc-spec-loop/assets/loop.sh
Exit codes:
  0  success (ready PR, or draft PR when blocked/unreachable items remain)
  2  usage or preconditions failed (bad flag; missing tool; dirty tree; prd.json missing or not approved)
  3  blocked stop (3 consecutive blocked items, or prd-01/prd-02 blocked)
EOF
  exit 0
fi
if [[ $# -gt 0 ]]; then echo "unknown argument: $1 (see --help)" >&2; exit 2; fi

# ---------- preconditions ----------
for bin in git jq gh claude; do command -v "$bin" >/dev/null || { echo "missing: $bin" >&2; exit 2; }; done
[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean" >&2; exit 2; }
[[ -f $PRD ]] || { echo "$PRD missing — run Phase 1" >&2; exit 2; }
[[ "$(jq -r .approved "$PRD")" == "true" ]] || { echo "prd.json not approved" >&2; exit 2; }

# ---------- branch ----------
BRANCH=$(jq -r '.branch // empty' "$PRD")
if [[ -z $BRANCH ]]; then
  BRANCH="poc/$(date +%F)"
  git switch -c "$BRANCH" main
  jq --arg b "$BRANCH" '.branch=$b' "$PRD" > "$PRD.tmp" && mv "$PRD.tmp" "$PRD"
  git commit -qam "chore(plans): start loop on $BRANCH"
else
  git switch "$BRANCH"
fi
BASE=$(git merge-base main "$BRANCH")

# ---------- helpers ----------
next_item() {   # first item: not passed, attempts<MAX, all deps passed, check != null
  jq -r --argjson m "$MAX_ATTEMPTS" '
    .items as $all
    | [ .items[] | select(.passes==false and .attempts<$m and .check!=null)
        | select( all(.deps[]; . as $d | ($all[] | select(.id==$d) | .passes)) ) ]
    | first // empty | .id' "$PRD"
}
set_field() { jq --arg id "$1" --arg k "$2" --argjson v "$3" \
  '(.items[] | select(.id==$id))[$k]=$v' "$PRD" > "$PRD.tmp" && mv "$PRD.tmp" "$PRD"; }
render_prompt() {   # crude template fill; swap for envsubst/jinja if it grows
  local id=$1 tpl; tpl=$(<"$SKILL_DIR/assets/task-prompt.md")
  local item; item=$(jq -c --arg id "$id" '.items[]|select(.id==$id)' "$PRD")
  tpl=${tpl//\{\{SPEC_MD\}\}/$(<"$SPEC")}
  tpl=${tpl//\{\{ID\}\}/$id}
  tpl=${tpl//\{\{TITLE\}\}/$(jq -r .title <<<"$item")}
  tpl=${tpl//\{\{DETAIL\}\}/$(jq -r '.detail // ""' <<<"$item")}
  tpl=${tpl//\{\{CHECK\}\}/$(jq -r .check <<<"$item")}
  tpl=${tpl//\{\{ATTEMPT\}\}/$(( $(jq -r .attempts <<<"$item") + 1 ))}
  tpl=${tpl//\{\{TOOLCHAINS_MD\}\}/$SKILL_DIR/references/toolchains.md}
  local lf="plans/.last_failure_$id"
  if [[ -s $lf ]]; then tpl=${tpl//\{\{LAST_FAILURE\}\}/$(<"$lf")}; tpl=${tpl//\{\{#LAST_FAILURE\}\}/}; tpl=${tpl//\{\{\/LAST_FAILURE\}\}/}
  else tpl=$(sed '/{{#LAST_FAILURE}}/,/{{\/LAST_FAILURE}}/d' <<<"$tpl"); fi
  printf '%s' "$tpl"
}
block_item() {
  local id=$1 reason=$2
  { echo "## $id — $(jq -r --arg id "$id" '.items[]|select(.id==$id)|.title' "$PRD")"; echo; echo '```'; echo "$reason"; echo '```'; echo; } >> "$BLOCKED"
  git add "$BLOCKED" "$PRD"; git commit -qm "chore(plans): block $id"
}
checkpoint() {   # every CHECKPOINT_EVERY passed items: code-review since BASE
  local room; room=$(( MAX_ITEMS - $(jq '.items|length' "$PRD") ))
  claude -p "Use the mattpocock-skills:code-review skill if available in this session; otherwise review the diff yourself. \
Review changes since $BASE against plans/SPEC.md (Spec) and the repo's lint/test conventions (Standards). \
For each Spec finding, append a new item to plans/prd.json (next free prd-NN id, origin:checkpoint, deps on the causing id, check command, passes:false, attempts:0), \
but at most $room new items (schema cap $MAX_ITEMS); put any further Spec findings into plans/REVIEW.md under 'Spec (over cap)'. \
Write Standards findings to plans/REVIEW.md only. Commit as 'chore(plans): checkpoint findings'." "${CLAUDE_FLAGS[@]}"
}
unreachable_items() {   # open items with a check that next_item can never select (a dep is blocked)
  jq -r --argjson m "$MAX_ATTEMPTS" \
    '.items[] | select(.passes==false and .check!=null and .attempts<$m) | "- \(.id) \(.title) (deps: \(.deps|join(", ")))"' "$PRD"
}
open_pr() {
  local kind=$1   # draft|ready
  git push -u origin "$BRANCH"
  local body; body=$(jq -r '.items[] | "- [\(if .passes then "x" else " " end)] \(.id) \(.title)\(if .manual_reason then " — MANUAL: " + .manual_reason else "" end)"' "$PRD")
  [[ -f $BLOCKED ]] && body+=$'\n\n## Blocked\n'"$(tail -c 8000 "$BLOCKED")"
  [[ -f plans/REVIEW.md ]] && body+=$'\n\n## Standards findings\n'"$(tail -c 8000 plans/REVIEW.md)"
  local unreach; unreach=$(unreachable_items)
  [[ -n $unreach ]] && body+=$'\n\n## Unreachable (a dependency is blocked)\n'"$unreach"
  body+=$'\n\n## Deployment\n'"$(awk '/^## Definition of Done/{f=1;next} /^## /{f=0} f' "$SPEC")"
  local extra=(); [[ $kind == draft ]] && extra=(--draft)
  gh pr create --base main --head "$BRANCH" --title "PoC loop $BRANCH" --body "$body" "${extra[@]}"
}

# ---------- loop ----------
consecutive_blocked=0; passed_since_checkpoint=0
while id=$(next_item) && [[ -n $id ]]; do
  echo "== $id"
  out=$(claude -p "$(render_prompt "$id")" "${CLAUDE_FLAGS[@]}" 2>&1 | tee "plans/.run_$id.log") || true
  if grep -q '^BLOCKED:' <<<"$out"; then
    set_field "$id" attempts "$MAX_ATTEMPTS"; block_item "$id" "$(grep '^BLOCKED:' <<<"$out")"
    consecutive_blocked=$((consecutive_blocked+1))
  elif check_out=$(bash -c "$(jq -r --arg id "$id" '.items[]|select(.id==$id)|.check' "$PRD")" 2>&1); then
    set_field "$id" passes true; rm -f "plans/.last_failure_$id"
    git add "$PRD"; git commit -qm "chore(plans): $id passes"
    consecutive_blocked=0; passed_since_checkpoint=$((passed_since_checkpoint+1))
  else
    n=$(( $(jq -r --arg id "$id" '.items[]|select(.id==$id)|.attempts' "$PRD") + 1 ))
    set_field "$id" attempts "$n"; printf '%s' "$check_out" | tail -c 4000 > "plans/.last_failure_$id"
    if (( n >= MAX_ATTEMPTS )); then block_item "$id" "$check_out"; consecutive_blocked=$((consecutive_blocked+1)); else git add "$PRD"; git commit -qm "chore(plans): $id attempt $n failed"; fi
  fi
  # stop conditions
  if (( consecutive_blocked >= MAX_CONSECUTIVE_BLOCKED )) || { [[ $id == prd-01 || $id == prd-02 ]] && grep -q "^## $id" "$BLOCKED" 2>/dev/null; }; then
    echo "STOP: blocked run" >&2; open_pr draft; exit 3
  fi
  if (( passed_since_checkpoint >= CHECKPOINT_EVERY )); then checkpoint; passed_since_checkpoint=0; fi
done

# ---------- end of run ----------
if [[ -n $(unreachable_items) ]] || [[ -s $BLOCKED ]]; then
  echo "END: blocked or unreachable items remain" >&2; open_pr draft
else
  open_pr ready
fi
