#!/usr/bin/env python3
"""Trigger-recall A/B: does routing hurt which skill the model would pick?

Run from repo root (or anywhere):
    python3 eval-suite/recall/check_recall.py            # A/B flat vs routed
    python3 eval-suite/recall/check_recall.py --dry-run  # print menus, no model calls
    python3 eval-suite/recall/check_recall.py --category architecture

Issue #50 gates flipping a category to a router on "no trigger-recall
regression vs. the flat baseline". The existing eval-suite force-injects the
skill and only grades output quality, so it cannot answer that question. This
standalone check does: over a set of labelled prompts (prompts.json) it shows
the model two menus of skill descriptions —

  * flat   — every auto skill listed individually (the pre-router world), and
  * routed — one broad router entry per routed category, plus the individual
             skills of non-routed categories,

— asks which single skill it would use for each prompt, and compares recall.
A pick counts as a hit when it names the expected skill; in the routed menu,
naming the router of the expected skill's category also counts (the router is
the correct next hop — it then routes to the sub-skill).

The gate: routed recall must be >= flat recall minus --tolerance (default 0).

Model calls go through the `claude` CLI (same dependency as the eval-suite
judge). If it is absent, the check skips with a clear message instead of
failing, so CI without model access stays green. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
MANIFEST_PATH = REPO_ROOT / "skills.json"
PROMPTS_PATH = HERE / "prompts.json"
DEFAULT_MODEL = "claude-sonnet-4-5"


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["skills"]


def routed_categories(skills: list[dict]) -> dict[str, str]:
    """category -> router skill name, for every activation: router skill."""
    return {
        s["category"]: s["name"] for s in skills if s.get("activation") == "router"
    }


def category_of(skills: list[dict], name: str) -> str | None:
    for s in skills:
        if s["name"] == name:
            return s["category"]
    return None


def build_menus(skills: list[dict]) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Return (flat_menu, routed_menu, category->router).

    Menus are lists of {name, summary}. Command skills are user-invoked and
    excluded from both. Flat has no routers and lists every auto skill. Routed
    replaces each routed category's members with its single router entry.
    """
    routers = routed_categories(skills)
    flat, routed = [], []
    for s in skills:
        act = s.get("activation")
        if act == "command":
            continue
        entry = {"name": s["name"], "summary": s["summary"]}
        if act == "router":
            # Routers exist only in the routed world.
            routed.append(entry)
            continue
        # A plain auto skill.
        flat.append(entry)
        if s["category"] not in routers:
            routed.append(entry)
    flat.sort(key=lambda e: e["name"])
    routed.sort(key=lambda e: e["name"])
    return flat, routed, routers


def render_menu(menu: list[dict]) -> str:
    return "\n".join(f"- {e['name']}: {e['summary']}" for e in menu)


def ask_model(model: str, menu: list[dict], prompt: str) -> str:
    menu_text = render_menu(menu)
    instruction = (
        "You are routing a user request to exactly one skill from a fixed menu.\n"
        "Reply with ONLY the skill name (the token before the colon), nothing "
        "else. If none fit, reply NONE.\n\n"
        f"MENU:\n{menu_text}\n\nUSER REQUEST:\n{prompt}\n\nSkill name:"
    )
    result = subprocess.run(
        ["claude", "-p", instruction, "--model", model],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI failed")
    return result.stdout.strip().split()[0].strip(".,`\"'") if result.stdout.strip() else "NONE"


def score(
    label: str,
    menu: list[dict],
    prompts: list[dict],
    skills: list[dict],
    routers: dict[str, str],
    model: str,
    routed_menu: bool,
) -> tuple[int, list[str]]:
    hits = 0
    misses: list[str] = []
    valid = {e["name"] for e in menu}
    for item in prompts:
        expected = item["expected"]
        want = {expected}
        if routed_menu:
            cat = category_of(skills, expected)
            if cat in routers:
                # In the routed world the sub-skill is hidden; the router is the
                # correct pick (it then routes to the sub-skill).
                want = {routers[cat]}
        choice = ask_model(model, menu, item["prompt"])
        if choice in want:
            hits += 1
        else:
            misses.append(f"{label}: {expected!r} -> picked {choice!r}")
    _ = valid  # (kept for future strict-menu validation)
    return hits, misses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print menus, no model calls")
    parser.add_argument("--tolerance", type=int, default=0, help="allowed recall drop (count)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--category", help="only score prompts whose expected skill is in this category")
    args = parser.parse_args()

    skills = load_manifest()
    flat, routed, routers = build_menus(skills)
    prompts = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))["prompts"]
    if args.category:
        prompts = [p for p in prompts if category_of(skills, p["expected"]) == args.category]
        if not prompts:
            sys.stderr.write(f"no prompts for category {args.category!r}\n")
            return 2

    print(f"flat menu: {len(flat)} entries | routed menu: {len(routed)} entries")
    print(f"routed categories: {', '.join(sorted(routers)) or '(none)'}")
    print(f"prompts: {len(prompts)}")

    if args.dry_run:
        print("\n--- FLAT MENU ---\n" + render_menu(flat))
        print("\n--- ROUTED MENU ---\n" + render_menu(routed))
        return 0

    if shutil.which("claude") is None:
        print("\nSKIP: `claude` CLI not on PATH — cannot run model recall A/B.")
        return 0

    flat_hits, flat_miss = score("flat", flat, prompts, skills, routers, args.model, False)
    routed_hits, routed_miss = score("routed", routed, prompts, skills, routers, args.model, True)

    n = len(prompts)
    print(f"\nflat recall:   {flat_hits}/{n}")
    print(f"routed recall: {routed_hits}/{n}")
    for m in flat_miss + routed_miss:
        print(f"  miss: {m}")

    regression = flat_hits - routed_hits
    if regression > args.tolerance:
        sys.stderr.write(
            f"\nFAIL: routed recall regressed by {regression} (> tolerance {args.tolerance}).\n"
            "Do not flip these categories to routers, or broaden the router description.\n"
        )
        return 1
    print(f"\nPASS: routed recall within tolerance (drop {max(regression, 0)} <= {args.tolerance}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
