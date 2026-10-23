"""Parse, validate and render this repository's instruction fragments.

The module API is shared by the installer, project mirror and fragment gate.
The command-line interface lets the Bash installer use the same format rules.

Exit codes: 0 success, 2 usage error, 3 invalid fragment or file error.
Examples:
  python3 scripts/instruction_fragments.py list --target claude --kind claude-rules
  python3 scripts/instruction_fragments.py block --target codex --python-pointer ~/.agents/instructions/30-python.md
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"
VALID_TARGETS = frozenset({"all", "claude", "codex", "opencode"})
TARGETS = VALID_TARGETS - {"all"}
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
    bad = [glob for glob in globs if '"' in glob or "\\" in glob]
    if bad:
        errors.append(f"'paths' glob(s) {', '.join(bad)} contain a quote or backslash")
    return errors


def fragment_matches_target(fragment: InstructionFragment, target: str) -> bool:
    _validate_target(target)
    errors = check_targets(fragment.fields["targets"]) if "targets" in fragment.fields else []
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
    return "all" in fragment.target_names or target in fragment.target_names


def is_claude_rule(fragment: InstructionFragment, target: str) -> bool:
    _validate_target(target)
    if target != "claude" or "paths" not in fragment.fields:
        return False
    errors = check_paths(fragment.fields["paths"])
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
    return True


def select_fragments(
    fragments: Iterable[InstructionFragment], target: str, kind: str
) -> list[InstructionFragment]:
    _validate_target(target)
    if kind not in {"block", "claude-rules"}:
        raise InstructionFragmentError("kind must be block or claude-rules")

    selected = []
    for fragment in fragments:
        errors = validate_fragment(fragment)
        if errors:
            raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
        if not fragment_matches_target(fragment, target):
            continue
        rule = is_claude_rule(fragment, target)
        if (kind == "claude-rules") == rule:
            selected.append(fragment)
    return selected


def render_instruction_block(
    fragments: Iterable[InstructionFragment],
    target: str,
    python_pointer: str | None = None,
) -> str:
    _validate_target(target)
    rendered = []
    for fragment in fragments:
        errors = validate_fragment(fragment)
        if errors:
            raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
        if not fragment_matches_target(fragment, target):
            raise InstructionFragmentError(f"{fragment.name}: does not match target {target}")
        if is_claude_rule(fragment, target):
            raise InstructionFragmentError(
                f"{fragment.name}: Claude path rules do not belong in the instruction block"
            )
        if target != "claude" and fragment.name == "30-python.md" and python_pointer:
            rendered.append(f"For Python work, read `{python_pointer}`.")
        else:
            rendered.append(fragment.body)
    return "\n\n".join(rendered)


def render_claude_rule(fragment: InstructionFragment, marker: str) -> str:
    errors = validate_fragment(fragment)
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")
    if not fragment_matches_target(fragment, "claude"):
        raise InstructionFragmentError(f"{fragment.name}: does not match target claude")
    if "\n" in marker or not marker.startswith("managed-by:"):
        raise InstructionFragmentError("marker must be a single managed-by line")

    lines = ["---"]
    if fragment.path_globs:
        lines.append("paths:")
        lines.extend(f'  - "{glob}"' for glob in fragment.path_globs)
    lines.extend((marker, "---", "", fragment.body))
    return "\n".join(lines) + "\n"


def _render_body_command(args: argparse.Namespace) -> None:
    fragment = load_fragment(args.fragment)
    _raise_if_invalid(fragment)
    sys.stdout.write(fragment.body)


def _render_block_command(args: argparse.Namespace) -> None:
    paths = [Path(path) for path in sys.stdin.read().splitlines() if path]
    fragments = [load_fragment(path) for path in paths]
    rendered = render_instruction_block(fragments, args.target, python_pointer=args.python_pointer)
    sys.stdout.write(rendered)


def _list_command(args: argparse.Namespace) -> None:
    fragments = select_fragments(load_fragments(), args.target, args.kind)
    for fragment in fragments:
        print(fragment.path)


def _render_claude_rule_command(args: argparse.Namespace) -> None:
    fragment = load_fragment(args.fragment)
    sys.stdout.write(render_claude_rule(fragment, args.marker))


def _raise_if_invalid(fragment: InstructionFragment) -> None:
    errors = validate_fragment(fragment)
    if errors:
        raise InstructionFragmentError(f"{fragment.name}: {errors[0]}")


def _validate_target(target: str) -> None:
    if target not in TARGETS:
        raise InstructionFragmentError(
            f"invalid target {target!r}; expected claude, codex or opencode"
        )


def _add_help_details(parser: argparse.ArgumentParser, examples: tuple[str, str]) -> None:
    parser.epilog = (
        "Exit codes: 0 success; 2 usage error; 3 invalid fragment or file error.\n"
        f"Examples:\n  {examples[0]}\n  {examples[1]}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse, validate and render instruction fragments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_help_details(
        parser,
        (
            "python3 scripts/instruction_fragments.py list --target claude --kind claude-rules",
            "python3 scripts/instruction_fragments.py block --target codex --python-pointer ~/.agents/instructions/30-python.md",
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser(
        "list",
        help="list fragments selected for a target",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_help_details(
        list_parser,
        (
            "python3 scripts/instruction_fragments.py list --target claude --kind block",
            "python3 scripts/instruction_fragments.py list --target claude --kind claude-rules",
        ),
    )
    list_parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    list_parser.add_argument("--kind", choices=("block", "claude-rules"), required=True)
    list_parser.set_defaults(run=_list_command)

    body_parser = commands.add_parser(
        "body",
        help="print a fragment's normalized body",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_help_details(
        body_parser,
        (
            "python3 scripts/instruction_fragments.py body --fragment instructions/30-python.md",
            "python3 scripts/instruction_fragments.py body --fragment instructions/40-r.md",
        ),
    )
    body_parser.add_argument("--fragment", type=Path, required=True)
    body_parser.set_defaults(run=_render_body_command)

    block_parser = commands.add_parser(
        "block",
        help="render selected fragment paths from stdin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_help_details(
        block_parser,
        (
            "python3 scripts/instruction_fragments.py block --target claude < /tmp/claude-fragments.txt",
            "python3 scripts/instruction_fragments.py block --target codex --python-pointer ~/.agents/instructions/30-python.md < /tmp/codex-fragments.txt",
        ),
    )
    block_parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    block_parser.add_argument("--python-pointer")
    block_parser.set_defaults(run=_render_block_command)

    rule_parser = commands.add_parser(
        "claude-rule",
        help="render one Claude rule",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_help_details(
        rule_parser,
        (
            "python3 scripts/instruction_fragments.py claude-rule --fragment instructions/40-r.md --marker 'managed-by: install'",
            "python3 scripts/instruction_fragments.py claude-rule --fragment instructions/40-r.md --marker 'managed-by: project-mirror'",
        ),
    )
    rule_parser.add_argument("--fragment", type=Path, required=True)
    rule_parser.add_argument("--marker", required=True)
    rule_parser.set_defaults(run=_render_claude_rule_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except (InstructionFragmentError, OSError) as error:
        sys.stderr.write(f"{error}\n")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
