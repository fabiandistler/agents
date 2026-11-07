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
sole caller of the SKILL.md frontmatter parser in `skill_frontmatter.py` and
owns the selection rules (routed
members, top-level entries, per-target and per-environment subsets), while
callers decide where selected entries are placed. Stdlib-only.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from skill_frontmatter import parse_skill_frontmatter

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
# each runtime keeps it out of automatic selection through its own switch
# (Claude `disable-model-invocation`, Codex `agents/openai.yaml`, opencode
# `opencode/autoinvoke` metadata). `router`:
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

    @property
    def is_command(self) -> bool:
        """Whether this skill is user-invoked rather than model-triggered."""
        return self.activation == "command"

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
    _validate_router_identity(name, category, activation, skill_md)

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
    """Load validated entries in manifest order; missing or malformed input fails."""
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{manifest_path}: skill manifest not found. Run: python3 scripts/build_manifest.py"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{manifest_path}: invalid skills.json: {error.msg}") from error
    if not isinstance(manifest, dict):
        raise TypeError(f"{manifest_path}: skills.json must be an object")
    if "skills" not in manifest:
        raise ValueError(f"{manifest_path}: skills.json must contain a 'skills' array")
    if not isinstance(manifest["skills"], list):
        raise TypeError(f"{manifest_path}: skills.json 'skills' field must be an array")

    entries: list[SkillEntry] = []
    names: set[str] = set()
    for index, raw_entry in enumerate(manifest["skills"]):
        location = f"{manifest_path}: skills[{index}]"
        if not isinstance(raw_entry, dict):
            raise TypeError(f"{location} must be an object")
        name = _required_string(raw_entry, "name", location)
        summary = _required_string(raw_entry, "summary", location)
        category = _validated_category(_required_string(raw_entry, "category", location), location)
        path = _required_string(raw_entry, "path", location)
        activation_value = _validated_activation(raw_entry.get("activation", "auto"), location)
        _validate_manifest_path(path, name, location)
        _validate_router_identity(name, category, activation_value, location)
        if name in names:
            raise ValueError(f"{location}: duplicate skill name {name!r}")
        names.add(name)

        entries.append(
            SkillEntry(
                name=name,
                summary=summary,
                category=category,
                path=path,
                activation=activation_value,
                compatibility=_manifest_optional_string(raw_entry, "compatibility", location),
                environments=_manifest_list(raw_entry, "environments", ENVIRONMENTS, location),
                targets=_manifest_list(raw_entry, "targets", TARGETS, location),
                version=_manifest_optional_string(raw_entry, "version", location),
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


def router_members(catalogue: Iterable[SkillEntry], category: str) -> list[SkillEntry]:
    """Auto skills nested under the router for `category`, in manifest order."""
    entries = tuple(catalogue)
    if category not in routed_categories(entries):
        raise ValueError(f"category {category!r} has no router in the skill catalogue")
    return [entry for entry in entries if entry.category == category and entry.activation == "auto"]


def top_level_entries(catalogue: Iterable[SkillEntry]) -> list[SkillEntry]:
    """Entries registered flat; auto skills in routed categories stay nested."""
    entries = tuple(catalogue)
    routed = routed_categories(entries)
    return [
        entry for entry in entries if not (entry.category in routed and entry.activation == "auto")
    ]


def entries_for_target(catalogue: Iterable[SkillEntry], target: str) -> list[SkillEntry]:
    """Entries that ship for one named runtime target, preserving order."""
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {', '.join(TARGETS)}")
    return [entry for entry in catalogue if entry.in_target(target)]


def entries_for_environment(catalogue: Iterable[SkillEntry], environment: str) -> list[SkillEntry]:
    """Entries available in one named work environment, preserving order."""
    if environment not in ENVIRONMENTS:
        raise ValueError(
            f"unknown environment {environment!r}; expected one of {', '.join(ENVIRONMENTS)}"
        )
    return [entry for entry in catalogue if entry.in_environment(environment)]


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


def _validate_router_identity(
    name: str, category: str, activation: str, source: Path | str
) -> None:
    if activation == "router" and name != category:
        raise ValueError(
            f"{source}: a router's name ({name!r}) must equal its category ({category!r})"
        )


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


def _manifest_optional_string(entry: Mapping[str, object], key: str, location: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{location}: '{key}' must be a string")
    return value or None


def _manifest_list(
    entry: Mapping[str, object],
    key: str,
    allowed: tuple[str, ...],
    location: str,
) -> tuple[str, ...] | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"{location}: '{key}' must be an array of strings")
    if any(not isinstance(item, str) for item in value):
        raise TypeError(f"{location}: '{key}' must contain only strings")
    if any(not item for item in value):
        raise ValueError(f"{location}: '{key}' must not contain empty strings")
    unknown = [item for item in value if item not in allowed]
    if unknown:
        raise ValueError(
            f"{location}: '{key}' has unknown value(s) {', '.join(unknown)}"
            f" (allowed: {', '.join(allowed)})"
        )
    return tuple(value)


def _validate_manifest_path(path: str, name: str, location: str) -> None:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or parsed.parts != ("skills", name, "SKILL.md"):
        raise ValueError(
            f"{location}: 'path' must be the relative source path skills/{name}/SKILL.md"
        )


def _truncate_summary(sentence: str, limit: int = SUMMARY_LIMIT) -> str:
    if len(sentence) > limit:
        return sentence[: limit - 1].rstrip() + "…"
    return sentence


def _warn(message: str) -> None:
    sys.stderr.write(f"warning: {message}\n")
