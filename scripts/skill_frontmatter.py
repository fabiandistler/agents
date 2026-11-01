"""Parse the limited YAML subset that SKILL.md frontmatter uses.

`parse_skill_frontmatter` turns the block between the `---` delimiters into a
dict of top-level scalars plus nested mappings such as `metadata.version`. It
knows the syntax only: which fields exist, which values are valid, and what an
entry looks like are `catalogue.py`'s business, and `catalogue.py` is the one
caller that turns these fields into catalogue entries. Stdlib-only.
"""

from __future__ import annotations

from pathlib import Path


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


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value
