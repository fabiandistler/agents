"""Parse, validate and render this repository's instruction fragments.

`check_instructions.py` (the fragment gate) and `build_project_claude.py` (the
cloud-session mirror) read fragments through this module, so both apply the
same frontmatter and `paths:` rules. install.sh stays an independent reader in
bash. Stdlib-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"
VALID_TARGETS = frozenset({"all", "claude", "codex", "opencode"})
TARGETS = VALID_TARGETS - {"all"}
# install.sh reads frontmatter with `grep -m1 '^<field>:'`, so a field only
# counts when it starts its own line; mirror that here rather than parsing YAML.
FIELD = re.compile(r"^([a-z]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)


class InstructionFragmentError(ValueError):
    """An instruction fragment does not follow the supported format."""


@dataclass(frozen=True)
class InstructionFragment:
    path: Path
    fields: dict[str, str]
    body: str

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def target_names(self) -> tuple[str, ...]:
        if "targets" not in self.fields:
            return ("all",)
        return tuple(part.strip() for part in self.fields["targets"].split(",") if part.strip())

    @property
    def path_globs(self) -> tuple[str, ...]:
        if "paths" not in self.fields:
            return ()
        return tuple(part.strip() for part in self.fields["paths"].split(","))


def parse_fragment(text: str, path: Path | str) -> InstructionFragment:
    source = Path(path)
    if not text.startswith("---\n"):
        raise InstructionFragmentError(
            f"{source.name}: missing or unterminated '---' frontmatter block"
        )
    end = text.find("\n---\n", 3)
    if end == -1:
        raise InstructionFragmentError(
            f"{source.name}: missing or unterminated '---' frontmatter block"
        )

    frontmatter = text[4 : end + 1]
    fields = dict(FIELD.findall(frontmatter))
    body = normalize_body(text[end + 5 :])
    return InstructionFragment(source, fields, body)


def load_fragment(path: Path) -> InstructionFragment:
    return parse_fragment(path.read_text(encoding="utf-8"), path)


def load_fragments(directory: Path = INSTRUCTIONS_DIR) -> list[InstructionFragment]:
    return [load_fragment(path) for path in sorted(directory.glob("*.md"))]


def normalize_body(body: str) -> str:
    """Trim empty lines at the edges and preserve internal spacing."""
    lines = body.split("\n")
    start = 0
    end = len(lines)
    while start < end and lines[start] == "":
        start += 1
    while end > start and lines[end - 1] == "":
        end -= 1
    return "\n".join(lines[start:end])


def validate_fragment(fragment: InstructionFragment) -> list[str]:
    errors: list[str] = []
    if not fragment.fields.get("title"):
        errors.append("missing or empty 'title'")

    # `targets` is optional: install.sh and build_project_claude.py read an
    # absent field as every agent. A present but blank one is ambiguous.
    if "targets" in fragment.fields:
        errors.extend(check_targets(fragment.fields["targets"]))

    if "paths" in fragment.fields:
        errors.extend(check_paths(fragment.fields["paths"]))

    if not fragment.body.strip():
        errors.append("body is empty; the fragment would render nothing")
    return errors


def check_targets(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        return ["'targets' is empty (omit the field to mean every agent)"]

    errors = []
    unknown = [part for part in parts if part not in VALID_TARGETS]
    if unknown:
        errors.append(
            f"'targets' has unknown value(s) {', '.join(sorted(unknown))};"
            f" expected a comma-separated subset of {', '.join(sorted(VALID_TARGETS))}"
        )
    if "all" in parts and len(parts) > 1:
        errors.append("'targets: all' cannot be combined with named agents")
    return errors


def check_paths(value: str) -> list[str]:
    globs = [glob.strip() for glob in value.split(",")]
    if not any(globs):
        return ["'paths' is empty (omit the field to load the fragment always)"]

    errors = []
    if any(not glob for glob in globs):
        errors.append("'paths' has an empty entry (stray comma)")
    # install.sh writes each glob inside a double-quoted YAML string; a quote
    # or backslash would break that frontmatter, and Claude then loads the rule
    # unconditionally instead of failing.
    bad = [glob for glob in globs if '"' in glob or "\\" in glob]
    if bad:
        errors.append(f"'paths' glob(s) {', '.join(bad)} contain a quote or backslash")
    return errors


def fragment_matches_target(fragment: InstructionFragment, target: str) -> bool:
    if target not in TARGETS:
        raise InstructionFragmentError(
            f"invalid target {target!r}; expected claude, codex or opencode"
        )
    errors = check_targets(fragment.fields["targets"]) if "targets" in fragment.fields else []
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
    return "all" in fragment.target_names or target in fragment.target_names


def render_claude_rule(fragment: InstructionFragment, marker: str) -> str:
    errors = validate_fragment(fragment)
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
    if not fragment_matches_target(fragment, "claude"):
        raise InstructionFragmentError(f"{fragment.name}: does not match target claude")
    if "\n" in marker or not marker.startswith("managed-by:"):
        raise InstructionFragmentError("marker must be a single managed-by line")

    # Quoted YAML list: a bare `**/*.R` parses as a YAML alias, and Claude
    # loads a rule whose frontmatter does not parse unconditionally.
    lines = ["---"]
    if fragment.path_globs:
        lines.append("paths:")
        lines.extend(f'  - "{glob}"' for glob in fragment.path_globs)
    lines.extend((marker, "---", "", fragment.body))
    return "\n".join(lines) + "\n"
