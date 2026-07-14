#!/usr/bin/env python3
"""Apply the Balanced Coupling rule to a list of assessed dependencies.

Implements the binary form of Vlad Khononov's balance rule (*Balancing
Coupling in Software Design*, Addison-Wesley 2024; coupling.dev):

    MODULARITY = STRENGTH XOR DISTANCE
    BALANCE    = (STRENGTH XOR DISTANCE) OR NOT VOLATILITY

Each edge is an already-made qualitative assessment (see the skill's
workflow steps 2-4); this script only reduces the levels to high/low,
applies the rule uniformly, and sorts the trouble to the top.

Input is JSON (see scripts/example_input.json):

    {
      "level": "service",
      "edges": [
        {"from": "web", "to": "billing",
         "strength": "contract", "distance": "service",
         "volatility": "low", "note": "versioned REST API"}
      ]
    }

Accepted values (aliases for high/low are reduced as shown):

    strength:   intrusive | functional | model  -> high
                contract                        -> low
    distance:   function | class | package      -> low
                component | service | system    -> high
    volatility: core                            -> high
                generic | supporting            -> low

`strength`, `distance`, and `volatility` also accept literal "high"/"low" —
use those to override an alias near a threshold (e.g. a supporting subdomain
under roadmap pressure is better stated as volatility "high").

Verdicts, worst first:

    knowledge leak   strength AND distance AND volatility   (imbalanced)
    low cohesion     neither strength nor distance, volatile (imbalanced)
    stable leak      strength AND distance, stable           (tolerated)
    stable clutter   neither, stable                         (tolerated)
    high cohesion    strength without distance               (balanced)
    loose coupling   distance without strength               (balanced)

Usage:
    python3 balance_check.py input.json
    python3 balance_check.py input.json --json

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class InputError(Exception):
    """Raised when the input file is malformed."""


STRENGTH = {
    "intrusive": True,
    "functional": True,
    "model": True,
    "contract": False,
    "high": True,
    "low": False,
}

DISTANCE = {
    "function": False,
    "class": False,
    "package": False,
    "component": True,
    "service": True,
    "system": True,
    "high": True,
    "low": False,
}

VOLATILITY = {
    "core": True,
    "supporting": False,
    "generic": False,
    "high": True,
    "low": False,
}

# (strength, distance, volatility) -> (rank, verdict, balance label)
VERDICTS = {
    (True, True, True): (0, "knowledge leak", "IMBALANCED"),
    (False, False, True): (1, "low cohesion", "IMBALANCED"),
    (True, True, False): (2, "stable leak", "tolerated"),
    (False, False, False): (3, "stable clutter", "tolerated"),
    (True, False, True): (4, "high cohesion", "balanced"),
    (True, False, False): (4, "high cohesion", "balanced"),
    (False, True, True): (5, "loose coupling", "balanced"),
    (False, True, False): (5, "loose coupling", "balanced"),
}


def reduce_level(edge: dict, field: str, scale: dict[str, bool]) -> bool:
    value = edge.get(field)
    if not isinstance(value, str) or value.lower() not in scale:
        raise InputError(
            f"edge {edge.get('from')!r} -> {edge.get('to')!r}: "
            f"{field} must be one of {', '.join(sorted(scale))}; got {value!r}"
        )
    return scale[value.lower()]


def load_edges(path: Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"no such file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON ({exc})") from exc
    edges = raw.get("edges") if isinstance(raw, dict) else None
    if not isinstance(edges, list) or not edges:
        raise InputError(f"{path}: expected a non-empty 'edges' list")
    return edges


def assess(edges: list[dict]) -> list[dict]:
    rows = []
    for edge in edges:
        if not edge.get("from") or not edge.get("to"):
            raise InputError(f"edge missing 'from'/'to': {edge!r}")
        strength = reduce_level(edge, "strength", STRENGTH)
        distance = reduce_level(edge, "distance", DISTANCE)
        volatility = reduce_level(edge, "volatility", VOLATILITY)
        rank, verdict, balance = VERDICTS[(strength, distance, volatility)]
        rows.append(
            {
                "from": edge["from"],
                "to": edge["to"],
                "strength": edge["strength"].lower(),
                "distance": edge["distance"].lower(),
                "volatility": edge["volatility"].lower(),
                "verdict": verdict,
                "balance": balance,
                "note": edge.get("note", ""),
                "_rank": rank,
            }
        )
    rows.sort(key=lambda r: (r["_rank"], r["from"], r["to"]))
    for row in rows:
        del row["_rank"]
    return rows


def render_table(rows: list[dict]) -> str:
    headers = ["From", "To", "Strength", "Distance", "Volatility", "Verdict", "Balance", "Note"]
    cells = [
        [
            r["from"],
            r["to"],
            r["strength"],
            r["distance"],
            r["volatility"],
            r["verdict"],
            r["balance"],
            r["note"],
        ]
        for r in rows
    ]
    widths = [max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)]

    def line(row: list[str]) -> str:
        return "| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |"

    out = [line(headers), line(["-" * w for w in widths])]
    out.extend(line(row) for row in cells)
    flagged = sum(r["balance"] == "IMBALANCED" for r in rows)
    tolerated = sum(r["balance"] == "tolerated" for r in rows)
    out.append("")
    out.append(
        f"{len(rows)} dependencies: {flagged} imbalanced, "
        f"{tolerated} tolerated on low volatility (need a revisit "
        f"condition), {len(rows) - flagged - tolerated} balanced."
    )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Apply the Balanced Coupling rule to assessed dependencies."
    )
    parser.add_argument("input", type=Path, help="JSON file with edges")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)
    try:
        rows = assess(load_edges(args.input))
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(render_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
