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

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cli
from cli import ScriptError, git


@dataclass(frozen=True)
class BranchDiff:
    """What HEAD changed since it left the base ref, in one repository."""

    repo: Path
    base: str

    def diff(self, *options: str, paths: tuple[str, ...] = ()) -> str | None:
        limit = ("--", *paths) if paths else ()
        return git(self.repo, "diff", *options, f"{self.base}...HEAD", *limit)


def changed_files(branch: BranchDiff) -> list[dict]:
    listing = branch.diff("-z", "--name-status", "-M")
    if listing is None:
        raise ScriptError(2, "cannot diff --base against HEAD (unknown ref?)")
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


def only_eol_whitespace(branch: BranchDiff, entry: dict) -> bool:
    paths = (entry["old_path"], entry["path"]) if "old_path" in entry else (entry["path"],)
    patch = branch.diff("-M", "--ignore-space-at-eol", "--ignore-cr-at-eol", paths=paths)
    if patch is None:
        raise ScriptError(2, "cannot diff a changed file against --base")
    markers = ("@@", "old mode", "new mode", "Binary files", "GIT binary patch")
    return not any(line.startswith(markers) for line in patch.splitlines())


NO_CI = "no CI status: only renames and formatting can be skimmed"


def read_json(path: Path) -> dict:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ScriptError(3, f"cannot read {path.name} as JSON") from err
    if not isinstance(parsed, dict):
        raise ScriptError(3, f"{path.name} is not a JSON object")
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
        raise ScriptError(3, "ci.json: state must be green, failing, pending or none")
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


def judge(branch: BranchDiff, entry: dict, ci: dict) -> None:
    if entry["status"] == "R100":
        entry.update(skim=True, proof="rename", reason="renamed or moved, content identical")
    elif entry["status"][0] in "MR" and only_eol_whitespace(branch, entry):
        entry.update(
            skim=True,
            proof="formatting",
            reason="only trailing whitespace or line endings changed",
        )
    elif ci["proof"]:
        entry.update(skim=True, proof="ci-green", reason=ci["reason"])
    else:
        entry.update(skim=False, proof=None, reason=f"content changed; {ci['reason']}")


def report(repo: Path, base: str, inputs: Path | None) -> None:
    if git(repo, "rev-parse", "--git-dir") is None:
        raise ScriptError(2, "--repo is not inside a git repository")
    ci = ci_proof(repo, inputs)
    branch = BranchDiff(repo, base)
    files = changed_files(branch)
    for entry in files:
        judge(branch, entry, ci)
    print(json.dumps({"ci": ci, "files": files}, indent=2))


def main(argv: list[str]) -> int:
    parser = cli.parser(__doc__, "skim_proof.py")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args(argv)
    return cli.run("skim_proof.py", lambda: report(args.repo, args.base, args.inputs))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
