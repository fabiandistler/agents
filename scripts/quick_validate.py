#!/usr/bin/env python3
"""Validate a skill's SKILL.md frontmatter and script path convention.

Run from repo root:
    python3 scripts/quick_validate.py skills/<name>/    # exit 1 if invalid

Checks the Agent Skills format plus this repo's catalogue fields. CI runs it
over every skill; it also works standalone on a skill directory outside this
repo.
"""

import re
import sys
from pathlib import Path

import yaml

# Frontmatter keys accepted in a SKILL.md: the Agent Skills format, the
# client-specific fields Claude Code honors, and the repo-specific catalogue
# fields consumed by build_manifest.py, install.sh and check_plugins.py.
#
# These vocabularies mirror CATEGORIES / ACTIVATIONS / TARGETS in
# scripts/build_manifest.py. They are restated rather than imported so this
# validator keeps working on skills outside this repo, where that tooling is
# not on the path. When the manifest builder gains a category, activation or
# target, update it here too.
ALLOWED_PROPERTIES = {
    # Agent Skills format
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
    # Client-specific (Claude Code); ignored by other agents
    "argument-hint",
    "disable-model-invocation",
    "when_to_use",
    # Repo-specific catalogue fields
    "category",
    "activation",
    "environments",
    "targets",
}

CATEGORIES = {
    "architecture",
    "refactoring",
    "ai-ml",
    "workflow",
    "communication",
    "personal",
}
ACTIVATIONS = {"auto", "command", "router"}
TARGETS = {"claude", "codex", "opencode"}
ENVIRONMENTS = {"coding", "chat"}

REPO_ROOT_SCRIPT_PATH = re.compile(
    r"(?<![\w./~])(?:skills/[a-z0-9-]+/scripts/|members/[a-z0-9-]+/scripts/)"
)


def find_repo_root_script_paths(skill_path):
    base = Path(skill_path)
    targets = []
    skill_md = base / "SKILL.md"
    if skill_md.is_file():
        targets.append(skill_md)
    references = base / "references"
    if references.is_dir():
        targets.extend(sorted(references.glob("*.md")))
    hits = []
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        label = "SKILL.md" if path.parent == base else f"references/{path.name}"
        for match in REPO_ROOT_SCRIPT_PATH.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{label}:{line}: {match.group(0).strip()}")
    return hits


def find_command_skill_gap(skill_path, frontmatter):
    """Return why a command skill could still be auto-triggered, or None.

    'activation: command' is a catalogue field no runtime reads. Claude honors
    'disable-model-invocation: true'; OpenCode honors its slash/autoinvoke
    metadata; Codex honors the committed agents/openai.yaml sidecar, which
    install.sh links but never generates.
    """
    if frontmatter.get("disable-model-invocation") is not True:
        return (
            "'activation: command' requires 'disable-model-invocation: true' "
            "in the frontmatter (keeps Claude from auto-triggering it)"
        )
    metadata = frontmatter.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("opencode/slash") != "true"
        or metadata.get("opencode/autoinvoke") != "false"
    ):
        return (
            "'activation: command' requires metadata 'opencode/slash: \"true\"' and "
            "'opencode/autoinvoke: \"false\"' (registers an explicit OpenCode slash command)"
        )
    sidecar = Path(skill_path) / "agents" / "openai.yaml"
    if not sidecar.is_file():
        return (
            "'activation: command' requires agents/openai.yaml with "
            "'policy.allow_implicit_invocation: false' (keeps Codex from auto-triggering it)"
        )
    try:
        config = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return f"Invalid YAML in agents/openai.yaml: {e}"
    policy = config.get("policy") if isinstance(config, dict) else None
    if not isinstance(policy, dict) or policy.get("allow_implicit_invocation") is not False:
        return "agents/openai.yaml must set 'policy.allow_implicit_invocation: false'"
    return None


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check enumerated values of the repo-specific fields, when present.
    for field, allowed in (("category", CATEGORIES), ("activation", ACTIVATIONS)):
        value = frontmatter.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or value not in allowed:
            return False, (f"'{field}' must be one of {', '.join(sorted(allowed))} (got {value!r})")

    for field, allowed in (("environments", ENVIRONMENTS), ("targets", TARGETS)):
        value = frontmatter.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            return False, f"'{field}' must be a comma-separated string, got {type(value).__name__}"
        items = [v.strip() for v in value.split(",") if v.strip()]
        if not items:
            return False, f"'{field}' is present but empty"
        unknown = [v for v in items if v not in allowed]
        if unknown:
            return False, (
                f"'{field}' has unknown value(s) {', '.join(unknown)} "
                f"(allowed: {', '.join(sorted(allowed))})"
            )

    # Check required fields
    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        # Check naming convention (kebab-case: lowercase with hyphens)
        if not re.match(r"^[a-z0-9-]+$", name):
            return (
                False,
                f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)",
            )
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return (
                False,
                f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
            )
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."
        # The Agent Skills format requires the name to match the parent
        # directory; install.sh links by directory, the manifest keys by name.
        dir_name = skill_path.absolute().name
        if name != dir_name:
            return False, f"Name '{name}' must match the skill directory '{dir_name}'"

    # Extract and validate description
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        # Descriptions are interpolated into the agent's system prompt, often
        # inside XML-ish scaffolding, so a '<' can open a tag that was never
        # meant to exist. A bare '>' cannot, and reads naturally as an arrow or
        # a hierarchy separator ("Principle > System > Workflow"), so it stays
        # allowed — banning it only forces trigger text to be mangled.
        if "<" in description:
            return False, "Description cannot contain '<' (it can open a tag in the system prompt)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return (
                False,
                f"Description is too long ({len(description)} characters). Maximum is 1024 characters.",
            )
        # This repo's tighter per-skill budgets (default, allowlist, router)
        # live only in scripts/check_descriptions.py, the CI gate for them.

    # Claude Code appends 'when_to_use' to the description in the skill listing,
    # so it reaches the system prompt the same way and carries the same '<'
    # hazard. Other agents ignore the key; its budget is check_descriptions.py's.
    when_to_use = frontmatter.get("when_to_use")
    if when_to_use is not None:
        if not isinstance(when_to_use, str):
            return False, f"when_to_use must be a string, got {type(when_to_use).__name__}"
        if not when_to_use.strip():
            return False, "'when_to_use' is present but empty"
        if "<" in when_to_use:
            return False, "when_to_use cannot contain '<' (it can open a tag in the system prompt)"

    # Validate compatibility field if present (optional)
    compatibility = frontmatter.get("compatibility", "")
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"Compatibility must be a string, got {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return (
                False,
                f"Compatibility is too long ({len(compatibility)} characters). Maximum is 500 characters.",
            )

    if frontmatter.get("activation") == "command":
        problem = find_command_skill_gap(skill_path, frontmatter)
        if problem:
            return False, problem

    hits = find_repo_root_script_paths(skill_path)
    if hits:
        detail = "; ".join(hits)
        return False, (
            f"Repo-root skill script path ({detail}): reference bundled scripts "
            "relative to the skill directory (scripts/...) and pass the target "
            "repo as an argument"
        )

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
