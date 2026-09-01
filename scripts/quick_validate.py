#!/usr/bin/env python3
"""Validate a skill's SKILL.md frontmatter.

Run from repo root:
    python3 scripts/quick_validate.py skills/<name>/    # exit 1 if invalid

Checks the Agent Skills format plus this repo's catalogue fields. CI runs it
over every skill; it also works standalone on a skill directory outside this
repo.
"""

import sys
import re
import yaml
from pathlib import Path

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
            return False, (
                f"'{field}' must be one of {', '.join(sorted(allowed))} (got {value!r})"
            )

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
        # This repo budgets descriptions far tighter than the spec (≤250 chars,
        # ≤400 for the allowlist in scripts/check_descriptions.py). Warn rather
        # than fail here — CI's check_descriptions.py is the hard gate — so the
        # validator stays usable for skills outside this repo.
        if len(description) > 250:
            print(
                f"WARNING: description is {len(description)} chars; this repo's budget is "
                "≤250 (≤400 for the high-traffic allowlist). Move trigger lists into a "
                "'## When to use' body section."
            )

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

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
