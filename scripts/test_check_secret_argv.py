"""Tests for the credential-in-argv gate.

The detector tests feed single command lines to `rules_hit`; the end-to-end
tests build a fixture tree and run the entry point against it with --root.
"""

from pathlib import Path

import check_secret_argv

# Split so the gitleaks commit hook does not read the sample as a leaked login.
LITERAL_LOGIN = "admin:" + "hunter2"

POSITIVE = [
    ('curl -sS -u ":$AUTH_PAT" "$URL"', "user-flag"),
    ("curl --user me:$GITHUB_TOKEN https://api.example.com", "user-flag"),
    (f"curl -u {LITERAL_LOGIN} https://example.org", "user-flag"),
    ('curl -H "Authorization: Bearer $API_TOKEN" https://api.example.com', "auth-header"),
    ("curl -H 'Authorization: token ghp_abc' https://api.github.com", "auth-header"),
    ('gh api -H "Authorization: token $(gh auth token)" /user', "auth-header"),
    ('curl --header "PRIVATE-TOKEN: <your-token>" https://gitlab.example.com', "auth-header"),
    ('["curl", "-H", f"Authorization: Bearer {token}"]', "auth-header"),
    ('mysqladmin --password "$DB_PASSWORD" status', "secret-flag"),
    ("tool --password=hunter2", "secret-flag"),
    ("deploy --token=abc123", "secret-flag"),
    ('deploy --token "$DEPLOY_TOKEN"', "secret-flag"),
    ("cli --api-key <key> list", "secret-flag"),
    ('mytool "$OPENAI_API_KEY" --verbose', "secret-var"),
    ("git clone https://x-access-token:${GH_TOKEN}@github.com/o/r.git", "secret-var"),
    ('cat notes | upload "$CLIENT_SECRET"', "secret-var"),
    ('curl -H "X-Custom: $(printf %s "$SERVICE_TOKEN")" https://x', "secret-var"),
    ('upload --verbose "${ACCESS_TOKEN_FILE}"', "secret-var"),
]

SAFE = [
    'GH_TOKEN="$GH_TOKEN" gh api repos/o/r/pulls',
    "gh auth login --with-token < token.txt",
    "gh auth status",
    "uv publish --token-file ~/.config/pypi-token",
    'printf "%s" "$REGISTRY_PASSWORD" | docker login --password-stdin ghcr.io',
    'export API_TOKEN="$(cat ~/.config/token)"',
    "API_TOKEN=$(cat ~/.config/token)",
    '[ -n "$GITHUB_TOKEN" ] || exit 2',
    ': "${UV_PUBLISH_TOKEN:?set UV_PUBLISH_TOKEN}"',
    'curl -H @<(printf "Authorization: Bearer %s\\n" "$API_TOKEN") https://api.example.com',
    'token = os.environ["GITHUB_TOKEN"]',
    'parser.add_argument("--token-file")',
    "git push -u origin main",
    "docker run -u 1000:1000 image",
    'echo "$PATH" | tr : "\\n"',
    "Pass the --token flag only in tests.",
    # A plural TOKENS is a token count, not a credential.
    "Files stay under ${MAX_TOKENS} tokens so an agent can read any file whole",
    'summarize "$TOKENS" report.md',
    "curl -s https://api.example.com/v1/orders?limit=2",
]


def test_detector_fires_on_credentials_in_argv():
    missed = [
        (command, rule)
        for command, rule in POSITIVE
        if rule not in check_secret_argv.rules_hit(command)
    ]
    assert missed == []


def test_detector_stays_quiet_on_safe_forms():
    flagged = {command: check_secret_argv.rules_hit(command) for command in SAFE}
    assert {command: rules for command, rules in flagged.items() if rules} == {}


def run_gate(root: Path, capsys):
    code = check_secret_argv.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_markdown_code_is_scanned_and_prose_is_not(tmp_path, capsys):
    body = (
        "Never run curl -u with $AUTH_PAT in prose.\n\n"
        '```bash\ncurl -u ":$AUTH_PAT" "$URL"\n```\n\n'
        'Or inline: `deploy --token "$DEPLOY_TOKEN"`.\n'
    )
    write(tmp_path, "skills/demo/SKILL.md", body)

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:4: user-flag" in err
    assert "skills/demo/SKILL.md:7: secret-flag" in err
    assert ":1:" not in err
    assert "--token-file" in err


def test_scripts_and_instructions_are_scanned_but_tests_are_not(tmp_path, capsys):
    write(tmp_path, "instructions/90-x.md", "```sh\ntool --password=hunter2\n```\n")
    write(tmp_path, "skills/demo/scripts/run.sh", '#!/bin/sh\nmytool "$OPENAI_API_KEY"\n')
    write(tmp_path, "scripts/test_x.py", f"CASE = 'curl -u {LITERAL_LOGIN} https://x'\n")
    write(tmp_path, "skills/demo/scripts/test_run.py", "CASE = 'tool --password=x'\n")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "instructions/90-x.md:2: secret-flag" in err
    assert "skills/demo/scripts/run.sh:2: secret-var" in err
    assert "test_" not in err


def test_safe_tree_passes(tmp_path, capsys):
    write(tmp_path, "skills/demo/SKILL.md", '```bash\nGH_TOKEN="$GH_TOKEN" gh api user\n```\n')

    code, out, err = run_gate(tmp_path, capsys)

    assert code == 0, err
    assert "secret argv ok (1 files)" in out


def test_unknown_argument_is_a_usage_error(capsys):
    assert check_secret_argv.main(["--bogus"]) == 2
    assert "usage:" in capsys.readouterr().err
