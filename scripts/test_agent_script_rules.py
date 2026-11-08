"""The general agent-script rules live only in the on-demand 85 fragment (#710).

`AGENTS.md` keeps the repository-specific rules and points to the fragment by
its repository path, because a cloud session has no `~/.agents/` install.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAGMENT_PATH = "instructions/on-demand/85-agent-scripts.md"
FRAGMENT = (ROOT / FRAGMENT_PATH).read_text(encoding="utf-8")
POINTER = (ROOT / "instructions/85-agent-scripts.md").read_text(encoding="utf-8")
CLAUDE_RULE = (ROOT / ".claude/rules/agents-85-agent-scripts.md").read_text(encoding="utf-8")


def agents_section() -> str:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    start = text.index("## Scripts an agent runs\n")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def flatten(markdown: str) -> str:
    return re.sub(r"\s+", " ", markdown)


def fragment_rule_openings() -> list[str]:
    """First sentence of each general rule bullet in the fragment."""
    bullets = [line[2:] for line in FRAGMENT.splitlines() if line.startswith("- ")]
    return [re.split(r"(?<=[.;:])\s", bullet, maxsplit=1)[0] for bullet in bullets]


def test_no_general_rule_is_repeated_in_agents_md():
    section = flatten(agents_section())
    openings = fragment_rule_openings()

    assert len(openings) >= 9
    repeated = [opening for opening in openings if opening in section]
    assert repeated == []
    assert "edit both" not in section


def test_agents_md_points_to_the_fragment_and_keeps_repo_rules():
    section = flatten(agents_section())

    assert f"`{FRAGMENT_PATH}`" in section
    for repo_rule in (
        "scripts/check_secret_argv.py",
        "PEP 723 inline block",
        "is version-pinned",
        "relative to the skill directory",
        "skills/<name>/evals.json",
    ):
        assert repo_rule in section, repo_rule


def test_idempotency_and_json_tsv_live_in_the_fragment():
    assert "Idempotent by default" in FRAGMENT
    assert "Prefer JSON/TSV over whitespace-aligned columns" in FRAGMENT
    assert "Data to stdout, diagnostics to stderr" in FRAGMENT


def test_pointers_name_the_repository_path_not_agents_md():
    tier_paragraph = flatten((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert "85 is also repeated" not in tier_paragraph

    for pointer in (POINTER, CLAUDE_RULE):
        assert f"`{FRAGMENT_PATH}`" in pointer
        assert "load through `AGENTS.md`" not in pointer
