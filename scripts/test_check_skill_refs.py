"""End-to-end tests for the cross-skill reference gate (#466).

Each test builds a fixture repo with a small skills.json, runs the gate's entry
point against it with --root, and asserts on the exit code and reported lines.
"""

import json
from pathlib import Path

import check_skill_refs

CATALOGUE = [
    {"name": "architecture", "category": "architecture", "activation": "router"},
    {"name": "ddd", "category": "architecture"},
    {"name": "c4-modeling", "category": "architecture"},
    {"name": "docs", "category": "communication"},
    {"name": "tldr", "category": "communication", "activation": "command"},
]


def make_repo(root: Path) -> Path:
    entries = [{"summary": "x.", "path": f"skills/{e['name']}/SKILL.md", **e} for e in CATALOGUE]
    (root / "skills.json").write_text(json.dumps({"version": 1, "skills": entries}))
    return root


def write(root: Path, rel: str, body: str, description: str = "Demo.") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: x\ndescription: {description}\n---\n\n{body}\n")


def run_gate(root: Path, capsys):
    code = check_skill_refs.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_member_named_as_skill_fails_with_router_form_hint(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/docs/SKILL.md", "For diagrams use the `c4-modeling` skill.")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/docs/SKILL.md:6: c4-modeling:" in err
    assert "`members/c4-modeling/SKILL.md`, read via the `architecture` router" in err


def test_router_form_introduces_member_for_rest_of_file(tmp_path, capsys):
    make_repo(tmp_path)
    write(
        tmp_path,
        "skills/docs/references/page.md",
        "Read `members/c4-modeling/SKILL.md`, via the `architecture` router.\n\n"
        "Later, c4-modeling draws the views.",
    )

    code, out, err = run_gate(tmp_path, capsys)

    assert code == 0, err
    assert "skill refs ok" in out


def test_member_path_without_router_name_does_not_introduce(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/docs/SKILL.md", "Read `members/c4-modeling/SKILL.md`.\n\nUse ddd here.")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "ddd:" in err
    assert "c4-modeling:" not in err


def test_router_and_self_and_frontmatter_and_lookalikes_pass(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/architecture/SKILL.md", "- Domain boundaries -> `ddd`")
    write(tmp_path, "skills/ddd/SKILL.md", "The `ddd` skill. See <https://ddd-crew.github.io/>.")
    write(tmp_path, "skills/docs/SKILL.md", "The ddd-crew canvas and DDD in general.")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 0, err


def test_command_skill_needs_run_hint(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/docs/SKILL.md", "Compress it with `tldr`.")
    write(tmp_path, "skills/ddd/SKILL.md", "Suggest the user run `tldr`.")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/docs/SKILL.md:6: tldr: command skill" in err
    assert "skills/ddd/SKILL.md" not in err


def test_unknown_skill_fails_unless_external(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/docs/SKILL.md", "Use the `adr-workflow` skill.")
    write(
        tmp_path,
        "skills/ddd/SKILL.md",
        "Adapted from Someone's `pr` skill.\n\n"
        "See the `prek-hooks` skill in the [plugin](https://example.com).",
    )

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/docs/SKILL.md:6: adr-workflow: no such skill" in err
    assert "skills/ddd" not in err


def test_vendored_skill_names_count_as_known(tmp_path, capsys):
    make_repo(tmp_path)
    lock = tmp_path / ".claude/vendor/mattpocock-skills/lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({"skills": ["tdd"]}))
    write(tmp_path, "skills/docs/SKILL.md", "Use the `tdd` skill if available.")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 0, err


def test_bad_paths_fail(tmp_path, capsys):
    make_repo(tmp_path)
    write(
        tmp_path,
        "skills/docs/SKILL.md",
        "Read `members/gone/SKILL.md` via `architecture`.\n\nSee [d](../ddd/SKILL.md).",
    )

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "members/gone/SKILL.md: no such router member" in err
    assert "../ddd/:" in err


def test_member_symlink_copies_count_once(tmp_path, capsys):
    make_repo(tmp_path)
    write(tmp_path, "skills/c4-modeling/SKILL.md", "Then use ddd.")
    members = tmp_path / "skills/architecture/members"
    members.mkdir(parents=True)
    (members / "c4-modeling").symlink_to("../../c4-modeling")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert err.count("ddd:") == 1


def test_missing_manifest_is_usage_error(tmp_path, capsys):
    code, _, err = run_gate(tmp_path, capsys)

    assert code == 2
    assert "skills.json" in err


def test_trigger_text_names_no_member_or_command(tmp_path, capsys):
    make_repo(tmp_path)
    write(
        tmp_path, "skills/docs/SKILL.md", "Body.", description="Not for diagrams; use c4-modeling."
    )
    write(tmp_path, "skills/ddd/SKILL.md", "Body.", description="Compress with `tldr`.")
    write(
        tmp_path,
        "skills/architecture/SKILL.md",
        "Body.",
        description="Routes to ddd or c4-modeling.",
    )
    path = tmp_path / "skills/c4-modeling/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: c4-modeling\nwhen_to_use: >\n  draw it, then ddd\n---\n\nBody.\n")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/docs/SKILL.md:3: c4-modeling: router member named in trigger text" in err
    assert "skills/ddd/SKILL.md:3: tldr: command skill named in trigger text" in err
    assert "skills/c4-modeling/SKILL.md:4: ddd:" in err
    assert "skills/architecture" not in err
