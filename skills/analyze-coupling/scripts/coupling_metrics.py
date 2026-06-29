#!/usr/bin/env python3
"""Compute component-coupling metrics from a dependency-edge list.

Implements the metrics from Robert C. Martin / Richards & Ford
(*Fundamentals of Software Architecture*, ch. 3):

    Ce = efferent (outgoing) coupling   -> distinct components this one depends on
    Ca = afferent (incoming) coupling   -> distinct components that depend on it
    I  = Instability    = Ce / (Ce + Ca)            in [0, 1]
    A  = Abstractness   = abstract / (abstract + concrete)   in [0, 1]
    D  = Distance from the Main Sequence = |A + I - 1|        in [0, 1]

A component far from the Main Sequence (large D) sits toward one of two
trouble corners:
    A + I < 1  -> Zone of Pain        (concrete + stable -> brittle, hard to change)
    A + I > 1  -> Zone of Uselessness (abstract + unstable -> over-built, unused)

Input is JSON (see scripts/example_input.json):

    {
      "components": [
        {"name": "core", "abstract": 8, "concrete": 2},
        {"name": "web",  "abstract": 0, "concrete": 12}
      ],
      "edges": [["web", "core"], ["web", "db"], ["core", "db"]]
    }

Each edge [A, B] means "A depends on B" (A has efferent coupling to B; B
has afferent coupling from A). Abstractness is optional per component; omit
the counts and the row reports instability only (A and D blank).

Usage:
    python3 coupling_metrics.py input.json
    python3 coupling_metrics.py input.json --json
    python3 coupling_metrics.py input.json --threshold 0.4

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class InputError(Exception):
    """Raised when the input file is malformed."""


def load_model(path: Path) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Read the JSON model into a component map and a list of edges."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"no such file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON ({exc})") from exc

    components: dict[str, dict] = {}
    for entry in raw.get("components", []):
        name = entry.get("name")
        if not name:
            raise InputError("every component needs a 'name'")
        if name in components:
            raise InputError(f"duplicate component: {name}")
        components[name] = entry

    edges: list[tuple[str, str]] = []
    for edge in raw.get("edges", []):
        if len(edge) != 2:
            raise InputError(f"edge must be a [source, target] pair: {edge!r}")
        src, dst = edge
        # An edge can introduce a component not separately declared; that is
        # fine -- treat it as having no abstractness data.
        components.setdefault(src, {"name": src})
        components.setdefault(dst, {"name": dst})
        if src != dst:  # self-edges do not count as coupling
            edges.append((src, dst))

    if not components:
        raise InputError("no components found")
    return components, edges


def abstractness(entry: dict) -> float | None:
    """A = abstract / (abstract + concrete), or None when not provided."""
    if "abstract" not in entry and "concrete" not in entry:
        return None
    abstract = entry.get("abstract", 0)
    concrete = entry.get("concrete", 0)
    total = abstract + concrete
    if total == 0:
        return None
    return abstract / total


def compute(
    components: dict[str, dict],
    edges: list[tuple[str, str]],
    threshold: float,
) -> list[dict]:
    """Return one metrics row per component, sorted by D (desc) then name."""
    efferent: dict[str, set[str]] = {name: set() for name in components}
    afferent: dict[str, set[str]] = {name: set() for name in components}
    for src, dst in edges:
        efferent[src].add(dst)
        afferent[dst].add(src)

    rows: list[dict] = []
    for name in components:
        ce = len(efferent[name])
        ca = len(afferent[name])
        instability = ce / (ce + ca) if (ce + ca) > 0 else 0.0
        abstract = abstractness(components[name])
        distance = abs(abstract + instability - 1) if abstract is not None else None
        rows.append(
            {
                "name": name,
                "Ca": ca,
                "Ce": ce,
                "I": round(instability, 3),
                "A": round(abstract, 3) if abstract is not None else None,
                "D": round(distance, 3) if distance is not None else None,
                "zone": classify(abstract, instability, distance, threshold),
            }
        )

    # Unmeasurable rows (no abstractness) sort last; otherwise worst D first.
    rows.sort(key=lambda r: (r["D"] is None, -(r["D"] or 0.0), r["name"]))
    return rows


def classify(
    abstract: float | None,
    instability: float,
    distance: float | None,
    threshold: float,
) -> str:
    """Name the zone a component falls into."""
    if abstract is None or distance is None:
        return "unknown (no abstractness data)"
    if distance <= threshold:
        return "near main sequence"
    return "Zone of Pain" if (abstract + instability) < 1 else "Zone of Uselessness"


def render_table(rows: list[dict]) -> str:
    """Render rows as a GitHub-flavored markdown table."""
    header = "| Component | Ca | Ce | I | A | D | Zone |"
    divider = "|---|---|---|---|---|---|---|"
    lines = [header, divider]
    for r in rows:
        a = "—" if r["A"] is None else f"{r['A']:.2f}"
        d = "—" if r["D"] is None else f"{r['D']:.2f}"
        lines.append(
            f"| {r['name']} | {r['Ca']} | {r['Ce']} | "
            f"{r['I']:.2f} | {a} | {d} | {r['zone']} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="path to the JSON model")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="D above which a component is flagged as off the main sequence (default 0.5)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)

    try:
        components, edges = load_model(args.input)
    except InputError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    rows = compute(components, edges, args.threshold)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(render_table(rows))
        flagged = [r["name"] for r in rows if r["zone"].startswith("Zone")]
        if flagged:
            print(f"\nOff the main sequence (D > {args.threshold}): {', '.join(flagged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
