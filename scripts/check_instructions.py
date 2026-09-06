#!/usr/bin/env python3
"""Validate the agent instruction fragments in instructions/.

Run from repo root:
    python3 scripts/check_instructions.py    # exit 1 on any invalid fragment

install.sh --instructions composes these fragments into the managed block in
each agent's global instruction file. Composition is plain concatenation in
filename order, so most mistakes never surface as a broken render — a typo in
`targets:` silently drops a rule from an agent instead of failing loudly, and
two fragments sharing a numeric prefix reorder on any filesystem whose glob
order differs. This check is where those become errors.

Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"

# install.sh orders fragments by glob, so every name needs a numeric prefix.
FILENAME = re.compile(r"^(\d{2})-[a-z0-9-]+\.md$")
# install.sh reads frontmatter with `grep -m1 '^<field>:'`, so a field only
# counts when it starts its own line; mirror that here rather than parsing YAML.
FIELD = re.compile(r"^([a-z]+):[ \t]*(.*?)[ \t]*$", re.M)

VALID_TARGETS = frozenset({"all", "claude", "codex", "opencode"})
REQUIRED_FIELDS = ("title", "targets")


def split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    return text[4 : end + 1], text[end + 5 :]


def check_targets(value: str) -> list[str]:
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        return ["'targets' is empty (omit the field to mean every agent)"]
    errors = []
    unknown = [p for p in parts if p not in VALID_TARGETS]
    if unknown:
        errors.append(
            f"'targets' has unknown value(s) {', '.join(sorted(unknown))};"
            f" expected a comma-separated subset of {', '.join(sorted(VALID_TARGETS))}"
        )
    if "all" in parts and len(parts) > 1:
        errors.append("'targets: all' cannot be combined with named agents")
    return errors


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

        parts = split_frontmatter(path.read_text(encoding="utf-8"))
        if parts is None:
            errors.append(f"{name}: missing or unterminated '---' frontmatter block")
            continue
        frontmatter, body = parts
        fields = {k: v for k, v in FIELD.findall(frontmatter)}

        for field in REQUIRED_FIELDS:
            if not fields.get(field):
                errors.append(f"{name}: missing or empty '{field}'")

        targets = fields.get("targets")
        if targets:
            errors.extend(f"{name}: {e}" for e in check_targets(targets))

        if not body.strip():
            errors.append(f"{name}: body is empty; the fragment would render nothing")

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
