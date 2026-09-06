#!/usr/bin/env python3
"""Live trigger check: does a router actually fire inside the agent?

Run from repo root:
    python3 eval-suite/recall/check_live.py --category architecture
    python3 eval-suite/recall/check_live.py --category architecture --flat
    python3 eval-suite/recall/check_live.py --category architecture --reps 3 --model claude-opus-5

`check_recall.py` shows the model a *menu* of descriptions and forces it to pick
one. That measures which skill wins once the model has decided to consult a
skill at all; it cannot see the more common failure, where the model answers an
architecture question from its own knowledge and never opens the router. This
check measures that: it starts a real `claude -p` session with the repo's
plugins loaded, sends one realistic prompt, and records from the event stream
whether the router skill was invoked and which member `SKILL.md` was read.

Each prompt in `live_prompts.json` names the `category` it belongs to and an
`expected` member name, `any` (the router should fire, the member is a
judgement call) or `none` (a near-miss that must not fire). Prompts are run
`--reps` times each because triggering is stochastic; report rates, not single
runs.

Three surfaces can reach a member: the router hands off to it, the model reads
its `SKILL.md` directly, or a plugin subagent that works from that member is
launched and the router never opens at all. Each run records which surface got
there first and the report prints the tally, so a category's numbers say where
the triggering actually happens.

`--flat` swaps the category's router for a throwaway plugin that registers
every member individually — the pre-router layout — so the two can be
compared on the same prompts and model.

Needs the `claude` CLI on PATH; prints SKIP and exits 0 without it. Every run
costs real tokens (roughly 30-60 s and a few cents each). Stdlib-only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
MANIFEST_PATH = REPO_ROOT / "skills.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
PROMPTS_PATH = HERE / "live_prompts.json"

# The router hop rarely needs more than: explore (optional) -> router -> member.
MAX_TURNS = 3
# Read-only tools are enough to observe the routing, plus Agent, because a
# plugin subagent is one of the surfaces under measurement. Bash is denied to
# the session on purpose so a run cannot shell out around the routing; a
# subagent brings its own tool list, which is why the workdir is a throwaway.
ALLOWED_TOOLS = "Skill,Read,Glob,Grep,Agent"


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["skills"]


def members_of(skills: list[dict], category: str) -> list[str]:
    return [
        s["name"]
        for s in skills
        if s.get("category") == category and s.get("activation") not in ("command", "router")
    ]


def router_of(skills: list[dict], category: str) -> str | None:
    for s in skills:
        if s.get("category") == category and s.get("activation") == "router":
            return s["name"]
    return None


def make_flat_plugin(category: str, members: list[str], tmp: Path) -> Path:
    """A throwaway plugin that registers every member of the category flat."""
    plugin = tmp / f"{category}-flat"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": category, "description": f"{category} members, flat (live check)"}),
        encoding="utf-8",
    )
    skills_dir = plugin / "skills"
    skills_dir.mkdir()
    for m in members:
        (skills_dir / m).symlink_to(REPO_ROOT / "skills" / m, target_is_directory=True)
    return plugin


def agents_of(category: str, members: list[str]) -> dict[str, str]:
    """Plugin subagent name -> the member it works from.

    A subagent is a second way into a member: it reads that member's `SKILL.md`
    itself, so the router never fires. The mapping is read from the agent files,
    which name the member directory they work from.
    """
    found: dict[str, str] = {}
    agents_dir = PLUGINS_DIR / category / "agents"
    if not agents_dir.is_dir():
        return found
    for agent in sorted(agents_dir.glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        for m in members:
            if f"members/{m}/" in text:
                found[agent.stem] = m
                break
    return found


def make_workdir(tmp: Path) -> Path:
    """A tiny git project so prompts that say 'this repo' have a repo to look at.

    Identity and default branch are passed per invocation, so the commit works
    without a global git config and without writing one.
    """
    proj = tmp / "proj"
    (proj / "app").mkdir(parents=True)
    (proj / "tests").mkdir()
    (proj / "app" / "utils.py").write_text(
        "def paginate(items, page, size):\n    return items[page * size:(page + 1) * size]\n",
        encoding="utf-8",
    )
    (proj / "tests" / "test_utils.py").write_text(
        "from app.utils import paginate\n\n\ndef test_paginate():\n    assert paginate([1, 2, 3], 1, 2) == [3]\n",
        encoding="utf-8",
    )
    config = [
        "-c",
        "init.defaultBranch=main",
        "-c",
        "user.name=check_live",
        "-c",
        "user.email=check_live@example.invalid",
        "-c",
        "commit.gpgsign=false",
    ]
    for git_args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "Initial commit"]):
        subprocess.run(
            ["git", "-C", str(proj), *config, *git_args], check=True, capture_output=True
        )
    return proj


def run_prompt(prompt: str, plugin_dirs: list[Path], workdir: Path, model: str | None) -> list[str]:
    cmd = ["claude", "-p", prompt, "--setting-sources", "project"]
    for d in plugin_dirs:
        cmd += ["--plugin-dir", str(d)]
    cmd += [
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(MAX_TURNS),
        "--allowedTools",
        ALLOWED_TOOLS,
    ]
    if model:
        cmd += ["--model", model]
    result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=600)
    # A max-turns exit is expected and still carries the events we need.
    return result.stdout.splitlines()


def observe(
    lines: list[str], router: str | None, members: list[str], agents: dict[str, str]
) -> tuple[bool, str | None, str | None]:
    """(router invoked?, first member reached, surface that got there) from a transcript.

    A member counts as reached when its SKILL.md is read (the routed path), when
    it is invoked as a skill of its own (the flat layout), or when a subagent
    that works from it is launched. The surface is whichever came first.
    """
    fired = False
    member: str | None = None
    via: str | None = None
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event["message"]["content"]:
            if block.get("type") != "tool_use":
                continue
            if block["name"] == "Skill":
                name = str(block["input"].get("skill", "")).split(":")[-1]
                if router and name == router:
                    fired = True
                    via = via or "router"
                elif name in members:
                    member = member or name
                    via = via or "skill"
            elif block["name"] == "Read":
                path = str(block["input"].get("file_path", ""))
                for m in members:
                    if f"/{m}/SKILL.md" in path:
                        member = member or m
                        via = via or "read"
            elif "subagent_type" in block.get("input", {}):
                agent = str(block["input"]["subagent_type"]).split(":")[-1]
                if agent in agents:
                    member = member or agents[agent]
                    via = via or "subagent"
    return fired, member, via


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--category", required=True, help="routed category to check")
    parser.add_argument(
        "--flat", action="store_true", help="register the members flat instead of the router"
    )
    parser.add_argument("--reps", type=int, default=3, help="runs per prompt (default 3)")
    parser.add_argument("--workers", type=int, default=4, help="parallel claude sessions")
    parser.add_argument("--model", default=None, help="model id (default: the CLI's default)")
    parser.add_argument("--only", help="comma-separated prompt ids to run")
    args = parser.parse_args()

    skills = load_manifest()
    members = members_of(skills, args.category)
    router = router_of(skills, args.category)
    if not members:
        sys.stderr.write(f"no members in category {args.category!r}\n")
        return 2
    if router is None and not args.flat:
        sys.stderr.write(f"category {args.category!r} has no router; use --flat\n")
        return 2

    prompts = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))["prompts"]
    prompts = [
        p
        for p in prompts
        if p["category"] == args.category
        and (p["expected"] in ("any", "none") or p["expected"] in members)
    ]
    if args.only:
        wanted = set(args.only.split(","))
        prompts = [p for p in prompts if p["id"] in wanted]

    if shutil.which("claude") is None:
        print("SKIP: `claude` CLI not on PATH — cannot run the live trigger check.")
        return 0

    with tempfile.TemporaryDirectory(prefix="live-trigger-") as tmp_s:
        tmp = Path(tmp_s)
        plugin_dirs = [p for p in sorted(PLUGINS_DIR.iterdir()) if (p / ".claude-plugin").is_dir()]
        layout = "routed"
        agents = agents_of(args.category, members)
        if args.flat:
            plugin_dirs = [p for p in plugin_dirs if p.name != args.category]
            plugin_dirs.append(make_flat_plugin(args.category, members, tmp))
            layout = "flat"
            router = None
            agents = {}
        workdir = make_workdir(tmp)
        jobs = [(p, r) for p in prompts for r in range(args.reps)]
        print(
            f"category {args.category} ({layout}) | model {args.model or 'default'} | "
            f"{len(prompts)} prompts x {args.reps} reps = {len(jobs)} runs"
        )

        results: dict[str, list[tuple[bool, str | None, str | None]]] = {
            p["id"]: [] for p in prompts
        }
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(run_prompt, p["prompt"], plugin_dirs, workdir, args.model): p
                for p, _ in jobs
            }
            for fut in concurrent.futures.as_completed(futures):
                p = futures[fut]
                results[p["id"]].append(observe(fut.result(), router, members, agents))

    print(f"\n{'prompt':16} {'expected':30} {'fired':7} {'member reached':34} via")
    fired_pos = ok_pos = n_pos = fired_neg = n_neg = 0
    paths: Counter[str] = Counter()
    for p in prompts:
        obs = results[p["id"]]
        # In the flat layout there is no router; reaching any member is the fire.
        fired = sum(1 for f, m, _ in obs if f or (args.flat and m))
        picked = Counter(m or "-" for _, m, _ in obs)
        taken = Counter(v or "-" for _, _, v in obs)
        if p["expected"] == "none":
            n_neg += len(obs)
            fired_neg += fired
        else:
            paths.update(taken)
            if p["expected"] != "any":
                n_pos += len(obs)
                fired_pos += fired
                ok_pos += sum(1 for _, m, _ in obs if m == p["expected"])
        print(
            f"{p['id']:16} {p['expected']:30} {fired}/{len(obs):5} "
            f"{str(dict(picked)):34} {dict(taken)}"
        )
    print(f"\npositives: fired {fired_pos}/{n_pos}, expected member reached {ok_pos}/{n_pos}")
    print(f"paths taken (non-negatives): {dict(paths)}")
    if n_neg:
        print(f"negatives: fired {fired_neg}/{n_neg} (should be 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
