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

CATEGORIES = (
    "architecture",
    "refactoring",
    "r-development",
    "ai-ml",
    "workflow",
    "communication",
    "personal",
)

# How a skill is surfaced. `auto` (default): model-triggered; its description
# participates in the auto-trigger budget. `command`: user-invoked only;
# install.sh routes it to each target's command/prompt directory instead of
# the skills directory, keeping it out of the auto-trigger metadata.
ACTIVATIONS = ("auto", "command")


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


# The manifest summary is the description's first sentence, capped here; a
# longer first sentence is truncated with an ellipsis and loses its trigger.
SUMMARY_LIMIT = 200


def first_sentence(text: str) -> str:
    """The description's leading sentence, whitespace-normalized (untruncated)."""
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"\.\s", text)
    return text[: m.end()].strip() if m else text


def truncate_summary(sentence: str, limit: int = SUMMARY_LIMIT) -> str:
    if len(sentence) > limit:
        return sentence[: limit - 1].rstrip() + "…"
    return sentence


def warn(message: str) -> None:
    sys.stderr.write(f"warning: {message}\n")


# Agent-skills spec limit; Claude.ai silently drops skills that exceed it.
MAX_DESCRIPTION_LENGTH = 1024


def check_strict_yaml(block: str, skill_md: Path) -> None:
    """Reject frontmatter our lenient parser accepts but strict YAML rejects.

    An unquoted scalar containing ': ' is a YAML mapping error, so consumers
    like Claude.ai fail to load the skill even though skills.json builds fine.
    """
    for line in block.splitlines():
        if line.startswith((" ", "\t")) or not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, rest = line.partition(":")
        value = rest.strip()
        if value and value[0] not in ("'", '"') and ": " in value:
            raise ValueError(
                f"{skill_md}: unquoted '{key.strip()}' value contains ': ' — invalid YAML;"
                " rephrase (e.g. use an em-dash) or quote the value"
            )


def build_entry(skill_md: Path) -> dict[str, object]:
    text = skill_md.read_text(encoding="utf-8")
    block = extract_frontmatter(text)
    check_strict_yaml(block, skill_md)
    fm = parse_frontmatter(block)
    name = fm.get("name")
    description = fm.get("description")
    category = fm.get("category")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{skill_md}: frontmatter missing 'name'")
    if not isinstance(description, str) or not description:
        raise ValueError(f"{skill_md}: frontmatter missing 'description'")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"{skill_md}: description is {len(description)} chars"
            f" (limit {MAX_DESCRIPTION_LENGTH}; longer skills are dropped by Claude.ai)"
        )
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError(
            f"{skill_md}: frontmatter 'category' must be one of {', '.join(CATEGORIES)}"
            f" (got {category!r})"
        )
    activation = fm.get("activation", "auto")
    if not isinstance(activation, str) or activation not in ACTIVATIONS:
        raise ValueError(
            f"{skill_md}: frontmatter 'activation' must be one of {', '.join(ACTIVATIONS)}"
            f" (got {activation!r})"
        )
    sentence = first_sentence(description)
    if len(sentence) > SUMMARY_LIMIT:
        warn(
            f"{skill_md}: description's first sentence is {len(sentence)} chars;"
            f" the skills.json summary is truncated at {SUMMARY_LIMIT}, losing its"
            f" what+when trigger. Rewrite the first sentence to stand alone under"
            f" {SUMMARY_LIMIT} chars."
        )
    entry: dict[str, object] = {
        "name": name,
        "summary": truncate_summary(sentence),
        "category": category,
        "path": str(skill_md.relative_to(REPO_ROOT)),
    }
    # Emit only the non-default activation, mirroring compatibility/version.
    if activation != "auto":
        entry["activation"] = activation
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
