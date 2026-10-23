#!/usr/bin/env python3
"""Validate the agent instruction fragments in instructions/.

Run from repo root:
    python3 scripts/check_instructions.py    # exit 1 on any invalid fragment

install.sh --instructions composes these fragments into the managed block in
each agent's global instruction file. Composition is plain concatenation in
filename order, so most mistakes never surface as a broken render — a typo in
`targets:` silently drops a rule from an agent instead of failing loudly, a
malformed `paths:` glob makes Claude load a path-scoped rule everywhere, and
two fragments sharing a numeric prefix reorder on any filesystem whose glob
order differs. This check is where those become errors.

Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from instruction_fragments import InstructionFragmentError, load_fragment, validate_fragment

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"

# install.sh orders fragments by glob, so every name needs a numeric prefix.
FILENAME = re.compile(r"^(\d{2})-[a-z0-9-]+\.md$")


def main() -> int:
    if not INSTRUCTIONS_DIR.is_dir():
        sys.stderr.write(f"missing directory: {INSTRUCTIONS_DIR}\n")
        return 1

    errors: list[str] = []
    prefixes: dict[str, str] = {}
    count = 0

    for path in sorted(INSTRUCTIONS_DIR.glob("*.md")):
        name = path.name
        count += 1
        m = FILENAME.match(name)
        if not m:
            errors.append(f"{name}: expected a NN-slug.md name (e.g. 10-python.md)")
        else:
            prefix = m.group(1)
            if prefix in prefixes:
                errors.append(
                    f"{name}: numeric prefix {prefix} already used by"
                    f" {prefixes[prefix]}; order would be ambiguous"
                )
            else:
                prefixes[prefix] = name

        try:
            fragment = load_fragment(path)
        except InstructionFragmentError as error:
            errors.append(str(error))
            continue
        errors.extend(f"{name}: {error}" for error in validate_fragment(fragment))

    if count == 0:
        errors.append(f"no fragments found in {INSTRUCTIONS_DIR}")

    if errors:
        sys.stderr.write("invalid instruction fragments:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    print(f"instruction fragments ok ({count} fragments)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
