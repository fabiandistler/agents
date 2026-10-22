"""Tests for the Conventional Commits commit-msg hook."""

import check_commit_msg

PASSING_SUBJECTS = [
    "feat(install): add --merge-guard",
    "feat!: drop the opencode target",
    "fix(check-all)!: exit 4 on an old interpreter",
    "Merge pull request #577 from fabiandistlerkb/docs/readme",
    "Merge branch 'main' into feat/x",
    "fixup! feat: add hook",
    "squash! fix: guard",
    "amend! docs: reword",
]

FAILING_SUBJECTS = [
    "add a hook",
    "feature: add a hook",
    "Feat: add a hook",
    "feat:add a hook",
    "feat: ",
    "feat(): add a hook",
    "feat(two words): add a hook",
    "feat!(scope): add a hook",
    'Revert "feat: add a hook"',
    "WIP fixup! feat: add hook",
]


def run_hook(tmp_path, capsys, message: str):
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(message, encoding="utf-8")
    code = check_commit_msg.main([str(message_file)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_every_allowed_type_passes():
    rejected = [
        t for t in check_commit_msg.TYPES if not check_commit_msg.is_valid_subject(f"{t}: do it")
    ]

    assert rejected == []


def test_scope_breaking_marker_and_git_generated_subjects_pass():
    rejected = [s for s in PASSING_SUBJECTS if not check_commit_msg.is_valid_subject(s)]

    assert rejected == []


def test_non_conventional_subjects_fail():
    accepted = [s for s in FAILING_SUBJECTS if check_commit_msg.is_valid_subject(s)]

    assert accepted == []


def test_hook_passes_a_conventional_message_silently(tmp_path, capsys):
    code, out, err = run_hook(tmp_path, capsys, "feat(hooks): add commit-msg\n\nBody text.\n")

    assert (code, out, err) == (0, "", "")


def test_hook_rejects_a_bad_subject_naming_the_expected_form(tmp_path, capsys):
    code, _, err = run_hook(tmp_path, capsys, "add a hook\n")

    assert code == 1
    assert "<type>[(scope)][!]: <description>" in err
    assert "revert" in err


def test_subject_skips_leading_blank_and_comment_lines(tmp_path, capsys):
    message = "\n# Please enter the commit message\n\ndocs: explain the hook\n# trailing\n"

    code, _, _ = run_hook(tmp_path, capsys, message)

    assert code == 0


def test_body_line_cannot_rescue_a_bad_subject(tmp_path, capsys):
    code, _, _ = run_hook(tmp_path, capsys, "update things\n\nfeat: real change\n")

    assert code == 1


def test_empty_message_fails(tmp_path, capsys):
    code, _, _ = run_hook(tmp_path, capsys, "# only comments\n\n")

    assert code == 1


def test_missing_argument_is_a_usage_error(capsys):
    code = check_commit_msg.main([])

    assert code == 2
    assert "usage: check_commit_msg.py MESSAGE_FILE" in capsys.readouterr().err


def test_unreadable_file_is_a_usage_error(tmp_path, capsys):
    code = check_commit_msg.main([str(tmp_path / "missing")])

    assert code == 2
    assert "cannot read MESSAGE_FILE" in capsys.readouterr().err


def test_help_prints_usage_and_exit_codes(capsys):
    code = check_commit_msg.main(["--help"])

    out = capsys.readouterr().out
    assert code == 0
    assert "exit: 0 subject ok | 1 subject not conventional | 2 usage error" in out
    assert len(out.splitlines()) < 25
