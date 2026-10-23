#!/usr/bin/env python3
"""Flag examples that pass a credential on the command line.

Run from repo root:
    python3 scripts/check_secret_argv.py    # exit 1 when a credential sits in argv

instructions/on-demand/85-agent-scripts.md: secrets come from env or config, never a
flag. A value in argv lands in shell history and in every `ps` listing on the
host, and an agent copies the commands a skill shows it. This gate reads the
shell an agent would run — fenced blocks and code spans of Markdown, and all
lines of shell, Python and config files — under skills/, instructions/,
plugins/ and scripts/, and reports:

- user-flag: the curl-style user flag whose value holds a secret variable or
  a `user:password` literal.
- auth-header: an Authorization (or API-key / private-token) header given as
  a header flag, literal or variable alike.
- secret-flag: a password, token, API-key or secret flag followed by a value.
  The file and stdin variants of those flags are the safe form and pass.
- secret-var: a variable named like a secret (TOKEN, SECRET, PASSWORD,
  API_KEY, a PAT segment) expanded into a command's arguments. Assigning,
  exporting or testing it passes, and so does handing it to a shell builtin
  (echo, printf), whose arguments never reach a process's argv.

Safe forms stay quiet: the program reading the variable from its environment
(`GH_TOKEN=... gh api`, `os.environ`), a token file, stdin, gh's own auth,
curl's header-from-file form. Test files hold the patterns as data and are
not scanned. Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("skills", "instructions", "plugins", "scripts")
SUFFIXES = {".md", ".sh", ".bash", ".py", ".js", ".json", ".yaml", ".yml", ".toml", ".txt"}

USAGE = """usage: check_secret_argv.py [--root DIR] [--help]

Flag commands that put a credential in argv (user flag with a secret, an
Authorization header flag, a password/token flag with a value, a secret-named
variable expanded into arguments) in skills/, instructions/, plugins/ and
scripts/. Markdown prose is skipped; its code blocks and spans are read.

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_secret_argv.py
  python3 scripts/check_secret_argv.py --root /path/to/checkout

exit: 0 no credential in argv | 1 credentials in argv | 2 usage error
"""

DIRECTION = (
    "let the program read the secret from its environment or a file "
    "(GH_TOKEN=... gh, --token-file, --password-stdin, "
    "curl -H @<(printf 'Authorization: Bearer %s\\n' \"$TOKEN\"))"
)

CREDENTIAL_NAME_PATTERN = r"[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY)[A-Z0-9_]*|(?:[A-Z0-9_]*_)?PAT(?:_[A-Z0-9_]*)?"
SECRET_VAR = re.compile(rf"\$\{{?(?:{CREDENTIAL_NAME_PATTERN})\b")
FLAG_EDGE = r"(?<![\w-])"
# A value that is plainly data, not the next word of a sentence: a variable,
# a command substitution, a quoted string, a placeholder, or a long literal.
VALUE = r"""(?:\$|["'<]|\{\{|[A-Za-z0-9_\-]*\d[A-Za-z0-9_\-]{10,})"""
USER_FLAG = re.compile(rf"{FLAG_EDGE}(?:-u|--user)(?:=|\s+)(?P<value>\S+)")
USER_PASSWORD = re.compile(r"""^["']?[^\s:$"']*:[^\s$"'<]+""")
AUTH_HEADER = re.compile(
    rf"""{FLAG_EDGE}(?:-H|--header)(?:\s*=?\s*|["']?\s*,\s*[a-z]*)["']?"""
    r"(?:Authorization|Proxy-Authorization|X-API-Key|X-Auth-Token|PRIVATE-TOKEN)\s*:",
    re.IGNORECASE,
)
SECRET_FLAG = re.compile(
    rf"{FLAG_EDGE}--(?:password|passwd|token|api-key|apikey|secret|client-secret|"
    rf"access-token|auth-token|pat)(?:=\S|\s+{VALUE})"
)
CURL = re.compile(r"\bcurl\b")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
COMMAND_SEPARATOR = re.compile(r"\|\||&&|;|\|")
LEADING_ASSIGNMENTS = re.compile(r"""^\s*(?:[A-Za-z_]\w*=(?:"[^"]*"|'[^']*'|\S*)\s*)+""")
# Shell builtins: their arguments never reach a process's argv.
NON_ARGV_COMMANDS = {
    *("[", "[[", "test", ":", "echo", "printf"),
    *("export", "local", "readonly", "declare", "unset"),
}
# A builtin inside process substitution hands the program a /dev/fd path, not
# the value: curl's header-from-file form `-H @<(printf ...)`.
BUILTIN_PROCESS_SUBST = re.compile(r"<\(\s*(?:printf|echo)\b[^)]*\)")


def scanned_files(root: Path) -> list[Path]:
    candidates = [
        path
        for directory in SCAN_DIRS
        for path in sorted((root / directory).rglob("*"))
        if path.suffix in SUFFIXES
        and not path.name.startswith("test_")
        and "fixtures" not in path.parts
    ]
    return unique_real_files(candidates)


def secret_argv(path: Path) -> list[tuple[int, str]]:
    """(line number, rule) for each command line that puts a secret in argv."""
    text = path.read_text(encoding="utf-8")
    lines = markdown_code(text) if path.suffix == ".md" else enumerate(text.splitlines(), 1)
    found: list[tuple[int, str]] = []
    for number, code in lines:
        for rule in rules_hit(code):
            found.append((number, rule))
    return list(dict.fromkeys(found))


def rules_hit(code: str) -> list[str]:
    hits = []
    for match in USER_FLAG.finditer(code):
        value = match.group("value")
        if SECRET_VAR.search(value) or (CURL.search(code) and USER_PASSWORD.match(value)):
            hits.append("user-flag")
            break
    if AUTH_HEADER.search(code):
        hits.append("auth-header")
    if SECRET_FLAG.search(code):
        hits.append("secret-flag")
    shell = BUILTIN_PROCESS_SUBST.sub("", code)
    if not hits and any(secret_in_arguments(command) for command in COMMAND_SEPARATOR.split(shell)):
        hits.append("secret-var")
    return hits


def secret_in_arguments(command: str) -> bool:
    """Whether a simple command expands a secret-named variable into its arguments."""
    # NAME=value prefixes set the environment, which is the safe channel.
    rest = LEADING_ASSIGNMENTS.sub("", command, count=1)
    if not SECRET_VAR.search(rest):
        return False
    words = rest.split()
    return words[0] not in NON_ARGV_COMMANDS


def markdown_code(text: str) -> list[tuple[int, str]]:
    """(line number, code) for fenced-block lines and inline code spans."""
    code: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        opener = FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            else:
                code.append((number, line))
            continue
        if opener:
            fence = opener.group(1)
            continue
        code.extend((number, span.group(2)) for span in CODE_SPAN.finditer(line))
    return code


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    root = REPO_ROOT
    if args[:1] == ["--root"] and len(args) == 2:
        root = Path(args[1]).resolve()
    elif args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2
    files = scanned_files(root)
    violations = [
        f"{path.relative_to(root)}:{number}: {rule}"
        for path in files
        for number, rule in secret_argv(path)
    ]
    if violations:
        sys.stderr.write(f"credentials in argv: {len(violations)} in {len(files)} files\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(f"\nFix: {DIRECTION}.\n")
        return 1
    print(f"secret argv ok ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
