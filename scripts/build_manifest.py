#!/usr/bin/env python3
"""Generate skills.json from each skill's SKILL.md frontmatter.

Run from repo root:
    python3 scripts/build_manifest.py            # write skills.json
    python3 scripts/build_manifest.py --check    # exit 1 if drift

Stdlib-only. Parses a minimal subset of YAML frontmatter sufficient for
our SKILL.md files: top-level scalar keys (name, description,
compatibility) and a single nested `metadata.version` block.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills.json"
MANIFEST_VERSION = "1"


def find_skill_files() -> list[Path]:
    skills = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        if skill_md.is_file():
            skills.append(skill_md)
    return skills


def extract_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise ValueError("missing opening '---' frontmatter delimiter")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("missing closing '---' frontmatter delimiter")
    return text[4:end]


def parse_frontmatter(block: str) -> dict[str, object]:
    """Parse the limited YAML subset used by our SKILL.md files."""
    out: dict[str, object] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            value = rest.strip()
            if value == "":
                # Nested block (e.g. `metadata:`); collect indented children.
                nested: dict[str, str] = {}
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                    sub = lines[i].strip()
                    if sub and ":" in sub:
                        k, _, v = sub.partition(":")
                        nested[k.strip()] = _strip_quotes_and_continuation(v.strip(), lines, i)
                    i += 1
                out[key] = nested
                continue
            # Multi-line folded value? Our skills sometimes wrap descriptions.
            value, consumed = _maybe_join_continuation(value, lines, i)
            out[key] = _strip_quotes(value)
            i += 1 + consumed
            continue
        i += 1
    return out


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strip_quotes_and_continuation(value: str, lines: list[str], idx: int) -> str:
    return _strip_quotes(value)


def _maybe_join_continuation(value: str, lines: list[str], idx: int) -> tuple[str, int]:
    """If a quoted value spans multiple lines (single quote opened, not closed),
    keep joining lines until the quote closes. Returns (joined, extra_lines)."""
    if not value or value[0] not in ("'", '"'):
        return value, 0
    quote = value[0]
    if value.endswith(quote) and len(value) > 1:
        return value, 0
    consumed = 0
    parts = [value]
    j = idx + 1
    while j < len(lines):
        parts.append(lines[j])
        consumed += 1
        if lines[j].rstrip().endswith(quote):
            break
        j += 1
    return " ".join(p.strip() for p in parts), consumed


def first_sentence(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"\.\s", text)
    sentence = text[: m.end()].strip() if m else text
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rstrip() + "…"
    return sentence


def build_entry(skill_md: Path) -> dict[str, object]:
    text = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(extract_frontmatter(text))
    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{skill_md}: frontmatter missing 'name'")
    if not isinstance(description, str) or not description:
        raise ValueError(f"{skill_md}: frontmatter missing 'description'")
    entry: dict[str, object] = {
        "name": name,
        "summary": first_sentence(description),
        "path": str(skill_md.relative_to(REPO_ROOT)),
    }
    compat = fm.get("compatibility")
    if isinstance(compat, str) and compat:
        entry["compatibility"] = compat
    environments = fm.get("environments")
    if isinstance(environments, str) and environments.strip():
        entry["environments"] = [e.strip() for e in environments.split(",") if e.strip()]
    metadata = fm.get("metadata")
    if isinstance(metadata, dict) and metadata.get("version"):
        entry["version"] = str(metadata["version"])
    return entry


def build_manifest() -> dict[str, object]:
    skills = [build_entry(p) for p in find_skill_files()]
    return {"version": MANIFEST_VERSION, "skills": skills}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if skills.json is out of date")
    args = parser.parse_args()

    manifest = build_manifest()
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        existing = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else ""
        if existing != rendered:
            sys.stderr.write("skills.json is out of date. Run: python3 scripts/build_manifest.py\n")
            return 1
        return 0

    MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(manifest['skills'])} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
