"""Fixtures for the loop.sh test suites: stub runner and forge CLIs, a PoC repo.

Each stub records its argv; the runner stub commits the file the item's check
looks for, so by default one item passes and the loop ends with a ready PR.
"""

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

LOOP = Path(__file__).resolve().parent.parent / "assets" / "loop.sh"

RUNNER_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/$(basename "$0").argv"
for arg in "$@"; do
  if [[ $arg == "Loop infrastructure preflight."* ]]; then
    if [[ ${STUB_PREFLIGHT_FAILURE:-} == 1 ]]; then
      echo 'error building bubblewrap command: app-server socket directory must be' \\
        'a user-owned directory with mode 0700'
      exit 0
    fi
    if [[ ${STUB_PREFLIGHT_FAILURE:-} == 2 ]]; then
      echo shell-ok
      exit 0
    fi
    command=${arg#*$'\\n'}
    command=${command%%$'\\n'*}
    bash -c "$command"
    exit $?
  fi
done
echo task >> "$STUB_LOG/task_calls"
case ${STUB_TASK:-work} in
  fail) # the CLI itself fails: no work done
    echo 'error: 401 Unauthorized' >&2
    exit 1
    ;;
  blocked)
    echo 'BLOCKED: spec contradicts itself'
    exit "${STUB_TASK_EXIT:-0}"
    ;;
  idle) # the agent runs fine but commits nothing, so the check fails
    exit 0
    ;;
esac
echo done > done.txt
git add done.txt
git commit -qm "feat(prd-01): done"
exit "${STUB_TASK_EXIT:-0}"
"""

GH_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/gh.argv"
"""

# `az extension show` must succeed for the precondition; only `az repos` is logged.
AZ_STUB = """#!/usr/bin/env bash
[[ $1 == repos ]] && printf '%s\\0' "$@" > "$STUB_LOG/az.argv"
exit 0
"""

FORGE_URLS = {
    "github": "https://github.com/o/r.git",
    "azure": "https://dev.azure.com/o/p/_git/r",
}

EXPECTED_ARGV_HEAD = {
    "claude": ["-p"],
    "codex": ["exec", "--sandbox", "danger-full-access"],
    "opencode": ["run", "--auto"],
}

OPEN_ITEM = {
    "id": "prd-01",
    "title": "Create the done marker",
    "deps": [],
    "check": "test -f done.txt",
    "passes": False,
    "attempts": 0,
    "origin": "spec",
}

PRD = {"approved": True, "language": "bash", "target": "cli"}


def git(repo, *args):
    subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        check=True,
        capture_output=True,
    )


def make_poc(parent, origin_url=FORGE_URLS["github"], done_items=(), check=OPEN_ITEM["check"]):
    """A greenfield repo released for Phase 2, with a bare origin and stubs on PATH.

    origin carries a forge-looking URL; an insteadOf rewrite sends the push to
    the local bare repo. done_items are prepended as already-passed items;
    check replaces the open item's check command.
    """
    parent = Path(parent)
    origin = parent / "origin.git"
    repo = parent / "repo"
    bin_dir = parent / "bin"
    log_dir = parent / "log"
    for d in (repo, bin_dir, log_dir):
        d.mkdir()
    subprocess.run(  # noqa: S603 -- test creates a temporary bare repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "init",
            "-q",
            "--bare",
            str(origin),
        ],
        check=True,
    )
    git(repo, "init", "-q", "-b", "main")
    # Per-repo identity: CI runners have no global one, and loop.sh commits too.
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "remote", "add", "origin", origin_url)
    git(repo, "config", f"url.{origin}.insteadOf", origin_url)
    (repo / "plans").mkdir()
    (repo / "plans" / "SPEC.md").write_text(
        "---\nlanguage: bash\ntarget: cli\n---\n## Goal\nA marker.\n"
        "## Definition of Done\n- done.txt exists\n"
    )
    prd = {**PRD, "items": [*done_items, {**OPEN_ITEM, "check": check}]}
    (repo / "plans" / "prd.json").write_text(json.dumps(prd, indent=2))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "chore(plans): spec and prd")
    for name in EXPECTED_ARGV_HEAD:
        (bin_dir / name).write_text(RUNNER_STUB)
    (bin_dir / "gh").write_text(GH_STUB)
    (bin_dir / "az").write_text(AZ_STUB)
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log_dir),
    }
    env.pop("POC_AGENT", None)
    env.pop("POC_AGENT_FLAGS", None)
    return repo, log_dir, env


def run_loop(repo, env):
    return subprocess.run(  # noqa: S603 -- test runs the repo's loop against controlled stubs.
        ["bash", str(LOOP)],  # noqa: S607 -- Bash resolves from PATH in the test environment.
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def committed(repo, path):
    return subprocess.run(  # noqa: S603 -- test reads a temporary repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "-C",
            str(repo),
            "show",
            f"HEAD:{path}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def current_branch(repo):
    return subprocess.run(  # noqa: S603 -- test reads a temporary repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "-C",
            str(repo),
            "branch",
            "--show-current",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def read_argv(log_dir, name):
    return (log_dir / f"{name}.argv").read_text().split("\0")[:-1]


def task_calls(log_dir):
    """Number of task (non-preflight) runner calls the stub recorded."""
    calls = log_dir / "task_calls"
    return len(calls.read_text().splitlines()) if calls.exists() else 0


def stop_diagnosis(stderr):
    """The one-line reason infrastructure_stop prints before the shared guidance."""
    return next(line for line in stderr.splitlines() if line.startswith("Infrastructure stop:"))


def fail_command(repo, name, arg_glob):
    """Put a `name` wrapper on PATH that fails like a read-only file system.

    The wrapper exits 1 when any argument matches the bash glob arg_glob and
    otherwise runs the real command.
    """
    real = shlex.quote(shutil.which(name))
    wrapper = repo.parent / "bin" / name
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'for arg in "$@"; do\n'
        f"  if [[ $arg == {arg_glob} ]]; then\n"
        f'    echo "{name}: $arg: Read-only file system" >&2\n'
        "    exit 1\n"
        "  fi\n"
        f'done\nexec {real} "$@"\n'
    )
    wrapper.chmod(0o755)
