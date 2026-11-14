"""Tests for the factory side of the setup wizard (scripts/factory_repo_setup.py).

The wizard's dialogue and gh calls are covered by test/factory_repo_setup.bats.
"""

import io
import json

import factory_repo_setup
from issue_triage_policy import CATEGORIES, STATE_LABELS


def run(capsys, *argv: str, stdin: str = ""):
    code = factory_repo_setup.main(list(argv), io.StringIO(stdin))
    return code, capsys.readouterr()


def test_labels_are_the_state_labels_then_the_categories(capsys):
    code, captured = run(capsys, "labels")
    assert code == 0
    assert captured.out.splitlines() == [*STATE_LABELS, *CATEGORIES]


def test_missing_patterns_lists_only_what_the_list_lacks(capsys):
    selected = {"patterns_allowed": ["actions/checkout@*", "acme/tool@v1"]}
    code, captured = run(capsys, "missing-patterns", stdin=json.dumps(selected))
    assert code == 0
    assert captured.out.splitlines() == [
        p for p in factory_repo_setup.FACTORY_PATTERNS if p != "actions/checkout@*"
    ]


def test_a_complete_list_has_nothing_missing():
    selected = {"patterns_allowed": list(factory_repo_setup.FACTORY_PATTERNS)}
    assert factory_repo_setup.missing_patterns(selected) == []


def test_allowlist_body_keeps_current_patterns_and_flags(capsys):
    selected = {
        "github_owned_allowed": True,
        "verified_allowed": False,
        "patterns_allowed": ["acme/tool@v1"],
    }
    code, captured = run(capsys, "allowlist-body", stdin=json.dumps(selected))
    assert code == 0
    assert json.loads(captured.out) == {
        "github_owned_allowed": True,
        "verified_allowed": False,
        "patterns_allowed": ["acme/tool@v1", *factory_repo_setup.FACTORY_PATTERNS],
    }


def test_a_response_without_patterns_gets_all_of_them():
    body = factory_repo_setup.allowlist_body({})
    assert body["patterns_allowed"] == list(factory_repo_setup.FACTORY_PATTERNS)
    assert body["github_owned_allowed"] is False


def test_unknown_command_is_a_usage_error(capsys):
    code, captured = run(capsys, "bogus")
    assert code == 2
    assert captured.err.startswith("usage:")
