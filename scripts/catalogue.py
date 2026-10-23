"""The skill catalogue: SKILL.md frontmatter in, one entry per skill out.

The catalogue lives in `skills.json`, which `scripts/build_manifest.py`
generates from each SKILL.md's frontmatter through `entry_from_skill_file`
here. A checker asks this module what skills exist and what the catalogue says
about them instead of crawling `skills/` with its own frontmatter regexes.

The manifest source is a parameter, defaulting to the repo-root `skills.json`,
so a checker can also be driven from a fixture catalogue. The manifest must be
current for the answers to mean anything — CI runs `build_manifest.py --check`
as its first gate for that reason — and a missing manifest raises rather than
reporting an empty catalogue.

`build_manifest.py` stays the sole writer of `skills.json`; this module is the
sole parser of SKILL.md frontmatter. Stdlib-only.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills.json"

CATEGORIES = (
    "architecture",
    "refactoring",
    "ai-ml",
    "workflow",
    "communication",
    "personal",
)

# How a skill is surfaced. `auto` (default): model-triggered; its description
# participates in the auto-trigger budget. `command`: user-invoked only;
# install.sh routes it to each target's command/prompt directory instead of
# the skills directory, keeping it out of the auto-trigger metadata. `router`:
# a per-category entry skill (named after its category) that is the only
# member of the category registered at top level; its `members/` subdir nests
# the category's auto skills, which load lazily when the router routes to them.
ACTIVATIONS = ("auto", "command", "router")
ENVIRONMENTS = ("coding", "chat")

# Which agents a skill is installed for. Absent (the default) means all of
# them; `targets: codex, opencode` keeps install.sh from linking the skill
# under claude — e.g. when the Claude runtime ships its own version.
TARGETS = ("claude", "codex", "opencode")

# The manifest summary is the description's first sentence, capped here; a
# longer first sentence is truncated with an ellipsis and loses its trigger.
SUMMARY_LIMIT = 200

# Agent-skills spec limit; Claude.ai silently drops skills that exceed it.
MAX_DESCRIPTION_LENGTH = 1024

# How Claude Code joins `when_to_use` onto the description in its skill listing.
# The combined length is budgeted in scripts/check_descriptions.py.
CLAUDE_WHEN_TO_USE_JOINER = " - "


@dataclass(frozen=True)
class SkillEntry:
    """One validated skill entry, including its relative source path.

    `environments` and `targets` are None when the skill declares none, which
    means every environment and every target — the manifest omits the key
    rather than spelling out the list.
    """

    name: str
    summary: str
    category: str
    path: str
    activation: str = "auto"
    compatibility: str | None = None
    environments: tuple[str, ...] | None = None
    targets: tuple[str, ...] | None = None
    version: str | None = None

    @property
    def is_router(self) -> bool:
        """Whether this skill routes to its category's nested members."""
        return self.activation == "router"

    def in_environment(self, environment: str) -> bool:
        """Whether the skill is available in `environment` (all if undeclared)."""
        return self.environments is None or environment in self.environments

    def in_target(self, target: str) -> bool:
        """Whether the skill ships for `target` (all if undeclared)."""
        return self.targets is None or target in self.targets

    def to_manifest(self) -> dict[str, object]:
        """Return the JSON entry, omitting fields whose defaults are implicit."""
        entry: dict[str, object] = {
            "name": self.name,
            "summary": self.summary,
            "category": self.category,
            "path": self.path,
        }
        if self.activation != "auto":
            entry["activation"] = self.activation
        if self.compatibility:
            entry["compatibility"] = self.compatibility
        if self.environments is not None:
            entry["environments"] = list(self.environments)
        if self.targets is not None:
            entry["targets"] = list(self.targets)
        if self.version:
            entry["version"] = self.version
        return entry


def find_skill_files(skills_dir: Path = SKILLS_DIR) -> list[Path]:
    """Return top-level skill files in stable name order."""
    skills: list[Path] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        if skill_md.is_file():
            skills.append(skill_md)
    return skills


def parse_skill_frontmatter(text: str, source: Path | str = "SKILL.md") -> dict[str, object]:
    """Parse the repository's limited SKILL.md frontmatter subset.

    The parser accepts the top-level scalar fields and nested
    `metadata.version` shape used by this catalogue. It rejects malformed
    delimiters, unclosed quoted values, and plain scalars that strict YAML
    consumers would interpret as mappings.
    """
    block = _extract_frontmatter(text, source)
    _check_strict_yaml(block, source)
    return _parse_frontmatter(block, source)


