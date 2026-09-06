#!/usr/bin/env python3
"""The skill catalogue, as the consistency checks read it.

The catalogue lives in `skills.json`, which `scripts/build_manifest.py`
generates from each SKILL.md's frontmatter. This module hands out one entry per
skill, so a checker asks it what skills exist and what the catalogue says about
them instead of crawling `skills/` with its own frontmatter regexes.

The manifest source is a parameter, defaulting to the repo-root `skills.json`,
so a checker can also be driven from a fixture catalogue. The manifest must be
current for the answers to mean anything — CI runs `build_manifest.py --check`
as its first gate for that reason — and a missing manifest raises rather than
reporting an empty catalogue.

`build_manifest.py` stays the sole writer and the sole parser of SKILL.md; the
dependency runs one way only. Stdlib-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "skills.json"


@dataclass(frozen=True)
class SkillEntry:
    """One skill as the catalogue describes it.

    `environments` is None when the skill declares none, which means every
    environment — the manifest omits the key rather than spelling out the list.
    """

    name: str
    category: str
    activation: str
    environments: tuple[str, ...] | None

    @property
    def is_router(self) -> bool:
        """Whether the skill is its category's router rather than a capability."""
        return self.activation == "router"

    def in_environment(self, environment: str) -> bool:
        """Whether the skill is available in `environment` (all, if undeclared)."""
        return self.environments is None or environment in self.environments


def load_catalogue(manifest_path: Path = MANIFEST_PATH) -> list[SkillEntry]:
    """Every catalogued skill, in manifest order."""
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{manifest_path}: skill manifest not found. Run: python3 scripts/build_manifest.py"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = []
    for entry in manifest["skills"]:
        environments = entry.get("environments")
        entries.append(
            SkillEntry(
                name=entry["name"],
                category=entry["category"],
                activation=entry.get("activation", "auto"),
                environments=tuple(environments) if environments is not None else None,
            )
        )
    return entries
