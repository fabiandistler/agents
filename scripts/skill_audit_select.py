#!/usr/bin/env python3
"""Pick the skills the twice-monthly skill audit reviews by hand this run.

Usage: python3 scripts/skill_audit_select.py [--since-days N] [--slices K] [--date D] [--max M]

The audit is scheduled on the 8th and the 22nd of each month. Each scheduled
run gets its own number, run = (year*12 + month-1)*2 + (day >= 15), so two
consecutive runs always differ by one.

Selection = the rotating slice (sorted skill names where index % K == run % K)
          + skills whose files changed in the N days before the run date and
            on it, most churned first, until M skills are selected.
Every skill is thus reviewed at least once per K runs, changed ones sooner,
and a busy fortnight cannot turn the run into a full (expensive) audit. The
default window of 17 days covers the longest gap between two scheduled runs
(22nd to the 8th of the next month); consecutive windows may overlap.

Options:
  --since-days N  window for "changed" in days before the run date (default 17)
  --slices K      rotation length in runs (default 4; 1 = every skill every run)
  --date D        run date as YYYY-MM-DD for the slice and the window
                  (default: today, UTC)
  --max M         cap on selected skills (default 12); the slice is never cut

Output: one JSON object on stdout:
  {"date", "run", "slice", "slices", "changed", "rotation", "selected", "deferred"}
  changed is ordered by churn; deferred = changed skills over the cap.

Exit codes: 0 ok, 2 bad arguments, 3 not run inside this repo / git failed.

Examples:
  python3 scripts/skill_audit_select.py
  python3 scripts/skill_audit_select.py --slices 1   # full audit
  python3 scripts/skill_audit_select.py --date 2027-02-08
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


def run_number(run_date: datetime.date) -> int:
    """Count scheduled runs (8th and 22nd): one step per run, half-month buckets."""
    return (run_date.year * 12 + run_date.month - 1) * 2 + (run_date.day >= 15)


def change_window(
    run_date: datetime.date, since_days: int
) -> tuple[datetime.datetime, datetime.datetime]:
    """From midnight UTC `since_days` days before the run date to the end of it.

    Starting at midnight, not at the run's clock time, keeps the commits made
    on the previous run's day after it ran inside the window.
    """
    start = datetime.datetime.combine(
        run_date - datetime.timedelta(days=since_days), datetime.time(), datetime.timezone.utc
    )
    end = datetime.datetime.combine(
        run_date + datetime.timedelta(days=1), datetime.time(), datetime.timezone.utc
    )
    return start, end


def changed_skills(
    window: tuple[datetime.datetime, datetime.datetime], known: set[str]
) -> list[str]:
    """Skills touched in the window, most churned (added + deleted lines) first."""
    start, end = window
    out = subprocess.run(  # noqa: S603 -- validated Git argv; no shell.
        [  # noqa: S607 -- Git intentionally resolves from PATH.
            "git",
            "log",
            f"--since={start.isoformat()}",
            f"--until={end.isoformat()}",
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
        description=(
            "Pick the skills the twice-monthly skill audit (8th and 22nd) reviews this run: "
            "one rotating slice per run plus the skills changed since the previous run."
        ),
        epilog="Exit codes: 0 ok, 2 bad arguments, 3 not in repo / git failed.",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=17,
        help="window for 'changed' in days before the run date (default 17, the longest "
        "gap between two scheduled runs)",
    )
    parser.add_argument(
        "--slices",
        type=int,
        default=4,
        help="rotation length in runs (default 4; 1 = every skill every run)",
    )
    parser.add_argument(
        "--date",
        type=datetime.date.fromisoformat,
        default=datetime.datetime.now(datetime.timezone.utc).date(),
        help="run date as YYYY-MM-DD for the slice and the window (default: today, UTC)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=12,
        help="cap on selected skills (default 12); the slice is never cut",
    )
    args = parser.parse_args()
    if min(args.since_days, args.slices, args.max) < 1:
        print("--since-days, --slices and --max must be >= 1", file=sys.stderr)
        return 2
    if not (SKILLS_DIR.is_dir() and Path("scripts/build_manifest.py").is_file()):
        print("run from the repository root (skills/ not found)", file=sys.stderr)
        return 3

    names = skill_names()
    window = change_window(args.date, args.since_days)
    try:
        # A shallow clone silently truncates `git log --since`; warn only when
        # the oldest reachable commit is younger than the window.
        stamps = subprocess.run(
            ["git", "log", "--format=%ct"],  # noqa: S607 -- Git intentionally resolves from PATH.
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        oldest = min(stamps, key=int, default="")
        if oldest and int(oldest) > window[0].timestamp():
            print(
                f"warning: history ends inside the window; 'changed' is incomplete. "
                f"Run: git fetch --shallow-since='{window[0].date().isoformat()}'",
                file=sys.stderr,
            )
        changed = changed_skills(window, set(names))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"git log failed: {exc}", file=sys.stderr)
        return 3
    run = run_number(args.date)
    slice_idx = run % args.slices
    rotation = [n for i, n in enumerate(names) if i % args.slices == slice_idx]
    extra = [n for n in changed if n not in rotation]
    room = max(args.max - len(rotation), 0)
    print(
        json.dumps(
            {
                "date": args.date.isoformat(),
                "run": run,
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