def entry_from_skill_file(skill_md: Path, repo_root: Path = REPO_ROOT) -> SkillEntry:
    """Read, validate, and summarize one skill's source frontmatter."""
    fields = parse_skill_frontmatter(skill_md.read_text(encoding="utf-8"), skill_md)
    name = _required_string(fields, "name", skill_md)
    description = _required_string(fields, "description", skill_md)
    category = _validated_category(_required_string(fields, "category", skill_md), skill_md)
    if name != skill_md.parent.name:
        raise ValueError(
            f"{skill_md}: frontmatter 'name' ({name!r}) must match the skill directory"
        )
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"{skill_md}: description is {len(description)} chars"
            f" (limit {MAX_DESCRIPTION_LENGTH}; longer skills are dropped by Claude.ai)"
        )

    activation = _validated_activation(fields.get("activation", "auto"), skill_md)

    when_to_use = fields.get("when_to_use")
    if isinstance(when_to_use, str) and when_to_use.strip() and activation != "router":
        # Only the router branch below folds the field into the summary, so on
        # any other activation it would vanish from skills.json while Claude
        # Code still appends it to the listing — the menu would then be scored
        # against text the client never renders. Fail instead of dropping it.
        raise ValueError(
            f"{skill_md}: 'when_to_use' is only consumed for 'activation: router'"
            f" skills (this one is {activation!r}); a non-router summary is a"
            " truncated first sentence and would silently drop the field"
        )

    sentence = first_sentence(description)
    if activation == "router":
        # A router's description is the whole trigger surface of its category;
        # the summary is what the menu A/B in eval-suite/recall
        # ([fabiandistler/eval-suite](https://github.com/fabiandistler/eval-suite))
        # shows, so it carries all of it, untruncated, rather than a first
        # sentence. When the router also declares `when_to_use`, that is
        # appended the way Claude Code appends it to the listing (" - "), so the
        # menu shows the model exactly the text the client would. Codex ignores
        # the field, so this only ever adds what one of the two clients displays.
        summary = re.sub(r"\s+", " ", description).strip()
        if isinstance(when_to_use, str) and when_to_use.strip():
            summary += CLAUDE_WHEN_TO_USE_JOINER + re.sub(r"\s+", " ", when_to_use).strip()
    else:
        summary = _truncate_summary(sentence)
    if activation != "router" and len(sentence) > SUMMARY_LIMIT:
        _warn(
            f"{skill_md}: description's first sentence is {len(sentence)} chars;"
            f" the skills.json summary is truncated at {SUMMARY_LIMIT}, losing its"
            " what+when trigger. Rewrite the first sentence to stand alone under"
            f" {SUMMARY_LIMIT} chars."
        )

    return SkillEntry(
        name=name,
        summary=summary,
        category=category,
        path=skill_md.relative_to(repo_root).as_posix(),
        activation=activation,
        compatibility=_optional_string(fields, "compatibility", skill_md),
        environments=_source_list(fields, "environments", ENVIRONMENTS, skill_md),
        targets=_source_list(fields, "targets", TARGETS, skill_md),
        version=_metadata_version(fields, skill_md),
    )


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
        targets = entry.get("targets")
        entries.append(
            SkillEntry(
                name=entry["name"],
                summary=entry["summary"],
                category=entry["category"],
                path=entry["path"],
                activation=entry.get("activation", "auto"),
                compatibility=entry.get("compatibility"),
                environments=tuple(environments) if environments is not None else None,
                targets=tuple(targets) if targets is not None else None,
                version=entry.get("version"),
            )
        )
    return entries


def routed_categories(catalogue: Iterable[SkillEntry]) -> set[str]:
    """Categories reached through a router rather than skill by skill.

    A category is routed when it ships a skill with `activation: router` (named
    after the category). Its auto skills are nested under the router's
    `members/` dir rather than registered at top level, so only the router
    itself — plus any user-invoked command skills — is installed flat.
    `build_routers.py --check` validates the nested `members/` symlinks.
    """
    return {entry.category for entry in catalogue if entry.is_router}


def first_sentence(text: str) -> str:
    """Return the leading sentence with whitespace normalized."""
    text = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"\.\s", text)
    return text[: match.end()].strip() if match else text


def unique_real_files(paths: Iterable[Path]) -> list[Path]:
    """The existing files among `paths`, resolved and each listed once.

    A router's `members/<name>` is a symlink to the top-level skill directory,
    so the same SKILL.md or reference file is reachable under two paths. A
    checker that walks both reports it once, under its real path, in the order
    first seen. Paths that are not files are skipped.
    """
    seen: set[Path] = set()
    files: list[Path] = []
    for path in paths:
        if not path.is_file():
            continue
        real = path.resolve()
        if real in seen:
            continue
        seen.add(real)
        files.append(real)
    return files


