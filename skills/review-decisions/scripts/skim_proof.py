#!/usr/bin/env python3
"""List each changed file and whether "skim is enough" can be proven for it.

usage: skim_proof.py --repo DIR --base REF [--inputs FILE]

Compares REF...HEAD in DIR. A file may be skimmed only with proof:

  rename      moved or renamed with identical content (100% similarity)
  formatting  only trailing whitespace or line endings
              differ, also after a rename; indentation and spacing inside a
              line are not formal, since they can change meaning (Python,
              YAML, string literals)
  ci-green    the CI status in --inputs is green, and it was read for the
              commit checked out here

Every other file gets "skim": false: the reviewer looks at it in the PR.
Without --inputs, or without a ci.json in it, only the formal proofs apply.

--inputs is the inputs.json manifest gather_inputs.py wrote; its ci.json is
read from the same directory.

output (stdout, JSON):
  {"ci": {"proof": bool, "reason": str},
   "files": [{"path", "old_path" (renames only), "status", "skim", "proof", "reason"}]}
  "proof" is "rename", "formatting", "ci-green" or null.

exit codes: 0 ok; 1 usage error; 2 DIR not a git repository or REF unknown;
3 --inputs or its ci.json unreadable or malformed.

examples:
  python3 scripts/skim_proof.py --repo . --base main
  python3 scripts/skim_proof.py --repo . --base origin/main --inputs /tmp/rd.x1/inputs.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class ProofError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def git(repo: Path, *args: str) -> str | None:
    proc = subprocess.run(  # noqa: S603 -- fixed Git argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def changed_files(repo: Path, base: str) -> list[dict]:
    listing = git(repo, "diff", "-z", "--name-status", "-M", f"{base}...HEAD")
    if listing is None:
        raise ProofError(2, "cannot diff --base against HEAD (unknown ref?)")
    fields = listing.split("\0")
    entries = []
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status[0] in "RC":
            entries.append({"path": fields[i + 2], "old_path": fields[i + 1], "status": status})
            i += 3
        else:
            entries.append({"path": fields[i + 1], "status": status})
            i += 2
    return entries


def only_eol_whitespace(repo: Path, base: str, entry: dict) -> bool:
    paths = [entry["old_path"], entry["path"]] if "old_path" in entry else [entry["path"]]
    patch = git(
        repo,
        "diff",
        "-M",
        "--ignore-space-at-eol",
        "--ignore-cr-at-eol",
        f"{base}...HEAD",
        "--",
        *paths,
    )
    if patch is None:
        raise ProofError(2, "cannot diff a changed file against --base")
    markers = ("@@", "old mode", "new mode", "Binary files", "GIT binary patch")
    return not any(line.startswith(markers) for line in patch.splitlines())


NO_CI = "no CI status: only renames and formatting can be skimmed"


def read_json(path: Path) -> dict:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ProofError(3, f"cannot read {path.name} as JSON") from err
    if not isinstance(parsed, dict):
        raise ProofError(3, f"{path.name} is not a JSON object")
    return parsed


def ci_proof(repo: Path, inputs: Path | None) -> dict:
    """Whether green CI proves the checked-out commit; the reason says why not."""
    if inputs is None:
        return {"proof": False, "reason": NO_CI}
    manifest = read_json(inputs)
    ci_file = (manifest.get("files") or {}).get("ci")
    if not ci_file:
        return {"proof": False, "reason": NO_CI}
    state = read_json(inputs.parent / ci_file).get("state")
    if state not in {"green", "failing", "pending", "none"}:
        raise ProofError(3, "ci.json: state must be green, failing, pending or none")
    if state != "green":
        return {"proof": False, "reason": f"CI is {state}, not green"}
    head_sha = (manifest.get("pr") or {}).get("head_sha")
    local = (git(repo, "rev-parse", "HEAD") or "").strip()
    if not head_sha or head_sha != local:
        return {
            "proof": False,
            "reason": "CI is green for the PR head, not for the commit checked out here",
        }
    return {"proof": True, "reason": f"CI is green for {local[:12]}"}


def judge(repo: Path, base: str, entry: dict, ci: dict) -> None:
    if entry["status"] == "R100":
        entry.update(skim=True, proof="rename", reason="renamed or moved, content identical")
    elif entry["status"][0] in "MR" and only_eol_whitespace(repo, base, entry):
        entry.update(
            skim=True,
            proof="formatting",
            reason="only trailing whitespace or line endings changed",
        )
    elif ci["proof"]:
        entry.update(skim=True, proof="ci-green", reason=ci["reason"])
    else:
        entry.update(skim=False, proof=None, reason=f"content changed; {ci['reason']}")


class Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(1, f"skim_proof.py: {message}\n")


def main(argv: list[str]) -> int:
    parser = Parser(
        prog="skim_proof.py",
        usage="skim_proof.py --repo DIR --base REF [--inputs FILE]",
        description=__doc__.split("\n", 3)[3],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args(argv)
    try:
        if git(args.repo, "rev-parse", "--git-dir") is None:
            raise ProofError(2, "--repo is not inside a git repository")
        ci = ci_proof(args.repo, args.inputs)
        files = changed_files(args.repo, args.base)
        for entry in files:
            judge(args.repo, args.base, entry, ci)
    except ProofError as err:
        print(f"skim_proof.py: {err}", file=sys.stderr)
        return err.code
    print(json.dumps({"ci": ci, "files": files}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
