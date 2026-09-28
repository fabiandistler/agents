#!/usr/bin/env python3
"""Pick the skills the weekly skill audit reviews by hand this run.

Usage: python3 scripts/skill_audit_select.py [--since-days N] [--slices K] [--week W] [--max M]

Selection = the rotating slice (sorted skill names where index % K == W % K)
          + skills whose files changed in the last N days, most churned first,
            until M skills are selected.
Every skill is thus reviewed at least once per K weeks, changed ones sooner,
and a busy week cannot turn the run into a full (expensive) audit.

Options:
  --since-days N  window for "changed" (default 7)
  --slices K      rotation length in weeks (default 4; 1 = every skill every run)
  --week W        ISO week number to use for the slice (default: current week)
  --max M         cap on selected skills (default 12); the slice is never cut

Output: one JSON object on stdout:
  {"week", "slice", "slices", "changed", "rotation", "selected", "deferred"}
  changed is ordered by churn; deferred = changed skills over the cap.

Exit codes: 0 ok, 2 bad arguments, 3 not run inside this repo / git failed.

Examples:
  python3 scripts/skill_audit_select.py
  python3 scripts/skill_audit_select.py --slices 1   # full audit
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path("skills")


def skill_names() -> list[str]:
    # Router members are symlinks into skills/<name>/, so top-level dirs are
    # the complete, de-duplicated set.
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def changed_skills(since_days: int, known: set[str]) -> list[str]:
    """Skills touched in the window, most churned (added + deleted lines) first."""
    out = subprocess.run(
        [
            "git",
            "log",
            f"--since={since_days} days ago",
            "--numstat",
            "--format=",
            "--",
            str(SKILLS_DIR),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    churn: dict[str, int] = {}
    for line in out.splitlines():
        cols = line.split("\t")
        if len(cols) != 3:
            continue
        parts = Path(cols[2]).parts
        if len(parts) >= 2 and parts[1] in known:
            # Binary files report "-"; count them as one line.
            lines = sum(int(c) if c.isdigit() else 1 for c in cols[:2])
            churn[parts[1]] = churn.get(parts[1], 0) + lines
    return sorted(churn, key=lambda n: (-churn[n], n))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pick the skills the weekly skill audit reviews this run.",
        epilog="Exit codes: 0 ok, 2 bad arguments, 3 not in repo / git failed.",
    )
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--slices", type=int, default=4)
    parser.add_argument(
        "--week", type=int, default=datetime.datetime.now(datetime.timezone.utc).isocalendar()[1]
    )
    parser.add_argument("--max", type=int, default=12)
    args = parser.parse_args()
    if min(args.since_days, args.slices, args.max) < 1:
        print("--since-days, --slices and --max must be >= 1", file=sys.stderr)
        return 2
    if not (SKILLS_DIR.is_dir() and Path("scripts/build_manifest.py").is_file()):
        print("run from the repository root (skills/ not found)", file=sys.stderr)
        return 3

    names = skill_names()
    try:
        # A shallow clone silently truncates `git log --since`; warn only when
        # the oldest reachable commit is younger than the window.
        stamps = subprocess.run(
            ["git", "log", "--format=%ct"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        oldest = min(stamps, key=int, default="")
        window_start = (
            datetime.datetime.now(datetime.timezone.utc).timestamp() - args.since_days * 86400
        )
        if oldest and int(oldest) > window_start:
            print(
                f"warning: history ends inside the window; 'changed' is incomplete. "
                f"Run: git fetch --shallow-since='{args.since_days + 1} days ago'",
                file=sys.stderr,
            )
        changed = changed_skills(args.since_days, set(names))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"git log failed: {exc}", file=sys.stderr)
        return 3
    slice_idx = args.week % args.slices
    rotation = [n for i, n in enumerate(names) if i % args.slices == slice_idx]
    extra = [n for n in changed if n not in rotation]
    room = max(args.max - len(rotation), 0)
    print(
        json.dumps(
            {
                "week": args.week,
                "slice": slice_idx,
                "slices": args.slices,
                "changed": changed,
                "rotation": rotation,
                "selected": sorted(rotation + extra[:room]),
                "deferred": extra[room:],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