def _extract_frontmatter(text: str, source: Path | str) -> str:
    if not text.startswith("---\n"):
        raise ValueError(f"{source}: missing opening '---' frontmatter delimiter")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError(f"{source}: missing closing '---' frontmatter delimiter")
    return text[4:end]


def _parse_frontmatter(block: str, source: Path | str) -> dict[str, object]:
    fields: dict[str, object] = {}
    lines = block.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            value = rest.strip()
            if value == "":
                # Nested block (e.g. `metadata:`); collect indented children.
                nested: dict[str, str] = {}
                index += 1
                while index < len(lines) and lines[index].startswith((" ", "\t")):
                    sub = lines[index].strip()
                    if sub and ":" in sub:
                        nested_key, _, nested_value = sub.partition(":")
                        # Nested values are short scalars (metadata.version), so
                        # unlike top-level ones they never span lines.
                        nested[nested_key.strip()] = _strip_quotes(nested_value.strip())
                    index += 1
                fields[key] = nested
                continue
            # Multi-line folded value? Our skills sometimes wrap descriptions.
            value, consumed = _maybe_join_continuation(value, lines, index, source)
            fields[key] = _strip_quotes(value)
            index += 1 + consumed
            continue
        index += 1
    return fields


def _maybe_join_continuation(
    value: str, lines: list[str], index: int, source: Path | str
) -> tuple[str, int]:
    if not value or value[0] not in ("'", '"'):
        return value, 0
    quote = value[0]
    if value.endswith(quote) and len(value) > 1:
        return value, 0
    consumed = 0
    parts = [value]
    cursor = index + 1
    while cursor < len(lines):
        parts.append(lines[cursor])
        consumed += 1
        if lines[cursor].rstrip().endswith(quote):
            return " ".join(part.strip() for part in parts), consumed
        cursor += 1
    raise ValueError(f"{source}: unterminated quoted frontmatter value")


def _check_strict_yaml(block: str, source: Path | str) -> None:
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
                f"{source}: unquoted '{key.strip()}' value contains ': ' — invalid YAML;"
                " rephrase (e.g. use an em-dash) or quote the value"
            )


def _validated_category(value: str, source: Path | str) -> str:
    if value not in CATEGORIES:
        raise ValueError(
            f"{source}: 'category' must be one of {', '.join(CATEGORIES)} (got {value!r})"
        )
    return value


def _validated_activation(value: object, source: Path | str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{source}: 'activation' must be a string")
    if value not in ACTIVATIONS:
        raise ValueError(
            f"{source}: 'activation' must be one of {', '.join(ACTIVATIONS)} (got {value!r})"
        )
    return value


def _required_string(fields: Mapping[str, object], key: str, source: Path | str) -> str:
    if key not in fields:
        raise ValueError(f"{source}: missing '{key}'")
    value = fields[key]
    if not isinstance(value, str):
        raise TypeError(f"{source}: '{key}' must be a string")
    if not value:
        raise ValueError(f"{source}: '{key}' must be non-empty")
    return value


def _optional_string(fields: Mapping[str, object], key: str, source: Path | str) -> str | None:
    value = fields.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{source}: '{key}' must be a string")
    return value or None


def _source_list(
    fields: Mapping[str, object],
    key: str,
    allowed: tuple[str, ...],
    source: Path | str,
) -> tuple[str, ...] | None:
    value = fields.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{source}: '{key}' must be a comma-separated string")
    values = tuple(part.strip() for part in value.split(",") if part.strip())
    if not values:
        raise ValueError(f"{source}: '{key}' is present but empty")
    unknown = [part for part in values if part not in allowed]
    if unknown:
        raise ValueError(
            f"{source}: '{key}' has unknown value(s) {', '.join(unknown)}"
            f" (allowed: {', '.join(allowed)})"
        )
    return values


def _metadata_version(fields: Mapping[str, object], source: Path | str) -> str | None:
    metadata = fields.get("metadata")
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise TypeError(f"{source}: 'metadata' must be a mapping")
    version = metadata.get("version")
    if version is None or version == "":
        return None
    if not isinstance(version, str):
        raise TypeError(f"{source}: 'metadata.version' must be a string")
    return version


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _truncate_summary(sentence: str, limit: int = SUMMARY_LIMIT) -> str:
    if len(sentence) > limit:
        return sentence[: limit - 1].rstrip() + "…"
    return sentence


def _warn(message: str) -> None:
    sys.stderr.write(f"warning: {message}\n")
